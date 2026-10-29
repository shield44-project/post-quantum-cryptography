"""Watermark X-ray: read the hidden code out of a model and show every bit.

    python -m pqctl.actions.xray --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt
    python -m pqctl.actions.xray --model runs/baseline/seed0/model.pt            # unmarked model
    python -m pqctl.actions.xray --model ... --key mallory                        # read with Mallory's key
    python -m pqctl.actions.xray --model ... --key random                         # read with a random key

Steps (the same as verify_model stages 3 and 4, but every intermediate value is kept):
  carrier v (576 numbers) -> scores X @ v -> raw bits (score > 0) -> error correction -> 256 payload bits
  -> compare with SHA-256(signed manifest).
"""
import argparse
import json
import secrets
from pathlib import Path

from pqctl.actions import emit, r, run_main

KEYS = {"ours": "keys/watermark_key.bin", "mallory": "mallory/keys/watermark_key.bin"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--key", default="ours", help="ours, mallory, random, or a path")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--ecc", default=None)
    ap.add_argument("--n-bits", type=int, default=None)
    args = ap.parse_args()

    from crypto.manifest import payload_bits
    from embedding.ecc import get_code
    from embedding.extract import load_smallcnn
    from embedding.keys import key_fingerprint, load_key
    from embedding.projection import ProjectionWatermark, carrier_vector, get_weight
    from verify.verify_model import resolve_settings

    manifest = json.loads((Path(args.release_dir) / "signed_manifest.json").read_text())["manifest"]
    settings, source = resolve_settings(args.model, args.ecc, args.n_bits)
    if not (Path(args.model).parent / "final.json").exists() and args.ecc is None:
        settings.update(ecc="rs32")          # an unmarked model has no settings: read it the way our models are read
        source = "our scheme (no final.json next to this model)"
    n_payload = int(settings["n_bits"] or manifest["watermark"]["payload_bits"])

    if args.key == "random":
        key, key_label = secrets.token_bytes(32), "a random key"
    else:
        path = KEYS.get(args.key, args.key)
        key, key_label = load_key(path), path
    fp = key_fingerprint(key)

    code = get_code(settings["ecc"], n_payload)
    model = load_smallcnn(args.model, int(manifest["model"]["width"]))
    weight = get_weight(model, settings["layer"])
    wm = ProjectionWatermark(key, settings["layer"], code.n_bits, settings["mode"], weight.shape)
    raw_bits, logits = wm.extract(model)
    v = carrier_vector(weight.detach(), settings["mode"]).float().tolist()

    expected_payload = payload_bits(manifest, n_payload)
    expected_code = code.encode(expected_payload)
    raw_wrong = [int(a != b) for a, b in zip(raw_bits, expected_code)]
    d = code.decode(logits)
    decoded = d.get("bits") or []
    match = sum(int(a == b) for a, b in zip(decoded, expected_payload)) if d["ok"] else 0
    verdict = "VERIFIED" if d["ok"] and match == len(expected_payload) else "REJECTED"

    print("model     : %s" % args.model)
    print("key       : %s (fingerprint %s)" % (key_label, fp))
    print("settings  : ecc %s | %d payload bits -> %d code values | layer %s | mode %s  (%s)"
          % (settings["ecc"], n_payload, code.n_bits, settings["layer"], settings["mode"], source))
    print("carrier   : %d numbers" % len(v))
    print("raw bits  : %d of %d wrong before repair (%.1f%%), weakest score %.3f"
          % (sum(raw_wrong), code.n_bits, 100.0 * sum(raw_wrong) / code.n_bits, min(abs(z) for z in logits)))
    if d["ok"]:
        print("repair    : decoded, %d bytes corrected, %d erased" % (d["corrected"], d["erasures"]))
        print("payload   : %d of %d bits match SHA-256(signed manifest)" % (match, len(expected_payload)))
    else:
        print("repair    : FAILED - too much damage, or no watermark made with this key")
    print(verdict)
    emit({"model": args.model, "key": key_label, "fingerprint": fp, "settings": settings, "source": source,
          "n_payload": n_payload, "n_code": code.n_bits, "carrier": [r(x, 4) for x in v],
          "logits": [r(z) for z in logits], "expected_code": expected_code, "raw_bits": raw_bits,
          "raw_wrong": sum(raw_wrong), "decoded_ok": bool(d["ok"]), "corrected": d.get("corrected", 0),
          "erasures": d.get("erasures", 0), "decoded": decoded, "expected_payload": expected_payload,
          "payload_match": match, "margin": r(min(abs(z) for z in logits)),
          "mean_margin": r(sum(abs(z) for z in logits) / len(logits)), "verdict": verdict})
    return 0                  # REJECTED is a valid answer here, not a failure of the tool


if __name__ == "__main__":
    run_main(main)

"""Tamper lab: change something in a COPY of the signed release and see whether verification still passes.

    python -m pqctl.actions.tamper_lab --developer-id mallory
    python -m pqctl.actions.tamper_lab --width 64 --flip-signature
    python -m pqctl.actions.tamper_lab --wrong-key
    python -m pqctl.actions.tamper_lab --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt --developer-id mallory

The real release/ folder is never touched: edits are made in a temporary copy, checked with
verify.verify_release (and optionally verify.verify_model on a model), then the copy is deleted.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from pqctl.actions import emit, run_main


def flip_hex_char(s, pos):
    c = s[pos]
    return s[:pos] + ("0" if c != "0" else "1") + s[pos + 1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--public-key", default="keys/public_key.bin")
    ap.add_argument("--developer-id", default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--num-samples", type=int, default=None)
    ap.add_argument("--created", default=None, help="new created_utc text")
    ap.add_argument("--flip-root", action="store_true", help="change one character of the dataset Merkle root")
    ap.add_argument("--flip-signature", action="store_true", help="change one character of the signature")
    ap.add_argument("--flip-payload", action="store_true", help="change one character of payload.hex")
    ap.add_argument("--wrong-key", action="store_true", help="check with a freshly made, unrelated public key")
    ap.add_argument("--model", default=None, help="also run verify_model on this model against the edited release")
    args = ap.parse_args()

    from crypto.manifest import bits_to_hex, canonical_bytes, payload_bits
    from verify.verify_release import verify_release
    import hashlib

    tmp = Path(tempfile.mkdtemp(prefix="pqctl_tamper_"))
    try:
        rel = tmp / "release"
        shutil.copytree(args.release_dir, rel)
        p = rel / "signed_manifest.json"
        signed = json.loads(p.read_text())
        m = signed["manifest"]
        before_hash = hashlib.sha256(canonical_bytes(m)).hexdigest()
        changes = []

        def change(what, old, new):
            changes.append({"what": what, "old": str(old), "new": str(new)})
            print("edit      : %s: %r -> %r" % (what, old, new))

        if args.developer_id is not None and args.developer_id != m["developer_id"]:
            change("developer_id", m["developer_id"], args.developer_id)
            m["developer_id"] = args.developer_id
        if args.width is not None and args.width != m["model"]["width"]:
            change("model.width", m["model"]["width"], args.width)
            m["model"]["width"] = args.width
        if args.num_samples is not None and args.num_samples != m["dataset"]["num_samples"]:
            change("dataset.num_samples", m["dataset"]["num_samples"], args.num_samples)
            m["dataset"]["num_samples"] = args.num_samples
        if args.created and args.created != m.get("created_utc"):
            change("created_utc", m.get("created_utc"), args.created)
            m["created_utc"] = args.created
        if args.flip_root:
            old = m["dataset"]["merkle_root_sha256"]
            m["dataset"]["merkle_root_sha256"] = flip_hex_char(old, 0)
            change("dataset.merkle_root_sha256 (first character)", old[:12] + "…", m["dataset"]["merkle_root_sha256"][:12] + "…")
        if args.flip_signature:
            old = signed["signature_hex"]
            signed["signature_hex"] = flip_hex_char(old, 100)
            change("signature (character 100 of %d)" % len(old), old[96:104], signed["signature_hex"][96:104])
        p.write_text(json.dumps(signed, indent=2, sort_keys=True))
        if args.flip_payload:
            pp = rel / "payload.hex"
            old = pp.read_text().strip()
            pp.write_text(flip_hex_char(old, 0) + "\n")
            change("payload.hex (first character)", old[:12] + "…", flip_hex_char(old, 0)[:12] + "…")

        pk = args.public_key
        if args.wrong_key:
            from crypto.signing import generate_keys
            other = tmp / "other_public_key.bin"
            other.write_bytes(generate_keys()[0])
            pk = str(other)
            change("public key used to check", args.public_key, "a freshly made, unrelated key")
        if not changes:
            print("edit      : nothing changed (the untouched release)")

        after_hash = hashlib.sha256(canonical_bytes(m)).hexdigest()
        print("hash      : SHA-256(manifest) %s -> %s" % (before_hash[:16] + "…", after_hash[:16] + "…"))
        ok, checks = verify_release(rel, pk)
        model_res = None
        if args.model:
            from verify.verify_model import verify_model
            mok, mchecks, _ = verify_model(args.model, pk, "keys/watermark_key.bin", rel)
            model_res = {"ok": bool(mok), "checks": [[c[0], bool(c[1]), c[2]] for c in mchecks]}
            checks_to_print = mchecks
        else:
            checks_to_print = checks
        for name, passed, detail in checks_to_print:
            print("%s  %s%s" % ("PASS" if passed else "FAIL", name, "  (" + detail + ")" if detail else ""))
        final_ok = model_res["ok"] if model_res else ok
        print("VERIFIED" if final_ok else "REJECTED")
        emit({"changes": changes, "verdict": "VERIFIED" if final_ok else "REJECTED", "release_ok": bool(ok),
              "checks": [[c[0], bool(c[1]), c[2]] for c in checks], "model": model_res,
              "hash_before": before_hash, "hash_after": after_hash,
              "payload_before": bits_to_hex(payload_bits(json.loads((Path(args.release_dir) / "signed_manifest.json").read_text())["manifest"])),
              "payload_after": bits_to_hex(payload_bits(m))})
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    run_main(main)

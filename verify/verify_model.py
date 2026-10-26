"""Phase 5: verify a MODEL against a signed release (runs LOCALLY, needs liboqs + torch).

    python -m verify.verify_model --model runs/wm_v0/lam1_n32/seed0/model.pt \
        --public-key keys/public_key.bin --wm-key keys/watermark_key.bin --release-dir release

Checks, in order. A failing stage stops the run, because later stages trust earlier ones:
  1. release   : files load, key id, algorithm, signature, payload.hex   (verify.verify_release)
  2. model     : architecture from the SIGNED manifest, weights load at the signed width,
                 parameter count == manifest model.num_params
  3. watermark : X @ v with the watermark key, then ECC decode
  4. payload   : decoded bits == first n_bits of SHA-256(signed manifest)
VERIFIED only if every check passes (a decoder saying "ok" is never enough on its own).
Exit code 0 = VERIFIED, 1 = REJECTED.

Watermark settings (ecc, n_bits, layer, mode) are not in the manifest (adding them would change
the payload of every trained model). They come from the command line, else from the final.json
next to the model, else the Phase 3 defaults; the source is printed.
"""
import argparse
import json
import sys
from pathlib import Path

from crypto.manifest import payload_bits
from verify.verify_release import verify_release

DEFAULTS = {"ecc": "none", "n_bits": 32, "layer": "features.6.0.weight", "mode": "mean"}


def resolve_settings(model_path, ecc=None, n_bits=None, layer=None, mode=None):
    """Return (settings dict, source text). CLI value > final.json next to the model > DEFAULTS."""
    given = {"ecc": ecc, "n_bits": n_bits, "layer": layer, "mode": mode}
    f = Path(model_path).parent / "final.json"
    try:
        run = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        run = {}
    settings, sources = {}, set()
    for k, default in DEFAULTS.items():
        if given[k] is not None:
            settings[k], src = given[k], "command line"
        elif k in run:
            settings[k], src = run[k], "final.json"
        else:
            settings[k], src = default, "defaults"
        sources.add(src)
    return settings, " + ".join(sorted(sources))


def verify_model(model_path, public_key_path, wm_key_path, release_dir,
                 ecc=None, n_bits=None, layer=None, mode=None):
    """Return (ok, checks, settings). checks = list of (name, passed, detail)."""
    settings, source = resolve_settings(model_path, ecc, n_bits, layer, mode)
    settings["source"] = source

    # 1. release: signature etc.
    ok, checks = verify_release(release_dir, public_key_path)
    if not ok:
        return False, checks, settings

    def add(name, passed, detail=""):
        checks.append((name, bool(passed), detail))
        return bool(passed)

    manifest = json.loads((Path(release_dir) / "signed_manifest.json").read_text())["manifest"]

    # 2. model
    try:
        import torch

        from embedding.extract import load_smallcnn

        arch, width = manifest["model"]["architecture"], int(manifest["model"]["width"])
        if not add("architecture is SmallCNN", arch == "SmallCNN", "manifest says %r" % arch):
            return False, checks, settings
        model = load_smallcnn(model_path, width)
        add("model loads at signed width %d" % width, True)
        n_params = sum(p.numel() for p in model.parameters())
        if not add("parameter count matches manifest", n_params == manifest["model"]["num_params"],
                   "model %d, manifest %d" % (n_params, manifest["model"]["num_params"])):
            return False, checks, settings
    except Exception as e:
        add("model loads at signed width", False, "%s: %s" % (type(e).__name__, e))
        return False, checks, settings

    # 3. watermark: extract + decode
    try:
        from embedding.ecc import get_code
        from embedding.keys import load_key
        from embedding.projection import ProjectionWatermark, get_weight

        if not 1 <= int(settings["n_bits"]) <= manifest["watermark"]["payload_bits"]:
            add("n_bits within signed payload size", False,
                "%s requested, manifest has %d" % (settings["n_bits"], manifest["watermark"]["payload_bits"]))
            return False, checks, settings
        code = get_code(settings["ecc"], int(settings["n_bits"]))
        wm = ProjectionWatermark(load_key(wm_key_path), settings["layer"], code.n_bits, settings["mode"],
                                 get_weight(model, settings["layer"]).shape)
        _, logits = wm.extract(model)
        margin = min(abs(z) for z in logits)
        d = code.decode(logits)
        if not add("watermark read (ecc %s, %d values)" % (settings["ecc"], code.n_bits), d["ok"],
                   "min margin %.2f, corrected %d, erasures %d" % (margin, d["corrected"], d["erasures"])
                   if d["ok"] else "decoder failed; min margin %.2f" % margin):
            return False, checks, settings
    except Exception as e:
        add("watermark extracted", False, "%s: %s" % (type(e).__name__, e))
        return False, checks, settings

    # 4. payload: compare with the SIGNED manifest, never with payload.hex
    expected = payload_bits(manifest, int(settings["n_bits"]))
    wrong = sum(int(a != b) for a, b in zip(d["bits"], expected))
    add("extracted payload == SHA-256(signed manifest)", wrong == 0,
        "%d bits match" % len(expected) if wrong == 0 else "%d of %d bits differ" % (wrong, len(expected)))
    return all(c[1] for c in checks), checks, settings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--public-key", default="keys/public_key.bin")
    ap.add_argument("--wm-key", default="keys/watermark_key.bin")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--ecc", default=None)
    ap.add_argument("--n-bits", type=int, default=None)
    ap.add_argument("--layer", default=None)
    ap.add_argument("--mode", default=None)
    args = ap.parse_args()

    ok, checks, s = verify_model(args.model, args.public_key, args.wm_key, args.release_dir,
                                 args.ecc, args.n_bits, args.layer, args.mode)
    print("watermark settings (%s): ecc %s | n_bits %s | layer %s | mode %s"
          % (s["source"], s["ecc"], s["n_bits"], s["layer"], s["mode"]))
    for name, passed, detail in checks:
        print("%s  %s%s" % ("PASS" if passed else "FAIL", name, "  (" + detail + ")" if detail else ""))
    print("VERIFIED" if ok else "REJECTED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

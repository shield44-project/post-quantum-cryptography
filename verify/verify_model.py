"""Phase 5: verify a MODEL against a signed release (runs LOCALLY, needs liboqs + torch).

    python -m verify.verify_model --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt \
        --public-key keys/public_key.bin --wm-key keys/watermark_key.bin --release-dir release
    # legacy Phase 3 models (32 of the 256 signed bits, weaker proof):
    python -m verify.verify_model --model runs/wm_v0/lam1_n32/seed0/model.pt --n-bits 32 --allow-short

Checks, in order. A failing stage stops the run, because later stages trust earlier ones:
  1. release   : files load, key id, algorithm, signature, payload.hex   (verify.verify_release)
  2. model     : architecture from the SIGNED manifest, weights load at the signed width,
                 parameter count == manifest model.num_params
  3. watermark : n_bits == signed payload_bits, X @ v with the watermark key, then ECC decode
  4. payload   : decoded bits == SHA-256(signed manifest), all payload_bits of it
VERIFIED only if every check passes (a decoder saying "ok" is never enough on its own).
Phase 6b additions:
  - permutation defence: if the payload does not decode, the carrier's input channels are re-aligned
    (embedding/align.py, Hungarian algorithm) and decoded again; only an exact match counts. --no-align turns it off.
  - DAMAGED: signature and model are fine, the exact payload cannot be recovered, but the code values still agree
    with the signed codeword far beyond chance (below 2^-64 for an unmarked model, counted WITHOUT re-alignment).
    This is the overwrite attack's footprint: evidence that the mark was there, not a proof of the exact payload.
Exit code 0 = VERIFIED, 1 = REJECTED, 2 = DAMAGED. --json prints the same result as one JSON object (for scripts and CI).
Model files are loaded as plain tensors only: a checkpoint that needs a full unpickle is REJECTED, never executed.

Watermark settings (ecc, n_bits, layer, mode) are not in the manifest (adding them would change
the payload of every trained model). They come from the command line, else from the final.json
next to the model, else the defaults (n_bits default = the signed payload_bits); the source is printed.
Because they are unsigned, n_bits must equal the signed payload_bits: with fewer bits a forger can
retry keys/layers until an unrelated model passes. --allow-short accepts fewer (legacy models only)
and prints a WARNING line before the verdict.
"""
import argparse
import contextlib
import json
import sys
from pathlib import Path

from crypto.manifest import payload_bits
from verify.verify_release import verify_release

DEFAULTS = {"ecc": "none", "n_bits": None, "layer": "features.6.0.weight", "mode": "mean"}  # None = signed payload_bits
EXIT = {"VERIFIED": 0, "REJECTED": 1, "DAMAGED": 2}


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
                 ecc=None, n_bits=None, layer=None, mode=None, allow_short=False, align=True):
    """Return (ok, checks, settings). checks = list of (name, passed, detail).
    allow_short=True accepts n_bits < signed payload_bits (legacy models); settings["warning"] then says so.
    align=True (default) retries with the carrier's input channels re-aligned (Phase 6b permutation defence).
    ok is True only for an exact match. settings["verdict"] is "DAMAGED" when exact verification failed but the
    signed codeword is still statistically present (settings["evidence"]); otherwise use VERIFIED / REJECTED."""
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
        bad = [k for k, t in model.state_dict().items() if t.is_floating_point() and not bool(torch.isfinite(t).all())]
        if not add("weights are finite numbers", not bad, "NaN or inf in %s" % ", ".join(bad[:3]) if bad else ""):
            return False, checks, settings
    except Exception as e:
        add("model loads at signed width", False, "%s: %s" % (type(e).__name__, e))
        return False, checks, settings

    # 3. watermark: extract + decode
    try:
        from embedding.ecc import get_code
        from embedding.keys import load_key
        from embedding.projection import ProjectionWatermark, get_weight

        signed_bits = int(manifest["watermark"]["payload_bits"])
        if settings["n_bits"] is None:
            settings["n_bits"] = signed_bits
        n_req = int(settings["n_bits"])
        if not 1 <= n_req <= signed_bits or (n_req < signed_bits and not allow_short):
            add("embedded payload covers the whole signed payload", False,
                "settings say %d bits, the signed manifest has %d (--allow-short is for legacy models only)"
                % (n_req, signed_bits))
            return False, checks, settings
        if n_req < signed_bits:
            settings["warning"] = ("only %d of %d signed payload bits checked (--allow-short), weaker proof"
                                   % (n_req, signed_bits))
        code = get_code(settings["ecc"], n_req)
        weight = get_weight(model, settings["layer"])
        wm = ProjectionWatermark(load_key(wm_key_path), settings["layer"], code.n_bits, settings["mode"], weight.shape)
        _, raw_logits = wm.extract(model)
        expected = payload_bits(manifest, n_req)          # the SIGNED manifest, never payload.hex
        codeword = code.encode(expected)

        def exact(dec):
            return dec["ok"] and dec["bits"] == expected

        logits, d, note = raw_logits, code.decode(raw_logits), ""
        if not exact(d) and align and settings["mode"] == "mean" and n_req == signed_bits:
            # Phase 6b: undo function-preserving channel permutation and/or scaling. Only an EXACT match counts, only
            # for the full signed payload, and only when the code is long enough (embedding/align.py: undo_is_safe).
            from embedding.align import candidate_readouts
            from embedding.projection import carrier_vector

            X = wm.matrix().astype("float64")
            v = carrier_vector(weight.detach(), "mean").double().numpy()
            for label, moved, vv in candidate_readouts(X, v, codeword, weight.shape):
                if label == "raw":
                    continue
                z = (X @ vv).tolist()
                d2 = code.decode(z)
                if exact(d2):
                    logits, d = z, d2
                    note = ", after undoing channel %s%s" % (label, " (%d of %d channels moved)" % (moved, weight.shape[1]) if moved else "")
                    settings["realigned"] = label
                    break
        margin = min(abs(z) for z in logits)
        if not add("watermark read (ecc %s, %d values)" % (settings["ecc"], code.n_bits), d["ok"],
                   "min margin %.2f, corrected %d, erasures %d%s" % (margin, d["corrected"], d["erasures"], note)
                   if d["ok"] else "decoder failed; min margin %.2f" % margin):
            _evidence(settings, raw_logits, codeword, n_req == signed_bits)
            return False, checks, settings
    except Exception as e:
        add("watermark extracted", False, "%s: %s" % (type(e).__name__, e))
        return False, checks, settings

    # 4. payload: compare with the SIGNED manifest
    if len(d["bits"]) != len(expected):              # zip() below would silently compare only the overlap
        add("extracted payload length", False, "%d bits read, %d expected" % (len(d["bits"]), len(expected)))
        return False, checks, settings
    wrong = sum(int(a != b) for a, b in zip(d["bits"], expected))
    if not add("extracted payload == SHA-256(signed manifest)", wrong == 0,
               "%d bits match" % len(expected) if wrong == 0 else "%d of %d bits differ" % (wrong, len(expected))):
        _evidence(settings, raw_logits, codeword, n_req == signed_bits)
    return all(c[1] for c in checks), checks, settings


def _evidence(settings, raw_logits, codeword, full_payload):
    """Exact verification failed after the signature and model checks passed. Is the signed codeword still there?

    Agreement is counted in the model's OWN channel order (no re-alignment: searching orders would inflate it), so for
    a model that never carried this codeword it is Binomial(n, 1/2) and the printed chance is exact. Above the
    2^-64 line the verdict is DAMAGED: not a proof of the exact payload, but statistical proof the mark was there."""
    from embedding.align import EVIDENCE_LOG2_P, agreement, evidence_threshold, log2_tail

    n = len(codeword)
    if not full_payload or log2_tail(n, n) > EVIDENCE_LOG2_P:   # legacy short payloads cannot reach 2^-64
        return
    k, need = agreement(raw_logits, codeword), evidence_threshold(n)
    settings["evidence"] = {"agree": k, "of": n, "need": need, "log2_chance": round(log2_tail(n, k), 1)}
    if k >= need:
        settings["verdict"] = "DAMAGED"


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
    ap.add_argument("--allow-short", action="store_true",
                    help="accept legacy models that embed fewer bits than the manifest signs (weaker proof)")
    ap.add_argument("--json", action="store_true", help="print one JSON object instead of the text report")
    ap.add_argument("--no-align", action="store_true", help="do not undo channel permutations (Phase 6 behaviour, for ablations)")
    args = ap.parse_args()

    # with --json, stdout must hold only the JSON: anything printed while verifying (liboqs prints a banner) goes to stderr
    with contextlib.redirect_stdout(sys.stderr if args.json else sys.stdout):
        ok, checks, s = verify_model(args.model, args.public_key, args.wm_key, args.release_dir,
                                     args.ecc, args.n_bits, args.layer, args.mode, allow_short=args.allow_short,
                                     align=not args.no_align)
    verdict = "VERIFIED" if ok else s.get("verdict", "REJECTED")
    code = EXIT[verdict]
    if args.json:
        print(json.dumps({"verdict": verdict, "model": str(args.model), "settings": s,
                          "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in checks]}, indent=2))
        sys.exit(code)
    print("watermark settings (%s): ecc %s | n_bits %s | layer %s | mode %s"
          % (s["source"], s["ecc"], s["n_bits"], s["layer"], s["mode"]))
    for name, passed, detail in checks:
        print("%s  %s%s" % ("PASS" if passed else "FAIL", name, "  (" + detail + ")" if detail else ""))
    if s.get("warning"):
        print("WARNING  " + s["warning"])              # before the verdict: attacks/measure.py reads the last line
    e = s.get("evidence")
    if e:
        print("EVIDENCE  %d of %d code values agree with the signed codeword (need %d; chance for an unmarked model 2^%s)"
              % (e["agree"], e["of"], e["need"], e["log2_chance"]))
    print(verdict)
    sys.exit(code)


if __name__ == "__main__":
    main()

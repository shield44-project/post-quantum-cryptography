"""Attack lab: apply ONE attack, at a strength you pick, to a signed model, then verify the result.

    python -m pqctl.actions.attack_lab --attack noise_all --strength 0.1
    python -m pqctl.actions.attack_lab --attack prune_global --strength 0.5 --accuracy
    python -m pqctl.actions.attack_lab --attack permute_in --accuracy

The attacks are the Phase 6 ones (attacks/make_attacked.py: apply_attack), so results match the attack suite.
The attacked copy is saved in .pqctl/lab/<name>/ (never in runs/) with the clean model's final.json next to it,
then checked by the real verifier (verify.verify_model) and read by the X-ray for the bit picture.
"""
import argparse
import json
import shutil
import time
from pathlib import Path

from pqctl.actions import emit, r, run_main

# id -> (Phase 6 family, how the strength maps to params, label, unit, needs training data)
ATTACKS = {
    "noise_all":     ("noise", lambda s: {"sigma": s, "scope": "all"}, "Random noise on every weight", "× weight spread", False),
    "noise_carrier": ("noise", lambda s: {"sigma": s, "scope": "carrier"}, "Random noise on the watermark layer only", "× weight spread", False),
    "prune_global":  ("prune_global", lambda s: {"sparsity": s, "scope": "global"}, "Delete the smallest weights (whole model)", "share deleted", False),
    "prune_layer":   ("prune_layer", lambda s: {"sparsity": s, "scope": "layer"}, "Delete the smallest weights (each layer)", "share deleted", False),
    "quantize":      ("quantize", lambda s: {"kind": "per_tensor", "bits": int(s)}, "Compress every weight to fewer bits", "bits", False),
    "quantize_pc":   ("quantize", lambda s: {"kind": "per_channel", "bits": int(s)}, "Compress per channel to fewer bits", "bits", False),
    "half":          ("quantize", lambda s: {"kind": "half"}, "Round-trip through 16-bit floats", "", False),
    "rescale":       ("rescale", lambda s: {"max_scale": s, "scope": "all"}, "Rescale channels (same answers)", "max factor", False),
    "permute_out":   ("permute", lambda s: {"which": "out_carrier"}, "Shuffle the watermark layer's outputs", "", False),
    "permute_in":    ("permute", lambda s: {"which": "in_carrier"}, "Shuffle the channels feeding the watermark layer", "", False),
    "permute_all":   ("permute", lambda s: {"which": "all"}, "Shuffle channels in every layer", "", False),
    "finetune":      ("finetune", lambda s: {"epochs": max(1, int(s)), "lr": 0.01, "frac": 0.2}, "Retrain on 20% of the data", "epochs", True),
    "overwrite":     ("overwrite", lambda s: {"n_bits": 128, "lam": 20.0, "epochs": max(1, int(s)), "lr": 0.01, "frac": 0.2},
                      "Write an attacker's own 128-bit watermark over it", "epochs", True),
}

# id -> (lowest, highest) strength that makes sense; attacks not listed ignore the strength
LIMITS = {"noise_all": (0, 10), "noise_carrier": (0, 10), "prune_global": (0, 0.999), "prune_layer": (0, 0.999),
          "quantize": (2, 16), "quantize_pc": (2, 16), "rescale": (1, 1000), "finetune": (1, 50), "overwrite": (1, 50)}


def check_strength(attack, s):
    lo, hi = LIMITS.get(attack, (float("-inf"), float("inf")))
    if not lo <= s <= hi:
        msg = "strength %g is out of range for %s: use %g to %g" % (s, attack, lo, hi)
        emit({"error": msg})                  # so the dashboard shows the reason
        raise SystemExit(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="runs/wm_v1/lam20_n256_rs32/seed0/model.pt")
    ap.add_argument("--attack", choices=sorted(ATTACKS), required=True)
    ap.add_argument("--strength", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--accuracy", action="store_true", help="also measure test accuracy (needs CIFAR-10, ~20-60 s on CPU)")
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--out-root", default=".pqctl/lab")
    args = ap.parse_args()

    from attacks.common import device, evaluate, load_model, save_model, seed_everything, test_loader
    from attacks.make_attacked import apply_attack
    from verify.verify_model import resolve_settings, verify_model

    family, to_params, label, unit, needs_train = ATTACKS[args.attack]
    check_strength(args.attack, args.strength)
    params = to_params(args.strength)
    src = Path(args.model)
    final_src = src.parent / "final.json"
    if not final_src.exists():
        raise SystemExit("this model has no final.json next to it, so it is not a watermarked model; pick a signed model")
    settings, _ = resolve_settings(str(src))
    fin = json.loads(final_src.read_text())
    width = int(fin.get("width", 32))
    dev = device()

    name = "%s_%s_%s" % (args.attack, ("%g" % args.strength).replace(".", "p"), time.strftime("%H%M%S"))
    out_dir = Path(args.out_root) / name
    print("attack    : %s (%s)  params %s" % (label, args.attack, params))
    print("model     : %s  (clean accuracy %s)" % (src, fin.get("final_test_acc")))
    t0 = time.time()
    seed_everything(args.seed)
    clean = load_model(str(src), width)
    attacked, extra = apply_attack({"family": family, "params": params}, clean, args.seed, settings["layer"], dev, args.data_root)
    save_model(attacked, str(out_dir / "model.pt"))
    shutil.copy(final_src, out_dir / "final.json")
    print("saved     : %s  (%.1f s)" % (out_dir / "model.pt", time.time() - t0))

    acc_clean, acc_after = fin.get("final_test_acc"), None
    if args.accuracy:
        print("accuracy  : measuring on the 10,000 test images ...", flush=True)
        loader = test_loader(args.data_root)
        acc_after = evaluate(attacked, loader, dev)
        print("accuracy  : %.4f after the attack (clean %.4f, drop %.1f points)"
              % (acc_after, acc_clean, 100 * (acc_clean - acc_after)) if acc_clean else "accuracy  : %.4f" % acc_after)

    ok, checks, s = verify_model(str(out_dir / "model.pt"), "keys/public_key.bin", "keys/watermark_key.bin", "release")
    for cname, passed, detail in checks:
        print("%s  %s%s" % ("PASS" if passed else "FAIL", cname, "  (" + detail + ")" if detail else ""))
    print("VERIFIED" if ok else "REJECTED")

    # bit picture, against the clean model's raw bits
    from embedding.ecc import get_code
    from embedding.extract import load_smallcnn
    from embedding.keys import load_key
    from embedding.projection import ProjectionWatermark, get_weight
    code = get_code(settings["ecc"], int(settings["n_bits"] or 256))
    key = load_key("keys/watermark_key.bin")

    def read(path):
        m = load_smallcnn(path, width)
        wm = ProjectionWatermark(key, settings["layer"], code.n_bits, settings["mode"], get_weight(m, settings["layer"]).shape)
        return wm.extract(m)

    clean_bits, clean_logits = read(str(src))
    bits, logits = read(str(out_dir / "model.pt"))
    flipped = [int(a != b) for a, b in zip(bits, clean_bits)]
    d = code.decode(logits)
    print("bits      : %d of %d code values flipped vs the clean model (%.1f%%)" % (sum(flipped), code.n_bits, 100.0 * sum(flipped) / code.n_bits))
    emit({"attack": args.attack, "label": label, "family": family, "params": params, "strength": args.strength, "unit": unit,
          "model": str(src), "lab_model": str(out_dir / "model.pt"), "verdict": "VERIFIED" if ok else "REJECTED",
          "checks": [[c[0], bool(c[1]), c[2]] for c in checks], "acc_clean": acc_clean, "acc_after": acc_after,
          "flipped": flipped, "n_flipped": sum(flipped), "n_code": code.n_bits, "logits": [r(z) for z in logits],
          "clean_logits": [r(z) for z in clean_logits], "margin": r(min(abs(z) for z in logits)),
          "clean_margin": r(min(abs(z) for z in clean_logits)), "corrected": d.get("corrected", 0), "decoded_ok": bool(d["ok"]),
          "extra": {k: (r(v, 4) if isinstance(v, float) else v) for k, v in extra.items()}, "seconds": r(time.time() - t0, 1)})
    return 0


if __name__ == "__main__":
    run_main(main)

"""Phase 4 'done when' check (runs LOCALLY on CPU): does the full payload survive light weight noise?

    python -m experiments.phase4_noise_test --model runs/wm_v1/lam5_n256_rs32/seed0/model.pt
    python -m experiments.phase4_noise_test --model ... --data-root data      # also measure test accuracy

Settings (ecc, n_bits, layer, mode, width) come from the final.json next to the model unless given.
For every noise level, `--trials` noisy copies are made (noise on every conv / linear weight,
scaled to each tensor's own std), the watermark is extracted and ECC-decoded.
"no-ECC errors" = errors in the first n_bits raw bits, where every code keeps the payload,
i.e. what Phase 3 style reading would give on the same noisy model.
Writes noise_test.json next to the model.
"""
import argparse
import json
import statistics as st
from pathlib import Path

import torch

from attacks.noise import add_gaussian_noise
from embedding.ecc import get_code
from embedding.extract import load_smallcnn
from embedding.keys import load_key, load_payload_bits
from embedding.projection import ProjectionWatermark, get_weight

DEFAULTS = {"ecc": "none", "n_bits": 32, "layer": "features.6.0.weight", "mode": "mean", "width": 32}


def fill_settings(args):
    """Missing CLI settings are taken from final.json, then from DEFAULTS. Returns where they came from."""
    f = Path(args.model).parent / "final.json"
    run = json.loads(f.read_text()) if f.exists() else {}
    for k, default in DEFAULTS.items():
        if getattr(args, k) is None:
            setattr(args, k, run.get(k, default))
    return str(f) if f.exists() else "defaults"


@torch.no_grad()
def test_accuracy(model, data_root):
    import torchvision
    import torchvision.transforms as T
    from torch.utils.data import DataLoader

    from training.data import CIFAR_MEAN, CIFAR_STD

    tf = T.Compose([T.ToTensor(), T.Normalize(CIFAR_MEAN, CIFAR_STD)])
    test = torchvision.datasets.CIFAR10(data_root, train=False, download=False, transform=tf)
    model.eval()
    correct = sum((model(x).argmax(1) == y).sum().item() for x, y in DataLoader(test, batch_size=1000))
    return correct / len(test)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--payload", default="release/payload.hex")
    ap.add_argument("--ecc", default=None)
    ap.add_argument("--n-bits", dest="n_bits", type=int, default=None)
    ap.add_argument("--layer", default=None)
    ap.add_argument("--mode", default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--levels", type=float, nargs="+", default=[0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 3, 4, 5])
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--light", type=float, default=0.05, help="largest noise level that counts as 'light'")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--data-root", default=None, help="CIFAR-10 folder; if given, test accuracy is measured too")
    ap.add_argument("--out", default=None, help="default: noise_test.json next to the model")
    args = ap.parse_args()
    source = fill_settings(args)

    key = load_key(args.key)
    payload = load_payload_bits(args.payload, args.n_bits)
    code = get_code(args.ecc, args.n_bits)
    codeword = code.encode(payload)
    model = load_smallcnn(args.model, args.width)
    wm = ProjectionWatermark(key, args.layer, code.n_bits, args.mode, get_weight(model, args.layer).shape)
    print("settings from %s: ecc %s | payload %d bits -> %d embedded | layer %s | mode %s | %d trials per level"
          % (source, args.ecc, args.n_bits, code.n_bits, args.layer, args.mode, args.trials))

    def errors(a, b):
        return sum(int(x != y) for x, y in zip(a, b))

    rows = []
    print("\nnoise | raw errors /%-4d min/mean/max | no-ECC errors /%-3d mean | decoded OK | mean min|logit| | test acc"
          % (code.n_bits, args.n_bits))
    for level in args.levels:
        g = torch.Generator().manual_seed(args.seed)
        raw, plain, margins, recovered = [], [], [], 0
        for _ in range(args.trials):
            got, logits = wm.extract(add_gaussian_noise(model, level, generator=g))
            raw.append(errors(got, codeword))
            plain.append(errors(got[: args.n_bits], payload))
            margins.append(min(abs(z) for z in logits))
            d = code.decode(logits)
            recovered += int(d["ok"] and d["bits"] == payload)
        acc = None
        if args.data_root:
            acc = test_accuracy(add_gaussian_noise(model, level, generator=torch.Generator().manual_seed(args.seed)),
                                args.data_root)
        rows.append({"level": level, "raw_errors": raw, "no_ecc_errors": plain, "recovered": recovered,
                     "trials": args.trials, "mean_min_abs_logit": st.mean(margins), "test_acc": acc})
        print("%4g%% | %5d / %6.1f / %-5d          | %6.1f                  | %3d/%-3d    | %8.2f        | %s"
              % (100 * level, min(raw), st.mean(raw), max(raw), st.mean(plain), recovered, args.trials,
                 st.mean(margins), "%.4f" % acc if acc is not None else "-"))

    light = [r for r in rows if r["level"] <= args.light]
    broken = [r["level"] for r in rows if r["recovered"] < r["trials"]]
    passed = bool(light) and all(r["recovered"] == r["trials"] for r in light)
    verdict = "PASSED" if passed else "NOT YET" if light else "NOT TESTED (no level <= --light)"
    print("\nfirst level with a failed trial: %s" % ("%g%%" % (100 * broken[0]) if broken else "none"))
    print("DONE-WHEN (noise <= %g%% -> 0 errors after decoding, every trial): %s" % (100 * args.light, verdict))

    out = Path(args.out) if args.out else Path(args.model).parent / "noise_test.json"
    out.write_text(json.dumps({"model": str(args.model), "ecc": args.ecc, "n_bits": args.n_bits,
                               "codeword_bits": code.n_bits, "layer": args.layer, "mode": args.mode,
                               "seed": args.seed, "light": args.light, "passed": passed, "rows": rows}, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()

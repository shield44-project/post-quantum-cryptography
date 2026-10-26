"""Phase 3 runner (COLAB): trains every (lambda, seed) pair, then compares to the baseline.

    python -m experiments.run_phase3 --lams 0.1 1 5 --seeds 0 1 2 --epochs 30 --n-bits 32

Skips runs that are already finished. Writes runs/wm_v0/summary.json and prints a table.
Accuracy differences are PAIRED: watermarked seed N minus baseline seed N.
"""
import argparse
import json
import os
import statistics as st
import subprocess
import sys
from pathlib import Path

KNOWN_BASELINE_W32 = {0: 0.8612, 1: 0.8532, 2: 0.8378}   # from skills.md Phase 1 results


def baseline_acc(baseline_dir, seed, width):
    p = Path(baseline_dir) / ("seed%d" % seed) / "final.json"
    if p.exists():
        d = json.loads(p.read_text())
        for k, v in d.items():                      # first numeric field with 'acc' in its name
            if "acc" in k.lower() and isinstance(v, (int, float)):
                return float(v)
    return KNOWN_BASELINE_W32.get(seed) if width == 32 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lams", type=float, nargs="+", default=[1.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--n-bits", type=int, default=32)
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--layer", default="features.6.0.weight")
    ap.add_argument("--mode", default="mean")
    ap.add_argument("--out-root", default="runs/wm_v0")
    ap.add_argument("--baseline-dir", default="runs/baseline")
    args = ap.parse_args()

    for lam in args.lams:
        for seed in args.seeds:
            cmd = [sys.executable, "-m", "training.train_watermarked", "--seed", str(seed),
                   "--epochs", str(args.epochs), "--lam", str(lam), "--n-bits", str(args.n_bits),
                   "--width", str(args.width), "--layer", args.layer, "--mode", args.mode,
                   "--out-root", args.out_root]
            print(">>>", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True, env=dict(os.environ, PYTHONUNBUFFERED="1"))

    summary = {}
    print("\n lam | seed | wm acc  | base acc | diff    | bit errors")
    for lam in args.lams:
        rows = []
        for seed in args.seeds:
            f = json.loads((Path(args.out_root) / ("lam%g_n%d" % (lam, args.n_bits)) / ("seed%d" % seed) / "final.json").read_text())
            b = baseline_acc(args.baseline_dir, seed, args.width)
            diff = None if b is None else f["final_test_acc"] - b
            rows.append({"seed": seed, "wm_acc": f["final_test_acc"], "base_acc": b, "diff": diff, "bit_errors": f["bit_errors"]})
            print(" %-4g| %-5d| %.4f  | %s | %s | %d" % (lam, seed, f["final_test_acc"],
                  "%.4f" % b if b is not None else "  n/a ", "%+.4f" % diff if diff is not None else "  n/a ", f["bit_errors"]))
        diffs = [r["diff"] for r in rows if r["diff"] is not None]
        summary["lam%g" % lam] = {
            "rows": rows,
            "mean_wm_acc": st.mean(r["wm_acc"] for r in rows),
            "mean_paired_diff": st.mean(diffs) if diffs else None,
            "std_paired_diff": st.stdev(diffs) if len(diffs) > 1 else None,
            "total_bit_errors": sum(r["bit_errors"] for r in rows),
        }
    (Path(args.out_root) / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\nwrote", Path(args.out_root) / "summary.json")


if __name__ == "__main__":
    main()

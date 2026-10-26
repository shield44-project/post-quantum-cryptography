"""Phase 4 runner (COLAB): trains every (ecc, layer, lambda, seed) combination, then compares to the baseline.

    # Stage A, tuning on seed 0 (6 runs, about 1 hour on a T4). lambda 0.1 is left out on purpose:
    # 512 bits need a stronger push than 32 bits (see docs/phase_commands.md, P4.2 simulation)
    python -m experiments.run_phase4 --eccs rs32 --layers features.6.0.weight features.4.0.weight --lams 1 5 20 --seeds 0
    # Stage B, the chosen layer + lambda on all seeds, with rep2 for comparison
    python -m experiments.run_phase4 --eccs rs32 rep2 --layers <best layer> --lams <best lam> --seeds 0 1 2

Skips runs that are already finished. Merges into runs/wm_v1/summary.json (earlier stages are kept)
and prints a table. Accuracy differences are PAIRED: watermarked seed N minus baseline seed N.
"""
import argparse
import json
import os
import statistics as st
import subprocess
import sys
from pathlib import Path

from experiments.run_phase3 import baseline_acc
from training.train_watermarked import run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eccs", nargs="+", default=["rs32"])
    ap.add_argument("--layers", nargs="+", default=["features.6.0.weight"])
    ap.add_argument("--lams", type=float, nargs="+", default=[5.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--n-bits", type=int, default=256)
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--mode", default="mean")
    ap.add_argument("--out-root", default="runs/wm_v1")
    ap.add_argument("--baseline-dir", default="runs/baseline")
    args = ap.parse_args()

    configs = [(e, l, lam) for e in args.eccs for l in args.layers for lam in args.lams]
    for ecc, layer, lam in configs:
        for seed in args.seeds:
            cmd = [sys.executable, "-m", "training.train_watermarked", "--seed", str(seed),
                   "--epochs", str(args.epochs), "--lam", str(lam), "--n-bits", str(args.n_bits),
                   "--ecc", ecc, "--width", str(args.width), "--layer", layer, "--mode", args.mode,
                   "--out-root", args.out_root]
            print(">>>", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True, env=dict(os.environ, PYTHONUNBUFFERED="1"))

    summary_path = Path(args.out_root) / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    print("\n ecc  | layer        | lam  | seed | wm acc | base acc | diff    | raw errors | decoded | min|logit|")
    for ecc, layer, lam in configs:
        rows = []
        for seed in args.seeds:
            f = json.loads((run_dir(args.out_root, lam, args.n_bits, ecc, layer, seed) / "final.json").read_text())
            b = baseline_acc(args.baseline_dir, seed, args.width)
            diff = None if b is None else f["final_test_acc"] - b
            rows.append({"seed": seed, "wm_acc": f["final_test_acc"], "base_acc": b, "diff": diff,
                         "raw_bit_errors": f["bit_errors"], "decoded_errors": f["decoded_errors"],
                         "min_abs_logit": f["min_abs_logit"]})
            print(" %-5s| %-13s| %-5g| %-5d| %.4f | %s | %s | %4d/%-5d | %3d/%-3d | %.2f" % (
                ecc, layer.replace(".weight", ""), lam, seed, f["final_test_acc"],
                "%.4f" % b if b is not None else "  n/a ", "%+.4f" % diff if diff is not None else "  n/a  ",
                f["bit_errors"], f["codeword_bits"], f["decoded_errors"], args.n_bits, f["min_abs_logit"]))
        diffs = [r["diff"] for r in rows if r["diff"] is not None]
        summary["%s/%s/lam%g" % (ecc, layer.replace(".weight", ""), lam)] = {
            "n_bits": args.n_bits,
            "rows": rows,
            "mean_wm_acc": st.mean(r["wm_acc"] for r in rows),
            "mean_paired_diff": st.mean(diffs) if diffs else None,
            "std_paired_diff": st.stdev(diffs) if len(diffs) > 1 else None,
            "total_raw_bit_errors": sum(r["raw_bit_errors"] for r in rows),
            "total_decoded_errors": sum(r["decoded_errors"] for r in rows),
            "min_abs_logit": min(r["min_abs_logit"] for r in rows),
        }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    total = sum(summary["%s/%s/lam%g" % (e, l.replace(".weight", ""), lam)]["total_decoded_errors"]
                for e, l, lam in configs)
    print("\nTOTAL DECODED ERRORS (this invocation): %d" % total)
    print("wrote", summary_path)


if __name__ == "__main__":
    main()

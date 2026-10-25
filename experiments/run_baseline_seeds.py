import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--out-dir", type=str, default="runs/baseline")
    args = parser.parse_args()

    for seed in args.seeds:
        final = Path(args.out_dir) / f"seed{seed}" / "final.json"
        if final.exists():
            print(f"seed {seed}: already done, skipping")
            continue
        subprocess.run(
            [sys.executable, "-m", "training.train_baseline",
             "--seed", str(seed), "--epochs", str(args.epochs),
             "--width", str(args.width), "--out-dir", args.out_dir],
            check=True,
        )

    accs = []
    for seed in args.seeds:
        with open(Path(args.out_dir) / f"seed{seed}" / "final.json") as f:
            accs.append(json.load(f)["test_acc"])

    mean = statistics.mean(accs)
    std = statistics.stdev(accs) if len(accs) > 1 else 0.0
    for seed, acc in zip(args.seeds, accs):
        print(f"seed {seed}: {acc:.4f}")
    print(f"BASELINE: {mean:.4f} +/- {std:.4f} over {len(accs)} seeds")

    summary = {"seeds": args.seeds, "accuracies": accs, "mean": mean, "std": std}
    with open(Path(args.out_dir) / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()

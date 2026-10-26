"""Phase 6 'done when': ONE command that runs every attack stage and writes the results table.

    python -m experiments.run_all_attacks                 # cheap attacks + control + evaluate + summarize
    python -m experiments.run_all_attacks --with-train    # also the training attacks (slow on CPU; use Colab if you can)

If you made the training attacks on Colab, unzip them into runs/attacks first and run without --with-train:
finished attacked models are skipped, evaluation picks everything up.
"""
import argparse
import subprocess
import sys


def run(*args):
    cmd = [sys.executable, "-m"] + list(args)
    print("\n>>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-train", action="store_true")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--useful-drop", type=float, default=0.05)
    args = ap.parse_args()
    seeds = [str(s) for s in args.seeds]

    run("attacks.make_attacked", "--cost", "cheap", "--seeds", *seeds)
    run("attacks.make_attacked", "--source", "baseline", "--seeds", *seeds, "--ids", "none", "prune_global_0.5",
        "noise_all_s0.1", "quant_pt_8")
    if args.with_train:
        run("attacks.make_attacked", "--cost", "train", "--seeds", *seeds)
    run("attacks.evaluate_attacked", "--jobs", str(args.jobs))
    run("attacks.summarize", "--useful-drop", str(args.useful_drop))


if __name__ == "__main__":
    main()

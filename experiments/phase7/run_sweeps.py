"""Phase 7, task P7.5: every training run the evaluation still needs (COLAB, T4 GPU; ~8.5 min per run, 23 runs ~3.3 h).

    python -m experiments.phase7.run_sweeps --dry-run          # list what is missing, train nothing
    python -m experiments.phase7.run_sweeps                    # train everything missing, most important first
    python -m experiments.phase7.run_sweeps --only seeds lambda

Finished runs are skipped (training/train_watermarked.py checks final.json), so a Colab session that times out can
simply be restarted. Before anything is trained the watermark key's fingerprint is checked against the one every
existing model was made with: a model trained with the wrong key file (it happened once, see skills.md 10d) is useless.

Groups, in priority order (a partial session still gives the most useful results first):
  seeds    baseline seeds 3, 4 and the chosen design (rs32, lambda 20) seeds 3, 4 -> 5 paired seeds
  ecc_off  no error correction at the full 256 bits, lambda 20, seeds 0-2           -> ECC on/off ablation
  lambda   lambda 1 and 5 on seeds 1, 2 (seed 0 exists) and lambda 10, 40 on seeds 0-2 -> lambda sweep
  payload  64 bits (rs8) and 128 bits (rs16) at rate 1/2, lambda 20, seeds 0-2     -> payload size vs accuracy
Afterwards: python -m experiments.phase7.collect_runs && python -m experiments.phase7.make_plots
(the payload and ECC plots appear once those runs exist).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from embedding.keys import key_fingerprint, load_key
from training.train_watermarked import DEFAULT_LAYER, run_dir

EXPECTED_FINGERPRINT = "81b57c4b28884f01"            # keys/watermark_key.bin used for every model in runs/wm_v1
OUT_ROOT = "runs/wm_v1"


def plan():
    """[(group, description, argv)] of every run, in priority order."""
    runs = []

    def wm(group, lam, n_bits, ecc, seed):
        runs.append((group, "%s lam %g, %d bits, seed %d" % (ecc, lam, n_bits, seed),
                     ["-m", "training.train_watermarked", "--seed", str(seed), "--epochs", "30", "--lam", "%g" % lam,
                      "--n-bits", str(n_bits), "--ecc", ecc, "--out-root", OUT_ROOT],
                     run_dir(OUT_ROOT, lam, n_bits, ecc, DEFAULT_LAYER, seed) / "final.json"))

    for s in (3, 4):
        runs.append(("seeds", "baseline seed %d" % s,
                     ["-m", "training.train_baseline", "--seed", str(s), "--epochs", "30", "--out-dir", "runs/baseline"],
                     Path("runs/baseline/seed%d/final.json" % s)))
    for s in (3, 4):
        wm("seeds", 20, 256, "rs32", s)
    for s in (0, 1, 2):
        wm("ecc_off", 20, 256, "none", s)
    for lam, seeds in ((1, (1, 2)), (5, (1, 2)), (10, (0, 1, 2)), (40, (0, 1, 2))):
        for s in seeds:
            wm("lambda", lam, 256, "rs32", s)
    for n_bits, ecc in ((64, "rs8"), (128, "rs16")):
        for s in (0, 1, 2):
            wm("payload", 20, n_bits, ecc, s)
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", choices=["seeds", "ecc_off", "lambda", "payload"], default=None)
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    todo = [r for r in plan() if args.only is None or r[0] in args.only]
    missing = [r for r in todo if not r[3].exists()]
    print("P7.5: %d runs planned, %d already done, %d to train (~%.1f h on a T4)"
          % (len(todo), len(todo) - len(missing), len(missing), len(missing) * 8.5 / 60))
    for group, desc, _, final in todo:
        print("  %-8s %-34s %s" % (group, desc, "done" if final.exists() else "TODO"))
    if args.dry_run or not missing:
        return

    fp = key_fingerprint(load_key(args.key))
    if fp != EXPECTED_FINGERPRINT:
        sys.exit("STOP: %s has fingerprint %s, the existing models expect %s. Upload the right keys/watermark_key.bin."
                 % (args.key, fp, EXPECTED_FINGERPRINT))
    print("watermark key fingerprint %s: OK" % fp)
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    for i, (group, desc, argv, final) in enumerate(missing, 1):
        print("\n>>> [%d/%d] %s: %s" % (i, len(missing), group, desc), flush=True)
        subprocess.run([sys.executable] + argv, check=True, env=env)
    print("\nall P7.5 runs done. Next: python -m experiments.phase7.collect_runs && python -m experiments.phase7.make_plots")


if __name__ == "__main__":
    main()

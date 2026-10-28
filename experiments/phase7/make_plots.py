"""Phase 7, task P7.1: plots and tables from existing results (no training, no liboqs).

    python -m experiments.phase7.make_plots
    python -m experiments.phase7.make_plots --runs results/phase7/wm_runs.csv --attacks results/phase6/attack_results.csv

Needs  results/phase7/wm_runs.csv            (python -m experiments.phase7.collect_runs)
       results/phase6/attack_results.csv     (Phase 6; only for the ECC-under-attack figure)
Writes results/phase7/plots/*.png and results/phase7/ecc_under_attack.csv. A missing input skips only its own figure.
Defaults describe the chosen design: layer features.6.0.weight, 256-bit payload, rs32, lam 20.
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LAYER = "features.6.0.weight"


def _agg(df, by, col):
    g = df.groupby(by)[col].agg(["mean", "std", "count"]).reset_index()
    g["std"] = g["std"].fillna(0.0)
    return g


def lambda_plot(runs, outdir, ecc="rs32", n_bits=256, layer=LAYER):
    d = runs[(runs.ecc == ecc) & (runs.n_bits == n_bits) & (runs.layer == layer)]
    if d["lam"].nunique() < 2:
        print("skip lambda plot: need at least 2 lambda values for %s n%d (have %d)" % (ecc, n_bits, d["lam"].nunique()))
        return
    d = d.assign(diff_pts=100 * d["acc_diff"])
    a, m = _agg(d.dropna(subset=["diff_pts"]), "lam", "diff_pts"), _agg(d, "lam", "min_margin")
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].errorbar(a["lam"], a["mean"], yerr=a["std"], marker="o", capsize=3)
    ax[0].axhline(0, color="grey", lw=0.8)
    for _, r in a.iterrows():
        ax[0].annotate("n=%d" % r["count"], (r["lam"], r["mean"]), textcoords="offset points", xytext=(4, 6), fontsize=7)
    ax[0].set(xlabel="lambda", ylabel="accuracy change vs baseline (points, paired)", title="Utility cost")
    ax[1].errorbar(m["lam"], m["mean"], yerr=m["std"], marker="o", color="#c0392b", capsize=3)
    ax[1].set(xlabel="lambda", ylabel="min |logit| (margin)", title="How safely the weakest bit is stored")
    for x in ax:
        x.set_xscale("symlog", linthresh=0.5)
    fig.suptitle("lambda sweep: %s, %d-bit payload, layer %s" % (ecc, n_bits, layer.replace(".weight", "")), fontsize=10)
    fig.tight_layout()
    fig.savefig(outdir / "lambda_tradeoff.png", dpi=170)
    plt.close(fig)


def ecc_plot(runs, outdir, lam=20.0, n_bits=256, layer=LAYER):
    d = runs[(runs.lam == lam) & (runs.n_bits == n_bits) & (runs.layer == layer)].dropna(subset=["acc_diff"])
    if d["ecc"].nunique() < 2:
        print("skip ECC plot: need at least 2 codes at lam %g (have %s)" % (lam, sorted(d["ecc"].unique())))
        return
    d = d.assign(diff_pts=100 * d["acc_diff"])
    g = _agg(d, "ecc", "diff_pts")
    cw = d.groupby("ecc")["codeword_bits"].first()
    dec = d.groupby("ecc")["decoded_errors"].sum()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(g["ecc"], g["mean"], yerr=g["std"], capsize=4, color="#4c78a8")
    ax.axhline(0, color="grey", lw=0.8)
    for i, r in g.iterrows():
        ax.text(i, r["mean"] - r["std"] - 0.25, "%d bits\n%d decoded errors" % (cw[r["ecc"]], dec[r["ecc"]]),
                ha="center", va="top", fontsize=7)
    ax.set(ylabel="accuracy change vs baseline (points)", title="Error-correcting code comparison (lam %g, %d-bit payload)" % (lam, n_bits))
    fig.tight_layout()
    fig.savefig(outdir / "ecc_comparison.png", dpi=170)
    plt.close(fig)


def payload_plot(runs, outdir, lam=20.0, layer=LAYER):
    """Only Reed-Solomon runs at rate 1/2 (codeword = 2 x payload) so that payload size is the only thing that changes."""
    d = runs[(runs.lam == lam) & (runs.layer == layer) & runs.ecc.str.startswith("rs")
             & (runs.codeword_bits == 2 * runs.n_bits)].dropna(subset=["acc_diff"])
    if d["n_bits"].nunique() < 2:
        print("skip payload plot: need at least 2 payload sizes (have %s)" % sorted(d["n_bits"].unique()))
        return
    d = d.assign(diff_pts=100 * d["acc_diff"])
    g = _agg(d, "n_bits", "diff_pts")
    fig, ax = plt.subplots(figsize=(5.5, 4))
    ax.errorbar(g["n_bits"], g["mean"], yerr=g["std"], marker="o", capsize=3)
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_xscale("log", base=2)
    ax.set_xticks(g["n_bits"])
    ax.set_xticklabels(g["n_bits"].astype(int))
    ax.set(xlabel="payload bits (rate-1/2 Reed-Solomon)", ylabel="accuracy change vs baseline (points)",
           title="Payload size vs accuracy (lam %g)" % lam)
    fig.tight_layout()
    fig.savefig(outdir / "payload_vs_accuracy.png", dpi=170)
    plt.close(fig)


def ecc_under_attack(attacks_csv, outdir, useful_drop=0.05):
    """Which attacks flipped raw codeword values, and did ECC repair them? (uses Phase 6 data, watermarked models only)"""
    df = pd.read_csv(attacks_csv)
    df = df[df["source"] == "wm"].copy()
    df["verified"] = (df["verdict"] == "VERIFIED").astype(int)
    for c in ("flip_rate", "corrected", "acc_drop"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["useful"] = df["acc_drop"] <= useful_drop
    # a run was "rescued" if raw errors existed (flip_rate > 0) but the decoded payload still matched
    df["rescued"] = ((df["flip_rate"] > 0) & (df["verified"] == 1)).astype(int)
    g = df.groupby("attack_id", sort=False).agg(
        family=("family", "first"), runs=("verified", "size"), verified_rate=("verified", "mean"),
        mean_flip=("flip_rate", "mean"), mean_corrected=("corrected", "mean"),
        rescued_runs=("rescued", "sum"), mean_drop=("acc_drop", "mean"), useful_rate=("useful", "mean"),
    ).reset_index()
    t = g[(g["mean_flip"] > 0) | (g["rescued_runs"] > 0)].sort_values("mean_flip")
    t.to_csv(outdir.parent / "ecc_under_attack.csv", index=False)
    if t.empty:
        print("no attack produced raw bit flips; nothing to plot")
        return t
    fig, ax = plt.subplots(figsize=(max(6, 0.55 * len(t) + 3), 4.2))
    colors = ["#4c9f70" if v >= 0.999 else ("#e0a030" if v > 0 else "#c0392b") for v in t["verified_rate"]]
    ax.bar(range(len(t)), 100 * t["mean_flip"], color=colors)
    ax.set_xticks(range(len(t)))
    ax.set_xticklabels(["%s\n(acc %+.0f pts)" % (a, -100 * d_) for a, d_ in zip(t["attack_id"], t["mean_drop"])],
                       rotation=60, ha="right", fontsize=7)
    ax.set(ylabel="raw codeword values flipped (%)", title="Attacks that flipped raw bits (green = ECC still verified, red = not)")
    fig.tight_layout()
    fig.savefig(outdir / "ecc_under_attack.png", dpi=170)
    plt.close(fig)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="results/phase7/wm_runs.csv")
    ap.add_argument("--attacks", default="results/phase6/attack_results.csv")
    ap.add_argument("--out", default="results/phase7/plots")
    ap.add_argument("--lam", type=float, default=20.0, help="lambda used for the ECC and payload plots")
    args = ap.parse_args()
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    if Path(args.runs).exists():
        runs = pd.read_csv(args.runs)
        lambda_plot(runs, outdir)
        ecc_plot(runs, outdir, lam=args.lam)
        payload_plot(runs, outdir, lam=args.lam)
    else:
        print("skip run plots: %s not found (run experiments.phase7.collect_runs first)" % args.runs)
    if Path(args.attacks).exists():
        t = ecc_under_attack(Path(args.attacks), outdir)
        if t is not None and len(t):
            pd.set_option("display.width", 200, "display.max_columns", 30)
            print(t.round(4).to_string(index=False))
    else:
        print("skip ECC-under-attack: %s not found" % args.attacks)
    print("plots in", outdir)


if __name__ == "__main__":
    main()

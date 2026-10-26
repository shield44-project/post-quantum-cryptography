"""Stage C: turn results/phase6/attack_results.csv into tables, plots and a Markdown report.

    python -m attacks.summarize --useful-drop 0.05

Key idea: a removal attack only counts as a SUCCESS if the watermark is gone (verdict not VERIFIED) AND the model is
still useful (accuracy within --useful-drop of the clean model). Destroying the model to kill the mark proves nothing.
"""
import argparse
from pathlib import Path

import pandas as pd

FUNCTION_PRESERVING = ("permute", "rescale")


def load(csv):
    df = pd.read_csv(csv)
    df["verified"] = (df["verdict"] == "VERIFIED").astype(int)
    for c in ("flip_rate", "min_margin", "corrected", "erasures"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def add_success(df, useful_drop):
    df = df.copy()
    df["useful"] = df["acc_drop"] <= useful_drop
    df["removal_success"] = ((df["verified"] == 0) & df["useful"]).astype(int)
    return df


def per_attack(df):
    order = df.drop_duplicates("attack_id")[["attack_id", "family"]]
    g = df.groupby(["attack_id"], sort=False).agg(
        runs=("verified", "size"),
        verified_rate=("verified", "mean"),
        removal_success=("removal_success", "mean"),
        mean_acc=("attacked_acc", "mean"),
        mean_drop=("acc_drop", "mean"),
        mean_flip=("flip_rate", "mean"),
        mean_margin=("min_margin", "mean"),
        mean_corrected=("corrected", "mean"),
    ).reset_index()
    return order.merge(g, on="attack_id")


def to_md(table, floatfmt=None):
    cols = list(table.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in table.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append("n/a" if pd.isna(v) else ("%.4f" % v if c in ("mean_acc", "mean_drop") else "%.3g" % v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def plots(table, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    outdir.mkdir(parents=True, exist_ok=True)
    for fam, sub in table.groupby("family", sort=False):
        if fam == "control" or len(sub) < 1:
            continue
        fig, ax = plt.subplots(figsize=(max(5, 0.9 * len(sub) + 2), 3.6))
        x = range(len(sub))
        ax.bar(x, sub["verified_rate"], color="#4c9f70", alpha=0.7, label="watermark verified (rate)")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("verified rate")
        ax.set_xticks(list(x))
        ax.set_xticklabels(sub["attack_id"], rotation=45, ha="right", fontsize=8)
        ax2 = ax.twinx()
        ax2.plot(list(x), sub["mean_acc"], "o-", color="#c0392b", label="test accuracy")
        ax2.set_ylabel("test accuracy")
        ax.set_title(fam)
        fig.legend(loc="lower left", fontsize=7)
        fig.tight_layout()
        fig.savefig(outdir / ("%s.png" % fam), dpi=140)
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="results/phase6/attack_results.csv")
    ap.add_argument("--out", default="docs/phase6_results.md")
    ap.add_argument("--plots", default="results/phase6/plots")
    ap.add_argument("--useful-drop", type=float, default=0.05)
    args = ap.parse_args()

    df = add_success(load(args.csv), args.useful_drop)
    wm, base = df[df["source"] == "wm"], df[df["source"] == "baseline"]
    table = per_attack(wm)
    md = ["# Phase 6 results", "",
          "Models: %d attacked watermarked checkpoints (seeds %s). A removal counts only if the verifier does not say VERIFIED "
          "and test accuracy stays within %.0f points of the clean model." % (len(wm), sorted(wm["seed"].unique().tolist()), 100 * args.useful_drop), "",
          "## Per attack", "", to_md(table), ""]

    succ = table[table["removal_success"] > 0]
    md += ["## Successful removals (watermark gone, model still useful)", ""]
    md += [to_md(succ[["attack_id", "family", "runs", "removal_success", "mean_drop", "mean_margin"]])] if len(succ) else ["None. Every attack either left the watermark verified or destroyed the model."]
    md += [""]

    broken = table[(table["verified_rate"] < 1.0)]
    md += ["## Attacks that broke verification in at least one run", ""]
    md += [to_md(broken[["attack_id", "family", "verified_rate", "mean_drop", "mean_flip", "mean_margin", "mean_corrected"]])] if len(broken) else ["None."]
    md += [""]

    fp = wm[wm["family"].isin(FUNCTION_PRESERVING)]
    bad = per_attack(fp)
    bad = bad[bad["mean_drop"].abs() > 0.005] if len(bad) else bad
    md += ["## Sanity check: function-preserving attacks should not change accuracy", ""]
    md += [to_md(bad[["attack_id", "mean_drop"]]) + "\n\nThese changed accuracy by more than 0.5 points, so they are not exactly function preserving; check the attack code."] if len(bad) else ["OK: permute and rescale attacks changed accuracy by less than 0.5 points."]
    md += [""]

    if len(base):
        md += ["## Control: attacks on the UNMARKED baseline models", "",
               "False-accept rate (verifier says VERIFIED on a model that never had the watermark): **%.3f** over %d checkpoints." % (base["verified"].mean(), len(base)), ""]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(md))
    plots(table, Path(args.plots))
    table.to_csv(Path(args.csv).with_name("attack_summary.csv"), index=False)
    print("\n".join(md))
    print("\nwrote", args.out, "and plots in", args.plots)


if __name__ == "__main__":
    main()

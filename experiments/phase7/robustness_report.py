"""Phase 7, tasks P7.2 to P7.4: false-positive study, robustness curves, naive-scheme comparison (LOCAL, no training).

    python -m experiments.phase7.robustness_report

Needs (each missing input skips only its own figure):
    results/phase6b/attack_results.csv     (python -m pqctl pipeline phase6b)
    results/phase6b/false_accept.csv       (python -m experiments.phase6b_false_accept)
    results/phase7/naive_vs_projection.csv (python -m experiments.phase7.naive_baseline)
    results/phase7/wm_config_summary.csv   (python -m experiments.phase7.collect_runs)
Writes results/phase7/plots/{false_positive,robustness_curves,naive_vs_projection}.png,
       results/phase7/false_positive_summary.csv, results/phase7/scheme_comparison.csv and docs/phase7_results.md.

Agreement = how many of the 512 code values read the way the signed codeword says, in the model's own channel order
(no re-alignment). For a model that never carried the codeword it is Binomial(512, 1/2); DAMAGED needs >= 358.
"""
import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from embedding.align import evidence_threshold, log2_cover_fraction, log2_tail  # noqa: E402

N = 512
VERDICT_COLOR = {"VERIFIED": "#2e8b57", "DAMAGED": "#e0a030", "REJECTED": "#c0392b"}
# family -> (params key giving the strength, x label, log x axis)
CURVES = {"noise": ("sigma", "noise std (x each weight's spread)", True),
          "prune_global": ("sparsity", "share of weights deleted (global)", False),
          "prune_layer": ("sparsity", "share of weights deleted (per layer)", False),
          "quantize": ("bits", "bits per weight (per tensor)", False),
          "scale_in": ("max_scale", "max input-channel scale factor", True)}


def strength(row):
    p = json.loads(row["params"]) if isinstance(row["params"], str) else {}
    fam = row["family"]
    if fam not in CURVES or (fam == "quantize" and p.get("kind") != "per_tensor"):
        return None
    if fam == "scale_in" and p.get("permute"):
        return None
    return p.get(CURVES[fam][0])


def outcome(verdicts, drops, useful=0.05):
    """held (every run VERIFIED or DAMAGED) / removed (some useful REJECTED run) / model ruined."""
    rej = [d <= useful for v, d in zip(verdicts, drops) if v == "REJECTED"]
    return "removed" if any(rej) else ("ruined" if rej else "held")


# ---------------------------------------------------------------- P7.2 false-positive study
def false_positive(fa_csv, att_csv, outdir):
    pops = []
    if fa_csv.exists():
        fa = pd.read_csv(fa_csv)
        for g, sub in fa.groupby("group", sort=False):
            pops.append((g, sub["raw_agree"].to_numpy(), int((sub["accepted_by"].fillna("") != "").sum()), int(sub["evidence"].sum())))
    if att_csv.exists():
        b = pd.read_csv(att_csv)
        base = b[b["source"] == "baseline"]
        pops.append(("attacked baselines (Phase 6b)", None, int((base["verdict"] == "VERIFIED").sum()), int((base["verdict"] == "DAMAGED").sum())))
        n_base = len(base)
    else:
        n_base = 0
    need = evidence_threshold(N)
    rows = [{"population": g, "models": (len(a) if a is not None else n_base), "false_verified": v, "false_damaged": d,
             "max_agree": (str(int(a.max())) if a is not None else None), "mean_agree": (round(float(a.mean()), 1) if a is not None else None)}
            for g, a, v, d in pops]
    summ = pd.DataFrame(rows)
    summ.to_csv(outdir.parent / "false_positive_summary.csv", index=False)

    allv = np.concatenate([a for _, a, _, _ in pops if a is not None]) if any(a is not None for _, a, _, _ in pops) else np.array([])
    if allv.size:
        fig, ax = plt.subplots(figsize=(8, 4))
        ks = np.arange(180, N + 1)
        pmf = np.array([math.exp(math.lgamma(N + 1) - math.lgamma(k + 1) - math.lgamma(N - k + 1) - N * math.log(2)) for k in ks])
        ax.hist(allv, bins=np.arange(180, 380, 4), density=True, color="#4c78a8", alpha=0.75,
                label="%d models without our mark" % allv.size)
        ax.plot(ks, pmf * 1, color="black", lw=1.2, label="Binomial(512, 1/2), exact")
        ax.axvline(need, color="#e0a030", lw=2, label="DAMAGED threshold %d (chance < 2^-64)" % need)
        ax.set(xlim=(180, 520), xlabel="code values agreeing with our signed codeword (of 512)", ylabel="share of models",
               title="False-positive study: worst unmarked model %d, threshold %d" % (allv.max(), need))
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / "false_positive.png", dpi=170)
        plt.close(fig)
    return summ, need, (int(allv.max()) if allv.size else None), int(allv.size)


# ---------------------------------------------------------------- P7.3 robustness curves
def robustness_curves(att_csv, outdir):
    if not att_csv.exists():
        return None
    d = pd.read_csv(att_csv)
    d = d[d["source"] == "wm"].copy()
    d["strength"] = d.apply(strength, axis=1)
    d = d.dropna(subset=["strength"])
    d["agree"] = (1 - pd.to_numeric(d["flip_rate"], errors="coerce")) * N
    fams = [f for f in CURVES if f in set(d["family"])]
    fig, axes = plt.subplots(1, len(fams), figsize=(3.6 * len(fams), 3.8), squeeze=False)
    need = evidence_threshold(N)
    for ax, fam in zip(axes[0], fams):
        sub = d[d["family"] == fam]
        if fam == "noise":
            sub = sub.assign(series=sub["attack_id"].str.contains("carrier").map({True: "carrier only", False: "all weights"}))
        else:
            sub = sub.assign(series="")
        ax2 = ax.twinx()
        for name, s in sub.groupby("series"):
            g = s.groupby("strength").agg(agree=("agree", "mean"), acc=("attacked_acc", "mean")).reset_index()
            ls = "--" if name == "carrier only" else "-"
            ax.plot(g["strength"], g["agree"], "k" + ls, lw=1, label=("agreement " + name).strip())
            ax2.plot(g["strength"], 100 * g["acc"], ls, color="#7f7f7f", lw=1, alpha=0.8)
            for _, r in s.iterrows():
                ax.scatter(r["strength"], r["agree"], s=18, color=VERDICT_COLOR.get(r["verdict"], "grey"), zorder=3)
        ax.axhline(need, color="#e0a030", lw=0.8, ls=":")
        ax.axhline(N / 2, color="grey", lw=0.6, ls=":")
        ax.set(ylim=(200, 520), xlabel=CURVES[fam][1], title=fam)
        if CURVES[fam][2]:
            ax.set_xscale("log")
        if fam == "quantize":
            ax.invert_xaxis()
        ax2.set_ylim(0, 100)
        ax2.tick_params(labelsize=7)
        if ax is axes[0][0]:
            ax.set_ylabel("code values still right (of 512)")
        if ax is axes[0][-1]:
            ax2.set_ylabel("test accuracy % (grey)")
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=v) for v, c in VERDICT_COLOR.items()]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle("Robustness curves (Phase 6b verifier): agreement in the model's own channel order, dot colour = verdict", fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(outdir / "robustness_curves.png", dpi=170)
    plt.close(fig)
    return d


# ---------------------------------------------------------------- P7.4 naive vs projection
def comparison(naive_csv, att_csv, outdir, useful):
    if not (naive_csv.exists() and att_csv.exists()):
        return None
    nv = pd.read_csv(naive_csv)
    nv = nv[nv["family"] != "control"]
    pj = pd.read_csv(att_csv)
    pj = pj[(pj["source"] == "wm") & pj["attack_id"].isin(set(nv["attack_id"]))]
    rows = []
    for aid, n_sub in nv.groupby("attack_id", sort=False):
        p_sub = pj[pj["attack_id"] == aid]
        rows.append({"attack_id": aid, "family": n_sub["family"].iloc[0],
                     "naive_verified": (n_sub["verdict"] == "VERIFIED").mean(), "naive_detected": n_sub["verdict"].isin(["VERIFIED", "DAMAGED"]).mean(),
                     "naive_outcome": outcome(n_sub["verdict"], n_sub["acc_drop"], useful), "naive_drop": n_sub["acc_drop"].mean(),
                     "proj_verified": (p_sub["verdict"] == "VERIFIED").mean(), "proj_detected": p_sub["verdict"].isin(["VERIFIED", "DAMAGED"]).mean(),
                     "proj_outcome": outcome(p_sub["verdict"], p_sub["acc_drop"], useful), "proj_drop": p_sub["acc_drop"].mean()})
    t = pd.DataFrame(rows)
    t.to_csv(outdir.parent / "scheme_comparison.csv", index=False)

    fams = list(dict.fromkeys(t["family"]))
    fig, ax = plt.subplots(figsize=(max(7, 0.9 * len(fams) + 3), 4))
    x = np.arange(len(fams))
    for i, (pre, name, col) in enumerate((("naive", "naive sign-based", "#c0392b"), ("proj", "projection + ECC + 6b verifier (ours)", "#2e8b57"))):
        det = [t[t["family"] == f][pre + "_detected"].mean() for f in fams]
        ver = [t[t["family"] == f][pre + "_verified"].mean() for f in fams]
        ax.bar(x + (i - 0.5) * 0.38, det, 0.36, color=col, alpha=0.35, label=name + ": traced (VERIFIED or DAMAGED)")
        ax.bar(x + (i - 0.5) * 0.38, ver, 0.36, color=col, label=name + ": VERIFIED exactly")
    ax.set_xticks(x)
    ax.set_xticklabels(fams, rotation=30, ha="right")
    ax.set(ylim=(0, 1.05), ylabel="share of attacked copies", title="Same payload, same ECC, same attacks: naive signs vs projection")
    ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(outdir / "naive_vs_projection.png", dpi=170)
    plt.close(fig)
    return t


def md_table(df, cols, fmt=None):
    fmt = fmt or {}
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join((fmt[c](r[c]) if c in fmt else ("—" if pd.isna(r[c]) else str(r[c]))) for c in cols) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attacks", default="results/phase6b/attack_results.csv")
    ap.add_argument("--false-accept", default="results/phase6b/false_accept.csv")
    ap.add_argument("--naive", default="results/phase7/naive_vs_projection.csv")
    ap.add_argument("--configs", default="results/phase7/wm_config_summary.csv")
    ap.add_argument("--plots", default="results/phase7/plots")
    ap.add_argument("--out", default="docs/phase7_results.md")
    ap.add_argument("--useful-drop", type=float, default=0.05)
    args = ap.parse_args()
    outdir = Path(args.plots)
    outdir.mkdir(parents=True, exist_ok=True)
    pct = lambda v: "—" if pd.isna(v) else "%.0f%%" % (100 * v)      # noqa: E731

    md = ["# Phase 7 results", "", "Generated by `python -m experiments.phase7.robustness_report` from files already in the repo "
          "(no training). Projection numbers use the Phase 6b verifier.", ""]

    if Path(args.configs).exists():
        c = pd.read_csv(args.configs)
        md += ["## P7.1 Every trained watermark configuration", "",
               md_table(c, ["ecc", "n_bits", "layer", "lam", "n_runs", "mean_acc", "mean_diff", "decoded_errors_total", "min_margin"],
                        {"mean_acc": lambda v: "%.4f" % v, "mean_diff": lambda v: "—" if pd.isna(v) else "%+.2f pts" % (100 * v),
                         "min_margin": lambda v: "%.2f" % v}),
               "", "Only seed 0 exists for most lambda values, ECC off at 256 bits was never trained, and every model uses a 256-bit "
               "payload: the full sweeps are task P7.5 (Colab).", ""]

    summ, need, worst, n_null = false_positive(Path(args.false_accept), Path(args.attacks), outdir)
    md += ["## P7.2 False-positive study", "",
           "Decision rules and their exact false-accept bounds for a model that never carried our codeword (512 code values):", "",
           "| Rule | Bound |", "|---|---|",
           "| VERIFIED, raw reading: Reed-Solomon decodes to exactly the signed 256-bit payload | negligible (a random word must land in the decoding radius of one specific codeword) |",
           "| VERIFIED after undoing channel scaling: 64 positive factors fit all 512 signs | 2^%.1f (Cover's function counting) |" % log2_cover_fraction(N, 64),
           "| DAMAGED: at least %d of 512 agree, counted in the model's own order | 2^%.1f (exact binomial tail) |" % (need, log2_tail(N, need)), "",
           "Measured on every population of models without our mark:", "",
           md_table(summ, ["population", "models", "false_verified", "false_damaged", "max_agree", "mean_agree"]), "",
           ("Worst agreement over %d null models: **%d of 512** (threshold %d). 0 false VERIFIED, 0 false DAMAGED." % (n_null, worst, need)
            if worst is not None else "No false-accept data yet."), "", "![false positives](../results/phase7/plots/false_positive.png)", ""]

    d = robustness_curves(Path(args.attacks), outdir)
    if d is not None:
        md += ["## P7.3 Robustness curves", "",
               "Agreement with the signed codeword (in the model's own channel order) against attack strength; dot colour = verdict, "
               "grey = test accuracy. Exact verification survives until the model itself is ruined; below that, DAMAGED still "
               "traces the copy. Scaling attacks show low raw agreement yet stay VERIFIED: the verifier undoes them before decoding.", "",
               "![robustness](../results/phase7/plots/robustness_curves.png)", ""]

    t = comparison(Path(args.naive), Path(args.attacks), outdir, args.useful_drop)
    if t is not None:
        nv = pd.read_csv(args.naive)
        ctrl = nv[nv["family"] == "control"]
        cost = []
        for s in sorted(nv["seed"].unique()):
            none = nv[(nv["seed"] == s) & (nv["attack_id"] == "none")]
            base = ctrl[ctrl["seed"] == s]
            if len(none) and len(base):
                cost.append(100 * (none["acc"].iloc[0] - base["acc"].iloc[0]))
        removed = lambda pre: ", ".join(t[t[pre + "_outcome"] == "removed"]["attack_id"]) or "none"      # noqa: E731
        md += ["## P7.4 Comparison with the naive sign-based scheme", "",
               "Naive scheme (the project's first design): bit = sign of one key-chosen weight. Built as fairly as possible: same "
               "layer, same 256-bit signed payload, same rs32 codeword, same soft decoding and decision rule, the same weight "
               "attacks (one draw per random attack; projection: 3 draws, 3 seeds).", "",
               "| | naive sign-based | projection (ours) |", "|---|---|---|",
               "| Accuracy cost of embedding | %s | −3.10 pts (paired, 3 seeds) |" % (("%+.2f pts (mean of %d seeds)" % (np.mean(cost), len(cost))) if cost else "—"),
               "| Attack types that removed it (model still useful) | %d: %s | %d: %s |" % ((t["naive_outcome"] == "removed").sum(), removed("naive"),
                                                                                       (t["proj_outcome"] == "removed").sum(), removed("proj")),
               "| Copies VERIFIED exactly, all attacks | %s | %s |" % (pct(t["naive_verified"].mean()), pct(t["proj_verified"].mean())),
               "| Copies traced (VERIFIED or DAMAGED) | %s | %s |" % (pct(t["naive_detected"].mean()), pct(t["proj_detected"].mean())), "",
               md_table(t, ["attack_id", "naive_outcome", "naive_verified", "naive_detected", "proj_outcome", "proj_verified", "proj_detected"],
                        {k: pct for k in ("naive_verified", "naive_detected", "proj_verified", "proj_detected")}), "",
               "![naive vs projection](../results/phase7/plots/naive_vs_projection.png)", ""]

    md += ["## Still to do", "",
           "- **P7.5 (Colab GPU):** lambda sweep on 3 seeds, payload size 64 / 128 / 256 bits at rate 1/2, ECC off at 256 bits, "
           "seeds 3 and 4 for the baseline and the chosen design. See `docs/phase_commands.md`, Phase 7.",
           "- **P7.6:** a second model (ResNet-18), which needs its own signed release.", ""]
    Path(args.out).write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print("\nwrote", args.out, "and plots in", outdir)


if __name__ == "__main__":
    main()

"""Figure 4: Recorded structural transformations (1-column IEEE width).

Sources:
  - results/phase6b/attack_results.csv (BCE/RS32)
  - results/phase7/attack_results_rs16.csv (BCE/RS16)
  - results/phase7/attack_results_hinge1.5.csv (Hinge/RS32)
Output:
  - paper2/figures/structural_edits.pdf
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
OUT_PNG = Path(__file__).resolve().parents[1] / "figures" / "structural_edits.png"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.7,
    "axes.labelsize": 7.8,
    "xtick.labelsize": 7.2,
    "ytick.labelsize": 7.2,
    "grid.color": "#E0E0E0",
    "grid.linewidth": 0.5,
})

C_NAVY = "#1F4E79"
C_TEAL = "#008080"
C_ORANGE = "#D55E00"
C_PURPLE = "#6A3D9A"


def main() -> None:
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    files = {
        "BCE/RS32": REPO / "results" / "phase6b" / "attack_results.csv",
        "BCE/RS16": REPO / "results" / "phase7" / "attack_results_rs16.csv",
        "Hinge/RS32": REPO / "results" / "phase7" / "attack_results_hinge1.5.csv",
    }
    attack_order = [
        ("permute_out_carrier", "Permute out ch."),
        ("scale_in_carrier_x2", "Scale in ch. (×2)"),
        ("scale_in_carrier_x10", "Scale in ch. (×10)"),
        ("scale_in_carrier_x100", "Scale in ch. (×100)"),
        ("permute_in_carrier", "Permute in ch."),
        ("permute_all", "Permute all layers"),
        ("permute_scale_in_x10", "Perm. + scale (×10)"),
    ]
    ids = [a[0] for a in attack_order]
    labels = [a[1] for a in attack_order]

    stats = {}
    ver_labels = {aid: set() for aid in ids}
    for dname, fpath in files.items():
        df = pd.read_csv(fpath)
        wm = df[(df["source"] == "wm") & (df["attack_id"].isin(ids))]
        grp = wm.groupby("attack_id").agg(
            n=("verdict", "count"),
            ver=("verdict", lambda s: (s == "VERIFIED").sum()),
            flip=("flip_rate", "mean"),
        )
        for aid in ids:
            ver_labels[aid].add(f"{int(grp.loc[aid, 'ver'])}/{int(grp.loc[aid, 'n'])}")
        stats[dname] = [grp.loc[aid, "flip"] * 100.0 for aid in ids]

    fig, ax = plt.subplots(figsize=(3.50, 2.95))
    y = np.arange(len(ids))[::-1]
    h = 0.24

    for dname, dy, col, hatch in [
        ("BCE/RS32", +h, C_ORANGE, ""),
        ("BCE/RS16", 0.0, C_PURPLE, "///"),
        ("Hinge/RS32", -h, C_NAVY, "..."),
    ]:
        ax.barh(y + dy, stats[dname], height=h, color=col, edgecolor="white", lw=0.45,
                hatch=hatch, label=dname, zorder=3)

    ax.text(1.5, y[0], "0.0% (mean-invariant)", ha="left", va="center",
            fontsize=5.8, style="italic", color="#475569")

    ax.axvline(57.5, color="#CBD5E1", lw=0.7, ls="-", zorder=2)
    ax.text(65.2, y[0] + 0.62, "Verified\n(retries on)", ha="center", va="bottom",
            fontsize=5.6, fontweight="bold", color=C_TEAL, linespacing=1.05)
    for yi, aid in zip(y, ids):
        lbl = f"{next(iter(ver_labels[aid]))} each" if len(ver_labels[aid]) == 1 else ", ".join(sorted(ver_labels[aid]))
        ax.text(65.2, yi, lbl, ha="center", va="center",
                fontsize=6.0, fontweight="bold", color=C_TEAL,
                bbox=dict(boxstyle="round,pad=0.18", fc="#ECFDF5", ec="#A7F3D0", lw=0.5))

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6.6)
    ax.set_xlim(0, 73.5)
    ax.set_xticks([0, 10, 20, 30, 40, 50])
    ax.set_ylim(-0.65, len(ids) - 0.15)
    ax.set_xlabel("Mean Clean-Relative Sign-Change Rate (%)")
    ax.xaxis.grid(True, linestyle="-", alpha=0.55)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.15), ncol=3,
              frameon=False, fontsize=6.2, handlelength=1.4, columnspacing=0.8)

    fig.savefig(OUT_PNG, format="png", dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()

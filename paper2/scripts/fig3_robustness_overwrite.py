"""Figure 3: Total suite verdicts and 512-bit overwrite tradeoff (2-column IEEE width).

Sources:
  - results/phase6b/attack_results.csv (BCE/RS32)
  - results/phase7/attack_results_rs16.csv (BCE/RS16)
  - results/phase7/attack_results_hinge1.5.csv (Hinge/RS32)
Output:
  - paper2/figures/robustness_overwrite.pdf
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[2]
OUT_PNG = Path(__file__).resolve().parents[1] / "figures" / "robustness_overwrite.png"

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

C_TEAL = "#008080"
C_AMBER = "#E69F00"
C_CRIMSON = "#B22222"


def load_data():
    files = [
        ("BCE/RS32", REPO / "results" / "phase6b" / "attack_results.csv"),
        ("BCE/RS16", REPO / "results" / "phase7" / "attack_results_rs16.csv"),
        ("Hinge/RS32", REPO / "results" / "phase7" / "attack_results_hinge1.5.csv"),
    ]
    verdict_rows = []
    overwrite_rows = []

    for design, path in files:
        df = pd.read_csv(path)
        wm = df[df["source"] == "wm"]
        vc = wm["verdict"].value_counts()
        removals = int(((wm["verdict"] == "REJECTED") & (wm["acc_drop"] <= 0.05 + 1e-12)).sum())
        verdict_rows.append({
            "design": design,
            "verified": int(vc.get("VERIFIED", 0)),
            "damaged": int(vc.get("DAMAGED", 0)),
            "rejected": int(vc.get("REJECTED", 0)),
            "successful_removals": removals,
        })

        ow = wm[wm["attack_id"] == "overwrite_512bit"].sort_values("seed")
        for _, r in ow.iterrows():
            overwrite_rows.append({
                "design": design,
                "seed": int(r["seed"]),
                "accuracy_drop_points": float(r["acc_drop"]) * 100.0,
                "verdict": str(r["verdict"]).upper(),
            })

    return pd.DataFrame(verdict_rows), pd.DataFrame(overwrite_rows)


def main() -> None:
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    vc, ow = load_data()

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(7.16, 2.75),
        gridspec_kw={"width_ratios": [1.08, 1.0], "wspace": 0.30}
    )

    # Panel (a): Horizontal stacked verdict counts (252 rows/design from 3 parents)
    designs = vc["design"].tolist()
    y_pos = np.arange(len(designs))[::-1]
    ver = vc["verified"].values
    dam = vc["damaged"].values
    rej = vc["rejected"].values
    rem = vc["successful_removals"].values

    bar_h = 0.50
    ax1.barh(y_pos, ver, height=bar_h, color=C_TEAL, edgecolor="white", lw=0.6,
             label="VERIFIED", zorder=3)
    ax1.barh(y_pos, dam, left=ver, height=bar_h, color=C_AMBER, edgecolor="white", lw=0.6,
             hatch="///", label="DAMAGED", zorder=3)
    ax1.barh(y_pos, rej, left=ver + dam, height=bar_h, color=C_CRIMSON, edgecolor="white", lw=0.6,
             hatch="xxx", label="REJECTED", zorder=3)

    for yi, v, d, r, rm in zip(y_pos, ver, dam, rej, rem):
        ax1.text(v / 2, yi, f"{v}", ha="center", va="center",
                 fontsize=7.2, fontweight="bold", color="white", zorder=5)
        txt_col = C_CRIMSON if rm > 0 else "#334155"
        ax1.text(256, yi, f"D:{d}, R:{r}\n({rm} rem.)", ha="left", va="center",
                 fontsize=6.3, fontweight="bold" if rm > 0 else "normal",
                 color=txt_col, linespacing=1.15)

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(designs, fontweight="bold")
    ax1.set_xlim(0, 316)
    ax1.set_xticks([0, 50, 100, 150, 200, 252])
    ax1.set_xlabel("Recorded Evaluations (n = 252 per design; 3 parent models)")
    ax1.set_title("(a) Suite Verdict Counts (Descriptive; Parent Reuse)", fontsize=8.0, fontweight="bold", pad=16)
    ax1.xaxis.grid(True, linestyle="-", alpha=0.55)
    ax1.set_axisbelow(True)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.45, 1.13), ncol=3,
               frameon=False, fontsize=6.4, handlelength=1.4, columnspacing=0.9)

    # Panel (b): 512-bit same-layer overwrite accuracy drop
    order = ["BCE/RS32", "BCE/RS16", "Hinge/RS32"]
    x_centers = np.arange(len(order))
    seed_offsets = {0: -0.20, 1: 0.0, 2: 0.20}

    ax2.axhspan(0, 5.0, color="#FEE2E2", alpha=0.28, zorder=1)
    ax2.axhline(5.0, color=C_CRIMSON, lw=1.05, ls=":", zorder=2)
    ax2.annotate(
        "5.0 pt removal budget",
        xy=(2.36, 5.03), xytext=(2.42, 6.05),
        ha="right", va="bottom", fontsize=6.2, fontweight="bold", color=C_CRIMSON,
        arrowprops=dict(arrowstyle="-|>", color=C_CRIMSON, lw=0.8),
        zorder=6,
    )

    for idx, dname in enumerate(order):
        sub = ow[ow["design"] == dname].sort_values("seed")
        for _, row in sub.iterrows():
            s = int(row["seed"])
            drop = float(row["accuracy_drop_points"])
            verd = str(row["verdict"])
            xp = x_centers[idx] + seed_offsets[s]
            stem_col = C_CRIMSON if verd == "REJECTED" else C_AMBER
            ax2.plot([xp, xp], [0, drop], color=stem_col, lw=0.9, alpha=0.55, zorder=2)

            if verd == "REJECTED":
                ax2.scatter([xp], [drop], s=46, marker="X", color=C_CRIMSON,
                            edgecolor="white", linewidth=0.5, zorder=5)
            else:
                ax2.scatter([xp], [drop], s=42, marker="^", color=C_AMBER,
                            edgecolor="#7C2D12", linewidth=0.55, zorder=5)

            ax2.text(xp, drop + 0.26, f"{drop:.2f}", ha="center", va="bottom",
                     fontsize=5.8, color="#1F2937", fontweight="bold" if verd == "REJECTED" else "normal")
            ax2.text(xp, 0.25, f"S{s}", ha="center", va="bottom", fontsize=5.5, color="#4B5563")

    hinge_ow = ow[ow["design"] == "Hinge/RS32"]
    hinge_rem = int(((hinge_ow["verdict"] == "REJECTED") & (hinge_ow["accuracy_drop_points"] <= 5.0)).sum())
    bce_ow = ow[ow["design"].isin(["BCE/RS32", "BCE/RS16"])]
    bce_rem = int(((bce_ow["verdict"] == "REJECTED") & (bce_ow["accuracy_drop_points"] <= 5.0)).sum())

    ax2.text(2.0, 2.05, f"{hinge_rem}/{len(hinge_ow)} successful\nremovals\n(REJECTED ≤ 5 pt)",
             ha="center", va="center", fontsize=5.8, fontweight="bold", color=C_CRIMSON,
             bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=C_CRIMSON, lw=0.65, alpha=0.92),
             zorder=6)
    ax2.text(0.50, 1.45, f"{bce_rem}/{len(bce_ow)} removals\n(all DAMAGED)",
             ha="center", va="center", fontsize=5.5, color="#92400E",
             bbox=dict(boxstyle="round,pad=0.22", fc="white", ec=C_AMBER, lw=0.65, alpha=0.95),
             zorder=6)

    ax2.set_xticks(x_centers)
    ax2.set_xticklabels(order, fontweight="bold")
    ax2.set_xlim(-0.48, 2.48)
    ax2.set_ylim(0, 7.85)
    ax2.set_ylabel("Accuracy Drop (percentage points)")
    ax2.set_xlabel("Watermark Design (Seeds S0, S1, S2)")
    ax2.set_title("(b) 512-Bit Same-Layer Overwrite Impact", fontsize=8.0, fontweight="bold", pad=16)
    ax2.yaxis.grid(True, linestyle="-", alpha=0.55)
    ax2.set_axisbelow(True)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    verdict_handles = [
        Line2D([0], [0], marker="^", color="none", mfc=C_AMBER, mec="#7C2D12", ms=6.0, label="DAMAGED"),
        Line2D([0], [0], marker="X", color="none", mfc=C_CRIMSON, mec="white", ms=6.5, label="REJECTED"),
    ]
    ax2.legend(handles=verdict_handles, loc="upper center", bbox_to_anchor=(0.5, 1.13),
               ncol=2, frameon=False, fontsize=6.4, handletextpad=0.35, columnspacing=1.0)

    fig.savefig(OUT_PNG, format="png", dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()

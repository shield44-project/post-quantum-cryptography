"""Figure 5: Negative-control raw agreement histogram (1-column IEEE width).

Source:
  - results/phase6b/false_accept.csv (724 rows; 54 attacked baselines excluded)
Output:
  - paper2/figures/negative_controls.pdf
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
OUT_PNG = Path(__file__).resolve().parents[1] / "figures" / "negative_controls.png"

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
C_AMBER = "#E69F00"
C_CRIMSON = "#B22222"


def main() -> None:
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fa = pd.read_csv(REPO / "results" / "phase6b" / "false_accept.csv")
    assert len(fa) == 724, f"Expected 724 rows, got {len(fa)}"
    obs_max = int(fa["raw_agree"].max())
    assert obs_max == 305, f"Expected max 305, got {obs_max}"

    wrong_key = fa[fa["group"] == "wrong key"]["raw_agree"].values
    rand_init = fa[fa["group"] == "random init"]["raw_agree"].values
    other_ctrl = fa[~fa["group"].isin(["wrong key", "random init"])]["raw_agree"].values

    fig, ax = plt.subplots(figsize=(3.50, 2.45))

    bins = np.arange(216, 316, 4)
    ax.hist(
        [wrong_key, rand_init, other_ctrl],
        bins=bins,
        stacked=True,
        color=[C_NAVY, C_TEAL, C_AMBER],
        edgecolor="white",
        linewidth=0.45,
        label=[f"Wrong key ({len(wrong_key)})", f"Random init ({len(rand_init)})",
               f"Base/Mallory/scr. ({len(other_ctrl)})"],
        zorder=3,
    )

    ax.axvline(256, color="#64748B", lw=0.9, ls=":", zorder=4)
    ax.annotate(
        "Null mean\n= 256",
        xy=(256.8, 113), xytext=(265, 113),
        ha="left", va="center", fontsize=5.8, color="#475569",
        arrowprops=dict(arrowstyle="-|>", color="#64748B", lw=0.7),
        zorder=5,
    )

    ax.axvline(obs_max, color=C_ORANGE, lw=1.0, ls="--", zorder=4)
    ax.annotate(
        f"Max observed\n{obs_max} / 512",
        xy=(obs_max, 18), xytext=(311, 52),
        fontsize=6.0, fontweight="bold", color=C_ORANGE,
        arrowprops=dict(arrowstyle="-|>", color=C_ORANGE, lw=0.8),
        zorder=5,
    )

    ax.axvspan(358, 382, color="#FEE2E2", alpha=0.55, zorder=1)
    ax.axvline(358, color=C_CRIMSON, lw=1.25, ls="--", zorder=4)
    ax.text(355.8, 115, "DAMAGED\ncutoff\n358 / 512", ha="right", va="top",
            fontsize=6.1, fontweight="bold", color=C_CRIMSON)

    ax.annotate(
        "", xy=(357, 8), xytext=(306, 8),
        arrowprops=dict(arrowstyle="<->", color="#475569", lw=0.75),
        zorder=5,
    )
    ax.text(331.5, 11.5, f"{358 - obs_max}-bit gap\n(0/{len(fa)} hits)", ha="center", va="bottom",
            fontsize=5.7, fontweight="bold", color="#334155")

    ax.set_xlim(212, 376)
    ax.set_ylim(0, 124)
    ax.set_xlabel("Raw RS32 Codeword Agreements (out of 512)")
    ax.set_ylabel("Control Evaluations (count)")
    ax.yaxis.grid(True, linestyle="-", alpha=0.55)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.48, 1.17), ncol=2,
              frameon=False, fontsize=5.9, handlelength=1.3, columnspacing=0.8)

    fig.savefig(OUT_PNG, format="png", dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()

"""Figure 2: Five-seed paired clean accuracy (1-column IEEE width).

Sources:
  - results/phase7/wm_runs.csv
  - runs/baseline/seed*/final.json
Output:
  - paper2/figures/paired_accuracy.pdf
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
OUT_PNG = Path(__file__).resolve().parents[1] / "figures" / "paired_accuracy.png"

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
C_ORANGE = "#D55E00"
C_PURPLE = "#6A3D9A"
C_SLATE = "#3B4252"


def load_paired_data():
    wm = pd.read_csv(REPO / "results" / "phase7" / "wm_runs.csv")
    seeds = np.arange(5)

    base = np.array([
        json.loads((REPO / f"runs/baseline/seed{s}/final.json").read_text())["test_acc"] * 100.0
        for s in seeds
    ])

    def extract_series(run_name: str) -> np.ndarray:
        sub = wm[wm["run"] == run_name].set_index("seed")["acc"] * 100.0
        return np.array([sub.get(s, np.nan) for s in seeds], dtype=float)

    bce16 = extract_series("lam20_n256_rs16")
    bce32 = extract_series("lam20_n256_rs32")
    hinge = extract_series("lam20_n256_rs32_hinge1.5")
    return seeds, base, bce16, bce32, hinge


def main() -> None:
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    seeds, base, bce16, bce32, hinge = load_paired_data()

    fig, ax = plt.subplots(figsize=(3.50, 2.80))

    # Shaded paired advantage band (Hinge/RS32 vs BCE/RS32 across all 5 seeds)
    ax.fill_between(seeds, bce32, hinge, color=C_NAVY, alpha=0.10, zorder=1)
    for s, h, b in zip(seeds, hinge, bce32):
        ax.plot([s, s], [b, h], color=C_NAVY, lw=0.85, alpha=0.55, zorder=2)

    ax.plot(seeds, base, color=C_SLATE, lw=1.15, ls="--", marker="o", ms=4.5,
            mfc="white", mec=C_SLATE, mew=1.1, label="Unmarked baseline (n=5)", zorder=4)
    ax.plot(seeds, hinge, color=C_NAVY, lw=1.35, ls="-", marker="s", ms=4.6,
            mfc=C_NAVY, mec="white", mew=0.45, label="Hinge m=1.5 / RS32 (n=5)", zorder=5)
    ax.plot(seeds, bce32, color=C_ORANGE, lw=1.35, ls="-", marker="D", ms=4.3,
            mfc=C_ORANGE, mec="white", mew=0.45, label="BCE / RS32 (n=5)", zorder=5)

    # Do NOT interpolate missing BCE/RS16 seeds 3-4
    valid16 = ~np.isnan(bce16)
    ax.plot(seeds[valid16], bce16[valid16], color=C_PURPLE, lw=1.15, ls=":", marker="^", ms=4.8,
            mfc=C_PURPLE, mec="white", mew=0.45, label="BCE / RS16 (seeds 0–2 only)", zorder=5)

    for s_miss in seeds[~valid16]:
        ax.text(s_miss, 79.45, "RS16\nn/a", ha="center", va="bottom",
                fontsize=5.6, color=C_PURPLE, style="italic", alpha=0.85)

    diffs = hinge - bce32
    x_offsets = [0.11, 0.11, 0.12, 0.11, -0.12]
    has = ["left", "left", "left", "left", "right"]
    for s, h, b, d, xo, ha in zip(seeds, hinge, bce32, diffs, x_offsets, has):
        ax.text(s + xo, (h + b) / 2, f"+{d:.2f}", ha=ha, va="center",
                fontsize=5.55, color=C_NAVY, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.82),
                zorder=6)

    mean_diff = float(np.mean(diffs))
    callout = (
        f"5-seed paired mean (seeds 0–4):\n"
        f"  Hinge − BCE/RS32 = +{mean_diff:.2f} pt\n"
        f"  Base {base.mean():.2f}% | Hinge {hinge.mean():.2f}% | BCE32 {bce32.mean():.2f}%\n"
        f"3-seed cohort (seeds 0–2):\n"
        f"  Base {base[:3].mean():.2f}% | BCE16 {bce16[:3].mean():.2f}% | BCE32 {bce32[:3].mean():.2f}%"
    )
    ax.text(0.025, 0.035, callout, transform=ax.transAxes,
            ha="left", va="bottom", fontsize=5.45, linespacing=1.22,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#CBD5E1", alpha=0.95, lw=0.65),
            zorder=6)

    ax.set_xticks(seeds)
    ax.set_xticklabels([f"Seed {s}" for s in seeds])
    ax.set_xlim(-0.35, 4.45)
    ax.set_ylim(76.2, 87.6)
    ax.set_ylabel("CIFAR-10 Test Accuracy (%)")
    ax.set_xlabel("Training Seed")
    ax.yaxis.grid(True, linestyle="-", alpha=0.6)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2,
              columnspacing=0.9, handletextpad=0.45, handlelength=1.7,
              fontsize=6.15, frameon=False)

    fig.savefig(OUT_PNG, format="png", dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()

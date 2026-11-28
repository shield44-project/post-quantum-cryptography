"""Figure 1: System workflow vector block diagram (2-column IEEE width).

Output: paper2/figures/system_workflow.pdf
"""

from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_PNG = Path(__file__).resolve().parents[1] / "figures" / "system_workflow.png"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "text.color": "#1A1A1A",
})

C_NAVY = "#1F4E79"
C_TEAL = "#008080"
C_ORANGE = "#D55E00"
C_AMBER = "#E69F00"
C_CRIMSON = "#B22222"
C_SLATE = "#3B4252"
C_BLUE_BG = "#EEF5FB"
C_PRIV_BG = "#FDF4EC"
C_OPT_BG = "#F5F5F7"


def main() -> None:
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.16, 3.85))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 54)
    ax.axis("off")

    def draw_box(x, y, w, h, title, sub="", fc="white", ec="#334155", lw=0.85,
                 title_color="#111827", sub_color="#475569", title_size=5.65, sub_size=4.75,
                 ls="-", radius=0.75, bold=True, title_y=0.67, sub_y=0.23):
        box = FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0.14,rounding_size={radius}",
            facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls, zorder=3
        )
        ax.add_patch(box)
        if sub:
            ax.text(x + w / 2, y + h * title_y, title, ha="center", va="center",
                    fontsize=title_size, fontweight="bold" if bold else "normal",
                    color=title_color, zorder=4, linespacing=1.06)
            ax.text(x + w / 2, y + h * sub_y, sub, ha="center", va="center",
                    fontsize=sub_size, color=sub_color, zorder=4, linespacing=1.06)
        else:
            ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                    fontsize=title_size, fontweight="bold" if bold else "normal",
                    color=title_color, zorder=4, linespacing=1.08)

    def arrow(x1, y1, x2, y2, color="#334155", lw=0.85, ls="-", rad=0.0):
        arr = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>,head_length=3.4,head_width=2.0",
            color=color, linewidth=lw, linestyle=ls,
            connectionstyle=f"arc3,rad={rad}", zorder=5
        )
        ax.add_patch(arr)

    # Lane A: Developer / Signed Release Creation
    ax.add_patch(FancyBboxPatch(
        (0.5, 32.4), 99.0, 20.8,
        boxstyle="round,pad=0.1,rounding_size=1.0",
        facecolor="#F8FAFC", edgecolor="#CBD5E1", linewidth=0.8, zorder=1
    ))
    ax.text(1.6, 51.8, "A. SIGNED RELEASE CREATION & WATERMARK EMBEDDING (Developer)",
            ha="left", va="center", fontsize=6.5, fontweight="bold", color=C_NAVY, zorder=4)

    # Lane B: Trusted White-Box Verification (Auditor)
    ax.add_patch(FancyBboxPatch(
        (0.5, 0.8), 76.0, 30.0,
        boxstyle="round,pad=0.1,rounding_size=1.0",
        facecolor="#FAFAFC", edgecolor="#CBD5E1", linewidth=0.8, zorder=1
    ))
    ax.text(1.6, 29.4, "B. TRUSTED WHITE-BOX VERIFICATION (Auditor)",
            ha="left", va="center", fontsize=6.5, fontweight="bold", color=C_NAVY, zorder=4)

    # Public Signature Boundary
    ax.add_patch(FancyBboxPatch(
        (1.6, 18.2), 51.8, 9.6,
        boxstyle="round,pad=0.1,rounding_size=0.8",
        facecolor=C_BLUE_BG, edgecolor=C_NAVY, linewidth=0.8, linestyle="--", zorder=2
    ))
    ax.text(2.4, 26.6, "Public Signature Boundary (Trusted Public Key)",
            ha="left", va="center", fontsize=5.35, fontweight="bold", color=C_NAVY, zorder=4)

    # Private Watermark-Key Boundary
    ax.add_patch(FancyBboxPatch(
        (1.6, 2.0), 54.4, 15.0,
        boxstyle="round,pad=0.1,rounding_size=0.8",
        facecolor=C_PRIV_BG, edgecolor=C_ORANGE, linewidth=0.8, linestyle="--", zorder=2
    ))
    ax.text(2.4, 15.8, "Private Watermark-Key Boundary (Secret K_wm + Pinned Profile)",
            ha="left", va="center", fontsize=5.35, fontweight="bold", color="#9A3412", zorder=4)

    # Lane C: Optional Dataset Comparison
    ax.add_patch(FancyBboxPatch(
        (77.7, 0.8), 21.8, 30.0,
        boxstyle="round,pad=0.1,rounding_size=1.0",
        facecolor=C_OPT_BG, edgecolor="#64748B", linewidth=0.85, linestyle=":", zorder=1
    ))
    ax.text(88.6, 29.4, "C. OPTIONAL CHECK", ha="center", va="center",
            fontsize=6.3, fontweight="bold", color="#334155", zorder=4)
    ax.text(88.6, 27.5, "(Separate from model verify)", ha="center", va="center",
            fontsize=5.0, style="italic", color="#475569", zorder=4)

    # Upper Lane Row 1
    y_u1, h_u = 43.0, 6.8
    draw_box(1.6,  y_u1, 13.0, h_u, "50k Labeled\nCIFAR-10", "Ordered split", fc="white", ec=C_SLATE)
    draw_box(16.8, y_u1, 14.2, h_u, "Deterministic\nLeaf Hashing", "SHA-256 (0x00/0x01)", fc="white", ec=C_SLATE)
    draw_box(33.2, y_u1, 11.4, h_u, "Merkle Root", "32-byte digest", fc="white", ec=C_SLATE, title_y=0.64, sub_y=0.28)
    draw_box(46.8, y_u1, 14.4, h_u, "Deterministic\nJSON Manifest", "Sorted UTF-8 (M)", fc="#EFF6FF", ec=C_NAVY)
    draw_box(63.4, y_u1, 16.0, h_u, "ML-DSA-65 Sign", "Sig 3,309 B | pk 1,952 B", fc="#DBEAFE", ec=C_NAVY, title_y=0.64, sub_y=0.28)
    draw_box(81.6, y_u1, 16.8, h_u, "Signed Release", "Manifest + Sig (external)", fc="#E0F2FE", ec=C_NAVY, title_y=0.64, sub_y=0.28)

    arrow(14.75, y_u1 + h_u / 2, 16.65, y_u1 + h_u / 2)
    arrow(31.15, y_u1 + h_u / 2, 33.05, y_u1 + h_u / 2)
    arrow(44.75, y_u1 + h_u / 2, 46.65, y_u1 + h_u / 2)
    arrow(61.35, y_u1 + h_u / 2, 63.25, y_u1 + h_u / 2)
    arrow(79.55, y_u1 + h_u / 2, 81.45, y_u1 + h_u / 2)

    # Upper Lane Row 2
    y_u2, h_u2 = 33.8, 6.6
    draw_box(30.4, y_u2, 15.6, h_u2, "SHA-256 Manifest\nDigest p", "256-bit payload", fc="#FEF3C7", ec=C_AMBER)
    draw_box(48.2, y_u2, 13.6, h_u2, "RS32 / RS16\nEncoder", "512 b / 384 b code", fc="#FEF3C7", ec=C_AMBER)
    draw_box(64.0, y_u2, 16.6, h_u2, "Keyed Projection\nTraining (K_wm)", "L_cls + λ L_wm (d=576)", fc="#FFEDD5", ec=C_ORANGE)
    draw_box(82.8, y_u2, 15.6, h_u2, "Marked SmallCNN\nCheckpoint", "features.6.0.weight", fc="#FFEDD5", ec=C_ORANGE)

    ax.plot([54.0, 54.0, 38.2], [42.85, 41.6, 41.6], color=C_NAVY, lw=0.85, zorder=4)
    arrow(38.2, 41.6, 38.2, 40.55, color=C_NAVY)
    arrow(46.15, y_u2 + h_u2 / 2, 48.05, y_u2 + h_u2 / 2, color="#9A3412")
    arrow(61.95, y_u2 + h_u2 / 2, 63.85, y_u2 + h_u2 / 2, color="#9A3412")
    arrow(80.75, y_u2 + h_u2 / 2, 82.65, y_u2 + h_u2 / 2, color="#9A3412")

    ax.text(1.7, 37.1,
            "Note: ML-DSA-65 signs\nmanifest M externally;\nonly 256-bit digest p is\nembedded in weights.",
            ha="left", va="center", fontsize=5.15, color="#475569",
            bbox=dict(boxstyle="round,pad=0.32", fc="white", ec="#CBD5E1", lw=0.6), zorder=4)

    # Lower Lane: Public Verification
    y_p, h_p = 19.3, 6.0
    draw_box(2.5,  y_p, 16.6, h_p, "Trusted pk_sig +\nSigned Manifest", "Independent key channel", fc="white", ec=C_NAVY)
    draw_box(21.3, y_p, 17.0, h_p, "Verify ML-DSA-65\nSignature", "Authenticates statement", fc="white", ec=C_NAVY)
    draw_box(40.5, y_p, 11.8, h_p, "Expected\nDigest p", "SHA-256(M)", fc="#DBEAFE", ec=C_NAVY)
    arrow(19.25, y_p + h_p / 2, 21.15, y_p + h_p / 2, color=C_NAVY)
    arrow(38.45, y_p + h_p / 2, 40.35, y_p + h_p / 2, color=C_NAVY)

    # Lower Lane: Private Watermark-Key Verification
    draw_box(2.5, 11.1, 13.4, 3.2, "Secret Key K_wm", "", fc="#FFEDD5", ec=C_ORANGE, title_size=4.95)
    draw_box(2.5,  7.2, 13.4, 3.2, "Submitted Weights", "", fc="white", ec=C_SLATE, title_size=4.65)
    draw_box(2.5,  3.3, 13.4, 3.2, "Pinned Profile", "", fc="white", ec=C_SLATE, title_size=4.95)

    draw_box(17.9, 4.2, 11.2, 9.4, "Keyed\nProjection\nExtraction", "z = X v\n(d = 576)",
             fc="white", ec=C_ORANGE, title_size=5.0, sub_size=4.55, title_y=0.68, sub_y=0.21)
    draw_box(30.9, 4.2, 11.6, 9.4, "Hard RS Decode\n+ Erasure Retry", "2..r/2 low-conf\nbytes",
             fc="white", ec=C_ORANGE, title_size=4.75, sub_size=4.55, title_y=0.68, sub_y=0.22)
    draw_box(44.3, 4.2, 10.8, 9.4, "Optional\nAssignment &\nScale Retries", "Cover gate;\nperm. / +scale",
             fc="white", ec=C_ORANGE, title_size=4.80, sub_size=4.50, title_y=0.68, sub_y=0.20)

    for y_in in (12.7, 8.8, 4.9):
        ax.plot([16.05, 16.9], [y_in, y_in], color="#9A3412", lw=0.75, zorder=4)
    ax.plot([16.9, 16.9], [4.9, 12.7], color="#9A3412", lw=0.75, zorder=4)
    arrow(16.9, 8.8, 17.75, 8.8, color="#9A3412")
    arrow(29.25, 8.9, 30.75, 8.9, color="#9A3412")
    arrow(42.65, 8.9, 44.15, 8.9, color="#9A3412")

    # Three Separate Outcomes
    draw_box(60.2, 19.6, 15.2, 6.2, "VERIFIED", "Full 256-bit digest\nmatch (association)",
             fc="#DCFCE7", ec=C_TEAL, lw=1.0, title_color="#065F46", sub_color="#065F46",
             title_size=5.9, sub_size=4.75, title_y=0.72, sub_y=0.28)
    draw_box(60.2, 11.4, 15.2, 6.4, "DAMAGED", "No exact match; orig.\norder k ≥ 358 / 280",
             fc="#FEF3C7", ec=C_AMBER, lw=1.0, title_color="#92400E", sub_color="#92400E",
             title_size=5.9, sub_size=4.75, title_y=0.72, sub_y=0.28)
    draw_box(60.2,  3.2, 15.2, 6.2, "REJECTED", "Check failure or\nk < cutoff",
             fc="#FEE2E2", ec=C_CRIMSON, lw=1.0, title_color="#991B1B", sub_color="#991B1B",
             title_size=5.9, sub_size=4.75, title_y=0.72, sub_y=0.28)

    ax.plot([52.45, 57.9], [22.3, 22.3], color=C_NAVY, lw=0.85, zorder=4)
    ax.plot([55.25, 57.9], [8.9, 8.9], color="#9A3412", lw=0.85, zorder=4)
    ax.plot([57.9, 57.9], [6.3, 22.3], color="#334155", lw=0.85, zorder=4)
    arrow(57.9, 22.3, 60.05, 22.3, color=C_TEAL, lw=0.9)
    arrow(57.9, 14.6, 60.05, 14.6, color=C_AMBER, lw=0.9)
    arrow(57.9,  6.3, 60.05,  6.3, color=C_CRIMSON, lw=0.9)

    ax.text(56.7, 25.0, "Compare\ndigest p", ha="center", va="center",
            fontsize=4.9, fontweight="bold", color="#334155",
            bbox=dict(boxstyle="round,pad=0.20", fc="white", ec="#94A3B8", lw=0.5), zorder=5)

    # Optional Dataset Check
    draw_box(79.2, 20.0, 18.8, 5.4, "Candidate Dataset", "Ordered byte view", fc="white", ec="#64748B", ls=":", title_y=0.65, sub_y=0.27)
    draw_box(79.2, 12.2, 18.8, 5.6, "Recompute Merkle\nRoot (SHA-256)", "Same leaf/node rule", fc="white", ec="#64748B", ls=":", title_y=0.68, sub_y=0.22)
    draw_box(79.2,  4.6, 18.8, 5.4, "Compare vs. Signed\nManifest Root", "Data commitment match", fc="#F1F5F9", ec="#475569", ls=":", title_y=0.68, sub_y=0.22)

    arrow(88.6, 19.85, 88.6, 17.95, color="#475569", ls=":")
    arrow(88.6, 12.05, 88.6, 10.15, color="#475569", ls=":")

    ax.text(88.6, 2.3, "Does NOT prove training\nuse or legal ownership",
            ha="center", va="center", fontsize=4.95, style="italic", color="#64748B", zorder=4)

    fig.savefig(OUT_PNG, format="png", dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()

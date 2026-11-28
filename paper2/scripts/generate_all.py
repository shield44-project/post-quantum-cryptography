"""Run all five standalone figure scripts for paper2."""

import fig1_system_workflow
import fig2_paired_accuracy
import fig3_robustness_overwrite
import fig4_structural_edits
import fig5_negative_controls


def main() -> None:
    fig1_system_workflow.main()
    fig2_paired_accuracy.main()
    fig3_robustness_overwrite.main()
    fig4_structural_edits.main()
    fig5_negative_controls.main()
    print("All 5 paper2 figures generated in paper2/figures/.")


if __name__ == "__main__":
    main()

"""RUN THIS FIRST (LOCAL). Confirms the Phase 6 suite can drive your Phase 5 verifier.

    python -m attacks.check_compat --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt

1. verifies the clean model with verify_model
2. copies model.pt + final.json to a temporary folder and verifies again (the mechanism Phase 6 relies on)
3. tests the raw-flip probe
"""
import argparse
import shutil
import tempfile
from pathlib import Path

from attacks.measure import Probe, run_verifier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="runs/wm_v1/lam20_n256_rs32/seed0/model.pt")
    ap.add_argument("--key", default="keys/watermark_key.bin")
    args = ap.parse_args()
    model = Path(args.model)

    r1 = run_verifier(model)
    print("1) clean model        :", r1["verdict"], "| wm read", r1["wm_read"], "| payload", r1["payload_match"],
          "| margin", r1["min_margin"], "| corrected", r1["corrected"], "| erasures", r1["erasures"],
          "| values", r1["n_values"], "| settings", (r1["ecc"], r1["n_bits"], r1["layer"], r1["mode"]))
    if r1["verdict"] == "ERROR":
        print("   verifier crashed:", r1.get("error"))

    tmp = Path(tempfile.mkdtemp()) / "copy"
    tmp.mkdir()
    shutil.copy(model, tmp / "model.pt")
    shutil.copy(model.parent / "final.json", tmp / "final.json")
    r2 = run_verifier(tmp / "model.pt")
    same = (r2["verdict"], r2["min_margin"], r2["corrected"]) == (r1["verdict"], r1["min_margin"], r1["corrected"])
    print("2) copied to temp dir :", r2["verdict"], "| same result as clean:", same)

    probe = Probe.from_clean(model, r1, args.key)
    print("3) raw-flip probe     :", "ENABLED" if probe.enabled else "disabled", "-", probe.reason)
    if probe.enabled:
        print("   flip rate of the clean model against itself:", probe.flip_rate(model), "(must be 0.0)")

    ok = r1["verdict"] == "VERIFIED" and r2["verdict"] == "VERIFIED" and same
    print("\nCOMPAT CHECK:", "PASSED, you can run Phase 6" if ok else "FAILED, send me this output")


if __name__ == "__main__":
    main()

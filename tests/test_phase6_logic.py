"""No torch needed.  python -m pytest tests/test_phase6_logic.py -v"""
import sys
import tempfile
from pathlib import Path

import pandas as pd

from attacks import registry
from attacks.measure import parse_verifier_output

REAL = """liboqs-python faulthandler is disabled
watermark settings (final.json): ecc rs32 | n_bits 256 | layer features.6.0.weight | mode mean
PASS  load release files
PASS  key id matches manifest  (manifest=bae58d20d2964be6ef068a9ff17772af key=bae58d20d2964be6ef068a9ff17772af)
PASS  algorithm is ML-DSA-65
PASS  signature valid
PASS  payload.hex matches manifest
PASS  architecture is SmallCNN  (manifest says 'SmallCNN')
PASS  model loads at signed width 32
PASS  parameter count matches manifest  (model 160234, manifest 160234)
PASS  watermark read (ecc rs32, 512 values)  (min margin 2.25, corrected 0, erasures 0)
PASS  extracted payload == SHA-256(signed manifest)  (256 bits match)
VERIFIED
"""

FAILED = """watermark settings (final.json): ecc rs32 | n_bits 256 | layer features.6.0.weight | mode mean
PASS  load release files
FAIL  watermark read (ecc rs32, 512 values)  (decode failed: too many errors)
REJECTED
"""

DEGRADED = REAL.replace("min margin 2.25, corrected 0, erasures 0", "min margin 0.31, corrected 4, erasures 2")


def test_parse_real_output():
    r = parse_verifier_output(REAL)
    assert r["verdict"] == "VERIFIED"
    assert r["wm_read"] == "PASS" and r["payload_match"] == "PASS"
    assert r["min_margin"] == 2.25 and r["corrected"] == 0 and r["erasures"] == 0 and r["n_values"] == 512
    assert (r["ecc"], r["n_bits"], r["layer"], r["mode"]) == ("rs32", 256, "features.6.0.weight", "mean")


def test_parse_failure_degraded_and_garbage():
    f = parse_verifier_output(FAILED)
    assert f["verdict"] == "REJECTED" and f["wm_read"] == "FAIL" and f["payload_match"] is None
    d = parse_verifier_output(DEGRADED)
    assert d["verdict"] == "VERIFIED" and d["corrected"] == 4 and d["erasures"] == 2 and abs(d["min_margin"] - 0.31) < 1e-9
    g = parse_verifier_output("Traceback (most recent call last):\n  boom")
    assert g["verdict"] is None and g["checks"] == []


def test_registry_is_consistent():
    ids = [c["id"] for c in registry.CONFIGS]
    assert len(ids) == len(set(ids))
    assert len(registry.select(cost="cheap")) + len(registry.select(cost="train")) == len(ids)
    assert {c["family"] for c in registry.CONFIGS} >= {"noise", "prune_global", "prune_layer", "quantize", "rescale",
                                                       "permute", "finetune", "prune_ft", "overwrite"}
    assert all(c["repeats"] >= 1 for c in registry.CONFIGS)


def _fake_csv(path):
    rows = []
    for seed in (0, 1):
        for attack, fam, verdict, drop in [("prune_global_0.5", "prune_global", "VERIFIED", 0.01),
                                           ("prune_global_0.95", "prune_global", "REJECTED", 0.60),
                                           ("noise_all_s0.5", "noise", "REJECTED", 0.02),
                                           ("permute_all", "permute", "REJECTED", 0.0)]:
            rows.append({"source": "wm", "seed": seed, "attack_id": attack, "family": fam, "rep": 0, "params": "{}",
                         "clean_acc": 0.85, "attacked_acc": 0.85 - drop, "acc_drop": drop, "verdict": verdict,
                         "wm_read": "PASS", "payload_match": "PASS", "min_margin": 1.0, "corrected": 0, "erasures": 0,
                         "flip_rate": 0.1})
        rows.append({"source": "baseline", "seed": seed, "attack_id": "none", "family": "control", "rep": 0, "params": "{}",
                     "clean_acc": 0.85, "attacked_acc": 0.85, "acc_drop": 0.0, "verdict": "REJECTED", "wm_read": "FAIL",
                     "payload_match": None, "min_margin": None, "corrected": None, "erasures": None, "flip_rate": None})
    pd.DataFrame(rows).to_csv(path, index=False)


def test_summary_counts_only_useful_removals():
    from attacks.summarize import add_success, load, per_attack
    d = Path(tempfile.mkdtemp())
    _fake_csv(d / "r.csv")
    df = add_success(load(d / "r.csv"), 0.05)
    t = per_attack(df[df["source"] == "wm"]).set_index("attack_id")
    assert t.loc["prune_global_0.5", "removal_success"] == 0           # still verified
    assert t.loc["prune_global_0.95", "removal_success"] == 0          # removed, but model destroyed (drop 0.60)
    assert t.loc["noise_all_s0.5", "removal_success"] == 1             # removed AND still useful
    assert t.loc["permute_all", "removal_success"] == 1


def test_summarize_writes_report_and_plots():
    from attacks import summarize
    d = Path(tempfile.mkdtemp())
    _fake_csv(d / "r.csv")
    old = sys.argv
    sys.argv = ["summarize", "--csv", str(d / "r.csv"), "--out", str(d / "out.md"), "--plots", str(d / "plots")]
    try:
        summarize.main()
    finally:
        sys.argv = old
    text = (d / "out.md").read_text()
    assert "Successful removals" in text and "False-accept rate" in text and "noise_all_s0.5" in text
    assert (d / "plots" / "noise.png").exists()

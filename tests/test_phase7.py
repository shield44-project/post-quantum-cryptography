"""Phase 7 (P7.2-P7.5) helpers.   python -m pytest tests/test_phase7.py -v      Needs torch; no trained models."""
import secrets

import pytest

torch = pytest.importorskip("torch")

from embedding.align import evidence_threshold  # noqa: E402
from embedding.ecc import get_code  # noqa: E402
from experiments.phase7.naive_baseline import LAYER, embed, positions, read  # noqa: E402
from experiments.phase7.robustness_report import outcome, strength  # noqa: E402
from experiments.phase7.run_sweeps import plan  # noqa: E402
from training.model import SmallCNN  # noqa: E402


def test_naive_scheme_round_trip_and_null():
    torch.manual_seed(0)
    m = SmallCNN(width=32).eval()
    numel = dict(m.named_parameters())[LAYER].numel()
    key = secrets.token_bytes(32)
    pos = positions(key, 512, numel)
    assert len(set(pos.tolist())) == 512 and pos.max() < numel
    assert (positions(key, 512, numel) == pos).all()                     # deterministic from the key
    code = get_code("rs32", 256)
    payload = [int(b) for b in torch.randint(0, 2, (256,))]
    cw = code.encode(payload)
    need = evidence_threshold(512)
    assert read(m, pos, code, cw, payload, need)[0] == "REJECTED"         # unmarked: about half agree
    embed(m, pos, cw)
    verdict, k = read(m, pos, code, cw, payload, need)
    assert verdict == "VERIFIED" and k == 512


def test_sweep_plan_is_complete_and_unique():
    runs = plan()
    assert len(runs) == 23 and len({str(r[3]) for r in runs}) == 23
    groups = [r[0] for r in runs]
    assert groups == sorted(groups, key=["seeds", "ecc_off", "lambda", "payload"].index)   # priority order
    names = {r[3].parent.parent.name for r in runs}
    assert {"lam20_n64_rs8", "lam20_n128_rs16", "lam20_n256", "lam40_n256_rs32"} <= names   # ecc none: no suffix


def test_outcome_and_strength_rules():
    assert outcome(["VERIFIED", "DAMAGED"], [0.0, 0.01]) == "held"
    assert outcome(["REJECTED"], [0.02]) == "removed"                    # gone while the model is still useful
    assert outcome(["REJECTED"], [0.40]) == "ruined"
    assert strength({"family": "noise", "params": '{"sigma": 0.1, "scope": "all"}'}) == 0.1
    assert strength({"family": "quantize", "params": '{"kind": "half"}'}) is None
    assert strength({"family": "scale_in", "params": '{"max_scale": 10, "permute": true}'}) is None

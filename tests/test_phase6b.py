"""Phase 6b: permutation / scaling defence and the DAMAGED verdict.   python -m pytest tests/test_phase6b.py -v

Self-contained: a temporary ML-DSA key, signed release and a small watermarked model (rs32, full 256-bit payload).
"""
import json
import math
import secrets

import numpy as np
import pytest

from embedding.align import (agreement, align_permutation, apply_permutation, evidence_threshold, log2_tail,
                             recover_scales)

pytest.importorskip("oqs")
torch = pytest.importorskip("torch")

from attacks.weight_attacks import permute_channels, scale_carrier_inputs  # noqa: E402
from crypto.manifest import build_manifest, payload_bits  # noqa: E402
from crypto.signing import generate_keys, key_id  # noqa: E402
from embedding.ecc import get_code  # noqa: E402
from embedding.projection import ProjectionWatermark, get_weight  # noqa: E402
from experiments.phase5_make_mallory import write_release  # noqa: E402
from training.model import SmallCNN  # noqa: E402
from verify.verify_model import verify_model  # noqa: E402

LAYER = "features.6.0.weight"


def _mark(model, wm_key, bits):
    """Watermark-only optimisation of the carrier layer towards `bits` (fast stand-in for training)."""
    target = torch.tensor(bits, dtype=torch.float32)
    wm = ProjectionWatermark(wm_key, LAYER, len(bits), "mean", get_weight(model, LAYER).shape)
    opt = torch.optim.SGD([get_weight(model, LAYER)], lr=5.0)
    for _ in range(300):
        opt.zero_grad()
        wm.loss(model, target).backward()
        opt.step()


@pytest.fixture(scope="module")
def dev(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase6b")
    pk, sk = generate_keys()
    (root / "public_key.bin").write_bytes(pk)
    wm_key = secrets.token_bytes(32)
    (root / "watermark_key.bin").write_bytes(wm_key)
    torch.manual_seed(0)
    model = SmallCNN(width=32).eval()
    manifest = build_manifest("dev", key_id(pk), "00" * 32, 50000, 32, sum(p.numel() for p in model.parameters()), 256,
                              created_utc="2026-11-03T00:00:00Z")
    write_release(root / "release", manifest, sk, pk)
    code = get_code("rs32", 256)
    codeword = code.encode(payload_bits(manifest, 256))
    _mark(model, wm_key, codeword)
    with torch.no_grad():                                   # make the BatchNorm in front of the carrier non-trivial
        for m in model.modules():
            if isinstance(m, torch.nn.BatchNorm2d):
                m.weight.uniform_(0.5, 1.5)
                m.bias.normal_()
    return {"root": root, "model": model, "wm_key": wm_key, "codeword": codeword, "manifest": manifest}


def _verify(dev, model, name, **kw):
    d = dev["root"] / name
    d.mkdir(exist_ok=True)
    torch.save(model.state_dict(), d / "model.pt")
    (d / "final.json").write_text(json.dumps({"ecc": "rs32", "n_bits": 256, "layer": LAYER, "mode": "mean"}))
    ok, checks, s = verify_model(d / "model.pt", dev["root"] / "public_key.bin", dev["root"] / "watermark_key.bin",
                                 dev["root"] / "release", **kw)
    return ("VERIFIED" if ok else s.get("verdict", "REJECTED")), s


def _same_function(a, b):
    x = torch.randn(8, 3, 32, 32)
    with torch.no_grad():
        return torch.allclose(a(x), b(x), atol=1e-4, rtol=1e-3)


def test_clean_model_needs_no_undo(dev):
    verdict, s = _verify(dev, dev["model"], "clean")
    assert verdict == "VERIFIED" and "realigned" not in s


@pytest.mark.parametrize("attack", ["permute_in", "permute_all", "scale_x10", "scale_x100", "permute_scale_x10"])
def test_function_preserving_attacks_are_undone(dev, attack):
    m = dev["model"]
    if attack.startswith("permute"):
        m = permute_channels(m, "in_carrier" if attack == "permute_in" else "all", 5, LAYER)
    if "scale" in attack:
        m = scale_carrier_inputs(m, 100 if attack.endswith("x100") else 10, 6, LAYER)
    assert _same_function(m, dev["model"])                  # the attack really is free for the attacker
    assert _verify(dev, m, attack, align=False)[0] != "VERIFIED"       # Phase 6 verifier: broken
    verdict, s = _verify(dev, m, attack)
    assert verdict == "VERIFIED" and s["realigned"]          # Phase 6b verifier: undone, exact match


def test_overwrite_damage_gives_damaged_not_verified(dev):
    rng = np.random.default_rng(0)
    damaged = np.array(dev["codeword"])
    damaged[rng.choice(len(damaged), 70, replace=False)] ^= 1            # ~14% flipped, like overwrite_128bit
    m = SmallCNN(width=32).eval()
    m.load_state_dict(dev["model"].state_dict())
    _mark(m, dev["wm_key"], damaged.tolist())
    verdict, s = _verify(dev, m, "overwritten")
    assert verdict == "DAMAGED"
    assert s["evidence"]["agree"] >= s["evidence"]["need"] and s["evidence"]["log2_chance"] < -64


def test_unmarked_model_stays_rejected(dev):
    torch.manual_seed(123)
    m = scale_carrier_inputs(permute_channels(SmallCNN(width=32).eval(), "in_carrier", 1, LAYER), 10, 2, LAYER)
    verdict, s = _verify(dev, m, "unmarked")
    assert verdict == "REJECTED" and s["evidence"]["agree"] < s["evidence"]["need"]


def test_wrong_key_stays_rejected(dev):
    (dev["root"] / "wrong_key.bin").write_bytes(secrets.token_bytes(32))
    d = dev["root"] / "wk"
    d.mkdir(exist_ok=True)
    torch.save(dev["model"].state_dict(), d / "model.pt")
    (d / "final.json").write_text(json.dumps({"ecc": "rs32", "n_bits": 256, "layer": LAYER, "mode": "mean"}))
    ok, _, s = verify_model(d / "model.pt", dev["root"] / "public_key.bin", dev["root"] / "wrong_key.bin", dev["root"] / "release")
    assert not ok and s.get("verdict", "REJECTED") == "REJECTED"


# ---------------------------------------------------------------- the maths, without models

def test_binomial_tail_and_threshold():
    from scipy.stats import binom
    for n, k in ((512, 300), (512, 358), (256, 200)):
        assert abs(log2_tail(n, k) - math.log2(binom.sf(k - 1, n, 0.5))) < 1e-6
    assert evidence_threshold(512) == 358 and log2_tail(512, 512) == -512


def test_alignment_and_scales_are_exact_inverses():
    rng = np.random.default_rng(1)
    C, K, n = 64, 9, 512
    X = rng.choice([-1.0, 1.0], size=(n, C * K))
    code = rng.integers(0, 2, n)
    s = 2 * code - 1
    # a trained carrier points along X^T s (the direction the watermark loss pushes it); then the true order is the
    # unique best one, since sum_c A_c . A_pi(c) is largest for pi = identity
    v_grad = X.T @ s / n
    perm = rng.permutation(C)
    back, moved = align_permutation(X, v_grad.reshape(C, K)[perm].ravel(), code, (8, C, 3, 3))
    assert moved == C - int((perm == np.arange(C)).sum())
    assert np.array_equal(apply_permutation(v_grad.reshape(C, K)[perm].ravel(), back, (8, C, 3, 3)), v_grad)
    v = np.linalg.lstsq(X, s * 3.0, rcond=None)[0]           # a carrier that reads `code` exactly, with margin 3
    assert agreement(X @ v, code) == n
    scaled = (v.reshape(C, K) / np.exp(rng.uniform(-math.log(10), math.log(10), C))[:, None]).ravel()
    fixed, margin = recover_scales(X, scaled, code, (8, C, 3, 3))
    assert margin > 0 and agreement(X @ fixed, code) == n
    noise = rng.standard_normal(C * K)                        # a carrier that never saw `code`
    _, margin_noise = recover_scales(X, noise, code, (8, C, 3, 3))
    assert margin_noise <= 0                                  # 64 positive factors cannot fit 512 random signs


def test_search_is_refused_when_it_could_fit_anything():
    from embedding.align import candidate_readouts, log2_cover_fraction, undo_is_safe
    assert log2_cover_fraction(512, 64) < -230 and undo_is_safe(512, (128, 64, 3, 3))      # rs32: safe
    assert not undo_is_safe(32, (32, 16, 3, 3))           # legacy 32-value code, 16 channels: 16 factors fit 32 signs
    rng = np.random.default_rng(2)
    X, code = rng.choice([-1.0, 1.0], size=(32, 144)), rng.integers(0, 2, 32)
    assert [lab for lab, _, _ in candidate_readouts(X, rng.standard_normal(144), code, (32, 16, 3, 3))] == ["raw"]

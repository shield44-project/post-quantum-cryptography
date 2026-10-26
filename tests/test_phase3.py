"""Run from the project root:  python -m pytest tests/test_phase3.py -v   (expect 5 passed)"""
import numpy as np
import pytest

from embedding.keys import (bit_error_rate, false_accept_probability, hex_to_bits,
                            key_fingerprint, projection_matrix_np)

torch = pytest.importorskip("torch")
from embedding.projection import ProjectionWatermark  # noqa: E402


class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = torch.nn.Conv2d(16, 32, 3, bias=False)


KEY = b"\x01" * 32


def test_projection_matrix_deterministic_and_key_dependent():
    a = projection_matrix_np(KEY, "conv.weight", 32, 144)
    assert np.array_equal(a, projection_matrix_np(KEY, "conv.weight", 32, 144))
    assert not np.array_equal(a, projection_matrix_np(b"\x02" * 32, "conv.weight", 32, 144))
    assert set(np.unique(a)) == {-1.0, 1.0}
    assert abs(a.mean()) < 0.1


def test_embedding_reaches_zero_bit_errors():
    torch.manual_seed(0)
    m = Tiny()
    bits_list = [int(b) for b in np.random.default_rng(3).integers(0, 2, 32)]
    wm = ProjectionWatermark(KEY, "conv.weight", 32, "mean", m.conv.weight.shape)
    bits = torch.tensor(bits_list, dtype=torch.float32)
    opt = torch.optim.SGD(m.parameters(), lr=0.5)
    for _ in range(300):
        opt.zero_grad()
        wm.loss(m, bits).backward()
        opt.step()
    got, logits = wm.extract(m)
    assert got == bits_list
    assert min(abs(z) for z in logits) > 0.5


def test_wrong_key_and_unmarked_model_look_random():
    torch.manual_seed(1)
    m = Tiny()
    bits_list = [int(b) for b in np.random.default_rng(4).integers(0, 2, 64)]
    wm = ProjectionWatermark(KEY, "conv.weight", 64, "mean", m.conv.weight.shape)
    bits = torch.tensor(bits_list, dtype=torch.float32)
    opt = torch.optim.SGD(m.parameters(), lr=0.5)
    for _ in range(400):
        opt.zero_grad()
        wm.loss(m, bits).backward()
        opt.step()
    assert wm.extract(m)[0] == bits_list
    wrong = ProjectionWatermark(b"\x09" * 32, "conv.weight", 64, "mean", m.conv.weight.shape)
    assert bit_error_rate(wrong.extract(m)[0], bits_list) > 0.2            # near 0.5, not near 0
    fresh = Tiny()
    assert bit_error_rate(wm.extract(fresh)[0], bits_list) > 0.2           # unmarked model


def test_full_mode_and_capacity_guard():
    m = Tiny()
    wm = ProjectionWatermark(KEY, "conv.weight", 128, "full", m.conv.weight.shape)
    assert wm.dim == 16 * 32 * 9
    with pytest.raises(ValueError):
        ProjectionWatermark(KEY, "conv.weight", 500, "mean", m.conv.weight.shape)   # 500 > 16*9


def test_helpers():
    assert hex_to_bits("a5") == [1, 0, 1, 0, 0, 1, 0, 1]
    assert key_fingerprint(KEY) != key_fingerprint(b"\x02" * 32)
    assert abs(false_accept_probability(32, 0) - 2 ** -32) < 1e-18
    assert bit_error_rate([0, 1, 1, 0], [0, 1, 0, 0]) == 0.25

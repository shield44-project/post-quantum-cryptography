"""Run from the project root:  python -m pytest tests/test_phase4.py -v   (expect 8 passed)"""
import numpy as np
import pytest

from embedding.ecc import get_code

pytest.importorskip("reedsolo")

PAYLOAD = [int(b) for b in np.random.default_rng(0).integers(0, 2, 256)]


def _logits(codeword, size=3.0):
    """Perfect extraction: +size for bit 1, -size for bit 0."""
    return np.where(np.asarray(codeword) == 1, size, -size)


def test_roundtrip_all_codes():
    for name, n_bits in [("none", 256), ("rep2", 512), ("rep3", 768), ("rs32", 512)]:
        code = get_code(name)
        cw = code.encode(PAYLOAD)
        assert code.n_bits == len(cw) == n_bits
        r = code.decode(_logits(cw))
        assert r["ok"] and r["bits"] == PAYLOAD and r["corrected"] == 0, name
    assert get_code("rs32").encode(PAYLOAD)[:256] == PAYLOAD                  # data bytes come first


def test_repetition_soft_beats_hard():
    code = get_code("rep3")
    z = _logits(code.encode(PAYLOAD)).reshape(3, 256)
    z[1:, :10] = -0.1 * np.sign(z[1:, :10])            # copies 2 and 3 of bits 0..9: wrong, but barely
    z = z.ravel()
    assert code.decode(z, soft=False)["bits"][:10] != PAYLOAD[:10]           # majority vote is fooled
    r = code.decode(z, soft=True)
    assert r["bits"] == PAYLOAD and r["corrected"] == 20                     # confident copy 1 wins


def test_rs_corrects_up_to_limit():
    code = get_code("rs32")
    rng = np.random.default_rng(1)
    for _ in range(20):
        z = _logits(code.encode(PAYLOAD)).reshape(64, 8)
        bad = rng.choice(64, 17, replace=False)
        z[bad[:16], 0] *= -1                                                  # 16 confidently wrong bytes
        r = code.decode(z.ravel(), soft=False)
        assert r["ok"] and r["bits"] == PAYLOAD and r["corrected"] == 16
        z[bad[16], 0] *= -1                                                   # one more: 17 > 32 / 2
        assert code.decode(z.ravel(), soft=False)["bits"] != PAYLOAD


def test_rs_soft_erasures_beat_hard():
    code = get_code("rs32")
    z = _logits(code.encode(PAYLOAD)).reshape(64, 8)
    bad = np.random.default_rng(2).choice(64, 24, replace=False)
    z[bad, 3] = -0.2 * np.sign(z[bad, 3])              # 24 wrong bytes, each with one barely-wrong bit
    z = z.ravel()
    assert code.decode(z, soft=False)["bits"] != PAYLOAD                      # 24 > 16: hard decoding fails
    r = code.decode(z, soft=True)
    assert r["ok"] and r["bits"] == PAYLOAD and r["erasures"] > 0            # erasing unsure bytes fixes it


def test_noise_and_garbage_never_crash():
    code = get_code("rs32")
    rng = np.random.default_rng(3)
    for _ in range(50):
        r = code.decode(rng.normal(size=512))          # what an unmarked model or wrong key looks like
        assert not r["ok"] and r["bits"] != PAYLOAD    # noise must not "decode" at all
    with pytest.raises(ValueError):
        code.decode(np.zeros(500))                     # wrong length


def test_bad_parameters_and_capacity():
    assert get_code("rs32").n_bits <= 576 and get_code("rep2").n_bits <= 576  # fit the mean-mode carrier
    assert get_code("rep3").n_bits > 576                                      # needs --mode full
    for bad in [lambda: get_code("rs240"), lambda: get_code("bch"), lambda: get_code("rep1"),
                lambda: get_code("rs32", k_bits=250)]:
        with pytest.raises(ValueError):
            bad()


def test_full_rs32_codeword_embeds_in_576_dim_carrier():
    """P4.2 in miniature: 512 codeword bits into a carrier the size of features.6.0 in mean mode."""
    torch = pytest.importorskip("torch")
    from embedding.projection import ProjectionWatermark

    class Mid(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = torch.nn.Conv2d(64, 8, 3, bias=False)     # mean-mode dim 64*3*3 = 576

    torch.manual_seed(0)
    m = Mid()
    code = get_code("rs32")
    cw = code.encode(PAYLOAD)
    wm = ProjectionWatermark(b"\x01" * 32, "conv.weight", code.n_bits, "mean", m.conv.weight.shape)
    target = torch.tensor(cw, dtype=torch.float32)
    opt = torch.optim.SGD(m.parameters(), lr=5.0)
    for _ in range(300):
        opt.zero_grad()
        wm.loss(m, target).backward()
        opt.step()
    got, logits = wm.extract(m)
    assert got == cw                                               # 0 raw errors on all 512 bits
    r = code.decode(logits)
    assert r["ok"] and r["bits"] == PAYLOAD
    with pytest.raises(ValueError):                                 # rep3 (768 bits) does not fit
        ProjectionWatermark(b"\x01" * 32, "conv.weight", get_code("rep3").n_bits, "mean", m.conv.weight.shape)


def test_gaussian_noise_copy_scope_and_scale():
    """P4.3 helper: returns a copy, touches only the chosen layers, noise std = level * weight std."""
    torch = pytest.importorskip("torch")
    from attacks.noise import add_gaussian_noise
    from training.model import SmallCNN

    m = SmallCNN(width=32)
    before = {k: v.clone() for k, v in m.state_dict().items()}
    g = torch.Generator().manual_seed(0)
    assert all(torch.equal(a, b) for a, b in zip(add_gaussian_noise(m, 0.0, generator=g).parameters(),
                                                 m.parameters()))           # level 0 changes nothing
    n = add_gaussian_noise(m, 0.1, layers=["features.6.0.weight"], generator=g)
    changed = {k for k, v in n.state_dict().items() if not torch.equal(v, before[k])}
    assert changed == {"features.6.0.weight"}                              # only the chosen layer
    assert all(torch.equal(v, before[k]) for k, v in m.state_dict().items())   # original untouched
    w, wn = m.features[6][0].weight, n.features[6][0].weight
    assert 0.09 < ((wn - w).std() / w.std()).item() < 0.11                 # 10% of the layer's std
    with pytest.raises(KeyError):
        add_gaussian_noise(m, 0.1, layers=["no.such.weight"])

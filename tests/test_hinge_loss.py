"""Margin-capped (hinge) watermark loss, the accuracy fix.
Run from the project root:  python -m pytest tests/test_hinge_loss.py -v   (expect 7 passed)"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
import torch.nn.functional as F  # noqa: E402

from embedding.projection import ProjectionWatermark, wm_loss_from_logits  # noqa: E402

KEY = b"\x01" * 32


class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = torch.nn.Conv2d(16, 32, 3, bias=False)


def _bits(n=32):
    bits_list = [int(b) for b in np.random.default_rng(3).integers(0, 2, n)]
    return bits_list, torch.tensor(bits_list, dtype=torch.float32)


def test_hinge_is_zero_with_zero_gradient_past_the_margin():
    z = torch.tensor([3.0, -3.0, 2.6, -2.5], requires_grad=True)     # every bit already past m = 2.5
    bits = torch.tensor([1.0, 0.0, 1.0, 0.0])
    loss = wm_loss_from_logits(z, bits, "hinge", 2.5)
    loss.backward()
    assert loss.item() == 0.0
    assert torch.equal(z.grad, torch.zeros(4))                      # nothing left pulling on the weights


def test_hinge_pushes_only_bits_below_the_margin_the_right_way():
    z = torch.tensor([0.5, -1.0, 3.0, -0.2], requires_grad=True)
    bits = torch.tensor([1.0, 0.0, 1.0, 1.0])                       # signed logits: 0.5, 1.0, 3.0, -0.2
    loss = wm_loss_from_logits(z, bits, "hinge", 2.5)
    loss.backward()
    assert loss.item() == pytest.approx((2.0 + 1.5 + 0.0 + 2.7) / 4)
    assert z.grad.tolist() == pytest.approx([-0.25, 0.25, 0.0, -0.25])
    # gradient descent moves z by -grad: bit-1 logits go up, the bit-0 logit goes down, the satisfied bit stays


def test_bce_is_still_the_default_and_unchanged():
    torch.manual_seed(0)
    m = Tiny()
    _, bits = _bits()
    wm = ProjectionWatermark(KEY, "conv.weight", 32, "mean", m.conv.weight.shape)
    assert wm.loss_kind == "bce"
    expected = F.binary_cross_entropy_with_logits(wm.logits(m), bits)
    assert wm.loss(m, bits).item() == pytest.approx(expected.item())


def test_bad_loss_kind_or_margin_is_rejected():
    shape = Tiny().conv.weight.shape
    with pytest.raises(ValueError):
        ProjectionWatermark(KEY, "conv.weight", 32, "mean", shape, loss_kind="mse")
    with pytest.raises(ValueError):
        ProjectionWatermark(KEY, "conv.weight", 32, "mean", shape, loss_kind="hinge", margin=0.0)


def _train(kind, steps=300, margin=1.0):
    torch.manual_seed(0)
    m = Tiny()
    bits_list, bits = _bits()
    wm = ProjectionWatermark(KEY, "conv.weight", 32, "mean", m.conv.weight.shape, loss_kind=kind, margin=margin)
    opt = torch.optim.SGD(m.parameters(), lr=0.5, weight_decay=5e-4)  # same weight decay as the real recipe
    for _ in range(steps):
        opt.zero_grad()
        wm.loss(m, bits).backward()
        opt.step()
    got, logits = wm.extract(m)
    return got == bits_list, np.abs(logits), wm.loss(m, bits).item()


def test_hinge_embeds_every_bit_and_then_stops_pushing():
    ok_h, abs_h, loss_h = _train("hinge")
    ok_b, abs_b, _ = _train("bce")
    assert ok_h and ok_b                                  # both embed all 32 bits
    assert abs_h.min() >= 0.95                            # hinge reaches the margin (m = 1.0) ...
    assert loss_h < 1e-3                                  # ... and then has (almost) nothing left to push
    assert abs_b.mean() > 2 * abs_h.mean()                # BCE keeps growing the logits (measured 3.0 vs 1.13)


def test_run_dir_keeps_old_names_and_tags_hinge_runs():
    pytest.importorskip("torchvision")
    from training.train_watermarked import run_dir
    old = run_dir("runs/wm_v1", 20.0, 256, "rs32", "features.6.0.weight", 0)
    assert old.as_posix() == "runs/wm_v1/lam20_n256_rs32/seed0"            # existing BCE runs are found again
    new = run_dir("runs/wm_v1", 20.0, 256, "rs32", "features.6.0.weight", 0, "hinge", 2.5)
    assert new.as_posix() == "runs/wm_v1/lam20_n256_rs32_hinge2.5/seed0"   # never overwrites a BCE run


def test_collect_runs_labels_old_and_new_runs():
    pytest.importorskip("pandas")
    from experiments.phase7.collect_runs import wm_loss_label
    assert wm_loss_label({"lam": 20.0}) == "bce"                           # final.json from before the fix
    assert wm_loss_label({"wm_loss": "bce", "hinge_margin": None}) == "bce"
    assert wm_loss_label({"wm_loss": "hinge", "hinge_margin": 2.5}) == "hinge2.5"

"""Needs torch and your training/model.py.  python -m pytest tests/test_phase6_attacks.py -v"""
import pytest

torch = pytest.importorskip("torch")
from torch.utils.data import DataLoader, TensorDataset  # noqa: E402

from attacks.common import carrier_block_index, conv_blocks, weight_tensors  # noqa: E402
from attacks.train_attacks import finetune, overwrite_watermark, prune_then_finetune  # noqa: E402
from attacks.weight_attacks import (add_noise, half_roundtrip, permute_channels, prune, quantize,  # noqa: E402
                                    rescale_channels, sparsity_of)

LAYER = "features.6.0.weight"


@pytest.fixture()
def net():
    from training.model import SmallCNN
    torch.manual_seed(0)
    m = SmallCNN(width=8)
    for mod in m.modules():                          # make BatchNorm statistics non-trivial
        if isinstance(mod, torch.nn.BatchNorm2d):
            mod.running_mean.normal_()
            mod.running_var.uniform_(0.5, 2.0)
            mod.weight.data.uniform_(0.5, 1.5)
            mod.bias.data.normal_()
    return m.eval()


@pytest.fixture()
def x():
    torch.manual_seed(1)
    return torch.randn(6, 3, 32, 32)


def _same(a, b, atol=1e-4):
    with torch.no_grad():
        return torch.allclose(a(x_cache[0]), b(x_cache[0]), atol=atol, rtol=1e-3)


x_cache = [None]


@pytest.fixture(autouse=True)
def _set_x(x):
    x_cache[0] = x


def test_permutations_preserve_the_function(net):
    for which in ("out_carrier", "in_carrier", "all"):
        assert _same(net, permute_channels(net, which, seed=3, layer=LAYER)), which


def test_permutation_effect_on_carrier_vector(net):
    v = lambda m: dict(m.named_parameters())[LAYER].detach().mean(dim=0).flatten()
    assert torch.allclose(v(net), v(permute_channels(net, "out_carrier", 5, LAYER)), atol=1e-6)   # mean over outputs unchanged
    assert not torch.allclose(v(net), v(permute_channels(net, "in_carrier", 5, LAYER)), atol=1e-6)  # order of the vector changes


def test_rescale_preserves_the_function(net):
    assert _same(net, rescale_channels(net, 3.0, seed=2, layer=LAYER), atol=2e-3)
    assert _same(net, rescale_channels(net, 3.0, seed=2, layer=None), atol=2e-3)
    w0 = dict(net.named_parameters())[LAYER].detach()
    w1 = dict(rescale_channels(net, 3.0, 2, LAYER).named_parameters())[LAYER].detach()
    assert not torch.allclose(w0, w1)


def test_prune_sparsity(net):
    g = prune(net, 0.5, "global")
    assert abs(sparsity_of(g) - 0.5) < 0.01
    for w in weight_tensors(prune(net, 0.5, "layer")):
        assert abs((w == 0).float().mean().item() - 0.5) < 0.02


def test_quantize_levels(net):
    q = quantize(net, 4)
    for w in weight_tensors(q):
        assert len(torch.unique(w)) <= 15
    qc = quantize(net, 4, per_channel=True)
    for w in weight_tensors(qc):
        assert all(len(torch.unique(row)) <= 15 for row in w.detach().flatten(1))
    h = half_roundtrip(net)
    assert max((a - b).abs().max().item() for a, b in zip(net.parameters(), h.parameters())) < 1e-2


def test_noise_scale_and_scope(net):
    base = dict(net.named_parameters())
    n = dict(add_noise(net, 0.1, seed=1).named_parameters())
    d = (n[LAYER] - base[LAYER]).detach()
    assert 0.07 < d.std().item() / base[LAYER].detach().std().item() < 0.13
    only = dict(add_noise(net, 0.5, seed=1, carrier_layer=LAYER).named_parameters())
    assert not torch.equal(only[LAYER], base[LAYER])
    other = "features.3.0.weight"
    assert torch.equal(only[other], base[other])


def _loader(n=64):
    torch.manual_seed(2)
    return DataLoader(TensorDataset(torch.randn(n, 3, 32, 32), torch.randint(0, 10, (n,))), batch_size=32)


def test_training_attacks_run(net):
    ft = finetune(net, _loader(), epochs=1, lr=0.01, dev="cpu")
    assert not torch.equal(dict(ft.named_parameters())[LAYER], dict(net.named_parameters())[LAYER])
    pf = prune_then_finetune(net, _loader(), sparsity=0.6, epochs=1, lr=0.01, dev="cpu")
    assert sparsity_of(pf) >= 0.58                                   # mask kept zero during fine-tuning
    out, ber, margin = overwrite_watermark(net, _loader(), LAYER, n_bits=16, lam=20.0, epochs=2, lr=0.05, seed=4, dev="cpu")
    assert 0.0 <= ber <= 1.0 and margin >= 0.0


def test_carrier_block_index(net):
    k = carrier_block_index(net, LAYER)
    assert conv_blocks(net)[k][0] is net.get_submodule("features.6.0")


def test_quantize_refuses_one_bit(net):
    with pytest.raises(ValueError):
        quantize(net, 1)                             # qmax would be 0: every weight becomes NaN

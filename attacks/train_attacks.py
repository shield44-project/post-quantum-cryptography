"""Attacks that need training: fine-tuning, prune + fine-tune, and overwriting with a second watermark.

All functions take a ready DataLoader (so they can be unit-tested with tiny fake data) and return a NEW model.
"""
import numpy as np
import torch
import torch.nn.functional as F

from attacks.common import clone_model, device, weight_tensors
from attacks.weight_attacks import prune


def _sgd(model, lr, wd=5e-4):
    return torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9, weight_decay=wd)


def finetune(model, loader, epochs, lr, dev=None, masks=None, extra_loss=None):
    """Plain fine-tuning with cross-entropy (what a remover with some data would do).
    masks: optional list of 0/1 tensors (same order as weight_tensors) re-applied after every step (pruning with recovery).
    extra_loss: optional callable(model) -> scalar added to the loss (used by the overwrite attack)."""
    dev = dev or device()
    m = clone_model(model).to(dev)
    opt = _sgd(m, lr)
    ws = weight_tensors(m)
    mk = [x.to(dev) for x in masks] if masks is not None else None
    for _ in range(epochs):
        m.train()
        for x, y in loader:
            x, y = x.to(dev), y.to(dev)
            loss = F.cross_entropy(m(x), y)
            if extra_loss is not None:
                loss = loss + extra_loss(m)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            if mk is not None:
                with torch.no_grad():
                    for w, k in zip(ws, mk):
                        w.mul_(k)
    return m.eval()


def prune_then_finetune(model, loader, sparsity, epochs, lr, dev=None):
    """Global magnitude pruning, then fine-tune with the pruned weights kept at zero."""
    pruned = prune(model, sparsity, "global")
    masks = [(w != 0).to(w.dtype).detach().clone() for w in weight_tensors(pruned)]
    return finetune(pruned, loader, epochs, lr, dev=dev, masks=masks)


class SecondWatermark:
    """The attacker's own projection watermark (random +/-1 matrix, random bits) on one layer, 'mean' carrier."""

    def __init__(self, layer_name, weight_shape, n_bits, seed):
        rng = np.random.default_rng(seed % (2 ** 32))
        self.layer_name = layer_name
        dim = int(weight_shape[1] * np.prod(weight_shape[2:]))
        self.X = torch.tensor(rng.integers(0, 2, size=(n_bits, dim)) * 2.0 - 1.0, dtype=torch.float32)
        self.bits = torch.tensor(rng.integers(0, 2, size=n_bits), dtype=torch.float32)

    def logits(self, model):
        w = dict(model.named_parameters())[self.layer_name]
        v = w.mean(dim=0).flatten()
        return self.X.to(v.device) @ v

    def loss(self, model):
        z = self.logits(model)
        return F.binary_cross_entropy_with_logits(z, self.bits.to(z.device))

    @torch.no_grad()
    def readout(self, model):
        z = self.logits(model).cpu()
        got = (z > 0).float()
        return float((got != self.bits).float().mean()), float(z.abs().min())


def overwrite_watermark(model, loader, layer_name, n_bits, lam, epochs, lr, seed, dev=None):
    """Embed a SECOND watermark (attacker's key and bits) into the same layer by fine-tuning with
    CE + lam * BCE. Returns (attacked_model, attacker_ber, attacker_min_abs_logit)."""
    shape = dict(model.named_parameters())[layer_name].shape
    wm = SecondWatermark(layer_name, shape, n_bits, seed)
    out = finetune(model, loader, epochs, lr, dev=dev, extra_loss=lambda mm: lam * wm.loss(mm))
    ber, margin = wm.readout(out)
    return out, ber, margin

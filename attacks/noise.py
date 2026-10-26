"""Gaussian weight noise (Phase 4 light-noise check; reused by the Phase 6 attack suite).

Each chosen weight tensor W becomes  W + N(0, (level * std(W))^2): the noise is scaled to the
tensor's own spread, so level 0.05 means "5% of a typical weight" in every layer.
"""
import copy

import torch


def add_gaussian_noise(model, level, layers=None, generator=None):
    """Return a NOISY COPY of `model` (the original is untouched).

    layers: parameter names to perturb; None = every conv / linear weight (tensors with dim > 1).
    generator: a torch.Generator, so the same seed gives the same noise.
    """
    noisy = copy.deepcopy(model)
    params = dict(noisy.named_parameters())
    if layers is not None:
        missing = [n for n in layers if n not in params]
        if missing:
            raise KeyError("parameters not found: %s" % missing)
    with torch.no_grad():
        for name, p in params.items():
            if (layers is None and p.dim() > 1) or (layers is not None and name in layers):
                noise = torch.randn(p.shape, generator=generator, dtype=p.dtype)
                p.add_(noise.to(p.device) * level * p.std())
    return noisy

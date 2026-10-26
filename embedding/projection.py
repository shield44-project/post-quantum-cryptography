"""Projection-based weight watermark (Uchida et al. style) in PyTorch (Phase 3).

carrier vector v  : the chosen conv layer's weights, either
                    "mean" -> average over output channels, flattened (dim = in*k*k)
                    "full" -> the whole weight tensor flattened   (dim = out*in*k*k)
logits            : X @ v            (X = secret +/-1 matrix, shape n_bits x dim)
watermark loss    : BCE-with-logits(logits, payload bits)
extraction        : bit = 1 if logit > 0 else 0
"""
import torch
import torch.nn.functional as F

from embedding.keys import projection_matrix_np


def get_weight(model, layer_name):
    params = dict(model.named_parameters())
    if layer_name not in params:
        convs = [n for n, p in params.items() if p.dim() == 4]
        raise KeyError("layer %r not found. Conv weights available: %s" % (layer_name, convs))
    return params[layer_name]


def carrier_vector(weight, mode):
    if mode == "mean":
        return weight.mean(dim=0).flatten()
    if mode == "full":
        return weight.flatten()
    raise ValueError("mode must be 'mean' or 'full'")


def carrier_dim(weight_shape, mode):
    out, inn = weight_shape[0], weight_shape[1]
    k = 1
    for s in weight_shape[2:]:
        k *= s
    return inn * k if mode == "mean" else out * inn * k


class ProjectionWatermark:
    def __init__(self, key: bytes, layer_name: str, n_bits: int, mode: str, weight_shape):
        self.layer_name, self.n_bits, self.mode = layer_name, n_bits, mode
        self.dim = carrier_dim(tuple(weight_shape), mode)
        if mode == "mean" and n_bits > self.dim:
            raise ValueError("n_bits (%d) exceeds carrier dimension (%d). Use --mode full, a wider model, or fewer bits." % (n_bits, self.dim))
        self._X_cpu = torch.from_numpy(projection_matrix_np(key, layer_name, n_bits, self.dim))
        self._X_dev = {}

    def _X(self, like):
        key = (like.device, like.dtype)
        if key not in self._X_dev:
            self._X_dev[key] = self._X_cpu.to(device=like.device, dtype=like.dtype)
        return self._X_dev[key]

    def logits(self, model):
        v = carrier_vector(get_weight(model, self.layer_name), self.mode)
        return self._X(v) @ v

    def loss(self, model, bits):
        """bits: tensor of 0./1. with shape (n_bits,)"""
        z = self.logits(model)
        return F.binary_cross_entropy_with_logits(z, bits.to(device=z.device, dtype=z.dtype))

    @torch.no_grad()
    def extract(self, model):
        """Return (bits as python list[int], logits as python list[float])."""
        z = self.logits(model).detach().float().cpu()
        return [int(b) for b in (z > 0).int().tolist()], z.tolist()

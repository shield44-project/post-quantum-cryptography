"""Projection-based weight watermark (Uchida et al. style) in PyTorch (Phase 3).

carrier vector v  : the chosen conv layer's weights, either
                    "mean" -> average over output channels, flattened (dim = in*k*k)
                    "full" -> the whole weight tensor flattened   (dim = out*in*k*k)
logits            : X @ v            (X = secret +/-1 matrix, shape n_bits x dim)
watermark loss    : "bce"   -> BCE-with-logits(logits, payload bits)           (Phases 3-6, the default)
                    "hinge" -> mean(relu(m - s * logits)), s = +1 for bit 1, -1 for bit 0
                               (margin-capped: a bit whose logit is already past m adds no loss and
                               no gradient, so the watermark stops competing with classification)
extraction        : bit = 1 if logit > 0 else 0
"""
import torch
import torch.nn.functional as F

from embedding.keys import projection_matrix_np

WM_LOSSES = ("bce", "hinge")


def wm_loss_from_logits(z, bits, kind="bce", margin=2.5):
    """Watermark loss for logits z and target bits (0./1., same shape as z)."""
    if kind == "bce":
        return F.binary_cross_entropy_with_logits(z, bits)
    if kind == "hinge":
        if margin <= 0:
            raise ValueError("hinge margin must be > 0, got %r" % margin)
        signs = 2.0 * bits - 1.0                    # bit 1 -> +1, bit 0 -> -1
        return F.relu(margin - signs * z).mean()    # 0 once every signed logit is >= margin
    raise ValueError("wm loss must be one of %s, got %r" % (WM_LOSSES, kind))


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
    def __init__(self, key: bytes, layer_name: str, n_bits: int, mode: str, weight_shape,
                 loss_kind: str = "bce", margin: float = 2.5):
        self.layer_name, self.n_bits, self.mode = layer_name, n_bits, mode
        wm_loss_from_logits(torch.zeros(1), torch.ones(1), loss_kind, margin)    # fail fast on a bad kind/margin
        self.loss_kind, self.margin = loss_kind, margin
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

    def matrix(self):
        """The secret +/-1 matrix X (n_bits x dim) as a numpy array."""
        return self._X_cpu.numpy()

    def logits(self, model):
        v = carrier_vector(get_weight(model, self.layer_name), self.mode)
        return self._X(v) @ v

    def loss(self, model, bits):
        """bits: tensor of 0./1. with shape (n_bits,)"""
        z = self.logits(model)
        return wm_loss_from_logits(z, bits.to(device=z.device, dtype=z.dtype), self.loss_kind, self.margin)

    @torch.no_grad()
    def extract(self, model):
        """Return (bits as python list[int], logits as python list[float])."""
        z = self.logits(model).detach().float().cpu()
        return [int(b) for b in (z > 0).int().tolist()], z.tolist()

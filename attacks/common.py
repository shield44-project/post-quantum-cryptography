"""Shared helpers for the Phase 6 attack suite (torch).

Self-contained on purpose: an attacker does not use the defender's code, and this
keeps Phase 6 independent of any later changes to embedding/ or verify/.
Only `training.model.SmallCNN` is imported (to rebuild the architecture).
"""
import copy
import hashlib
import os

import numpy as np
import torch
import torch.nn as nn

MEAN, STD = (0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)


def device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def stable_seed(*parts) -> int:
    """Deterministic 32-bit seed from any tuple of labels (same inputs -> same attack)."""
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


def seed_everything(seed: int):
    np.random.seed(seed % (2 ** 32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------------- model io
def load_state_dict(path, allow_pickle=False):
    """Accepts a raw state_dict, {'state_dict': ...} or (allow_pickle=True) a pickled nn.Module.
    A full unpickle can run code, so it is only done when asked for."""
    try:
        obj = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        obj = torch.load(path, map_location="cpu")
    except Exception as e:
        if not allow_pickle:
            raise ValueError("not a plain weights file (%s); refusing to unpickle it" % type(e).__name__) from e
        obj = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(obj, nn.Module):
        obj = obj.state_dict()
    if isinstance(obj, dict):
        for k in ("state_dict", "model_state_dict", "model"):
            if k in obj and isinstance(obj[k], dict):
                obj = obj[k]
                break
    return {k.replace("module.", "", 1): v for k, v in obj.items()}


def load_model(path, width=32):
    from training.model import SmallCNN
    m = SmallCNN(width=width)
    m.load_state_dict(load_state_dict(path))
    m.eval()
    return m


def clone_model(model):
    return copy.deepcopy(model)


def save_model(model, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, path)


# ---------------------------------------------------------------- structure
def conv_blocks(model):
    """[(conv, bn), ...] in forward order, from model.features (Sequential blocks of Conv, BN, ReLU)."""
    blocks = []
    for child in model.features:
        if isinstance(child, nn.Sequential) and len(child) >= 2 \
                and isinstance(child[0], nn.Conv2d) and isinstance(child[1], nn.BatchNorm2d):
            blocks.append((child[0], child[1]))
    if not blocks:
        raise RuntimeError("no Conv+BatchNorm blocks found in model.features; adapt attacks/common.py:conv_blocks")
    return blocks


def final_linear(model):
    lins = [m for m in model.classifier.modules() if isinstance(m, nn.Linear)]
    if not lins:
        raise RuntimeError("no Linear layer found in model.classifier")
    return lins[-1]


def weight_tensors(model):
    """Conv and Linear weight tensors (the things pruning / quantization / noise act on)."""
    return [m.weight for m in model.modules() if isinstance(m, (nn.Conv2d, nn.Linear))]


def carrier_block_index(model, layer_name):
    """Index (in conv_blocks) of the block whose conv weight is `layer_name`, e.g. features.6.0.weight."""
    module_name = layer_name.rsplit(".", 1)[0]
    target = dict(model.named_modules())[module_name]
    for i, (conv, _) in enumerate(conv_blocks(model)):
        if conv is target:
            return i
    raise KeyError("layer %s is not a conv block of this model" % layer_name)


# ---------------------------------------------------------------- data
def _transforms(train):
    import torchvision.transforms as T
    tf = [T.ToTensor(), T.Normalize(MEAN, STD)]
    if train:
        tf = [T.RandomCrop(32, padding=4), T.RandomHorizontalFlip()] + tf
    return T.Compose(tf)


def test_loader(root=None, batch_size=512, workers=2):
    import torchvision
    from torch.utils.data import DataLoader
    root = root or os.environ.get("CIFAR_ROOT", "data")
    ds = torchvision.datasets.CIFAR10(root, train=False, download=True, transform=_transforms(False))
    return DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=workers)


def train_loader(frac, seed, root=None, batch_size=128, workers=2):
    """A reproducible random `frac` of the CIFAR-10 train set (the attacker's data)."""
    import torchvision
    from torch.utils.data import DataLoader, Subset
    root = root or os.environ.get("CIFAR_ROOT", "data")
    ds = torchvision.datasets.CIFAR10(root, train=True, download=True, transform=_transforms(True))
    if frac < 1.0:
        n = int(len(ds) * frac)
        idx = np.random.default_rng(seed % (2 ** 32)).permutation(len(ds))[:n]
        ds = Subset(ds, idx.tolist())
    return DataLoader(ds, batch_size=batch_size, shuffle=True, num_workers=workers, drop_last=False)


@torch.no_grad()
def evaluate(model, loader, dev=None):
    dev = dev or device()
    model = model.to(dev).eval()
    correct = total = 0
    for x, y in loader:
        x, y = x.to(dev), y.to(dev)
        correct += (model(x).argmax(1) == y).sum().item()
        total += y.numel()
    return correct / total

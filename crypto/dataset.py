"""Merkle root over a dataset (Phase 2).

IMPORTANT: the root is computed over the RAW stored images (uint8, H x W x C),
never over augmented or normalised tensors. That is what makes it reproducible.
"""
import os

import numpy as np

from crypto.merkle import leaf_hash, merkle_root

LEAF_FORMAT = "sha256(0x00|index:u64be|label:u16be|image_bytes_HWC_uint8)"
NODE_FORMAT = "sha256(0x01|left|right); odd node promoted unchanged"


def leaves_from_arrays(images, labels):
    images = np.asarray(images)
    if images.dtype != np.uint8:
        raise ValueError("images must be uint8 (raw pixels), got %s" % images.dtype)
    if len(images) != len(labels):
        raise ValueError("images and labels must have the same length")
    return [
        leaf_hash(i, int(labels[i]), np.ascontiguousarray(images[i]).tobytes())
        for i in range(len(images))
    ]


def dataset_root_from_arrays(images, labels) -> bytes:
    return merkle_root(leaves_from_arrays(images, labels))


def load_cifar10_train(root=None, download=False):
    """Return (images uint8 [50000,32,32,3], labels list[int]) without any transform."""
    from torchvision.datasets import CIFAR10  # imported here so tests need no torch

    root = root or os.environ.get("CIFAR_ROOT", "data")
    ds = CIFAR10(root=root, train=True, download=download)
    return ds.data, list(ds.targets)


def cifar10_train_root(root=None, download=False) -> bytes:
    images, labels = load_cifar10_train(root, download)
    return dataset_root_from_arrays(images, labels)

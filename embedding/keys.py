"""Watermark key + projection matrix, numpy/hashlib only (Phase 3).

The projection matrix X is derived from the SECRET watermark key with SHAKE-256,
so it is bit-for-bit reproducible on any machine (Colab, WSL, auditor's laptop),
independent of numpy / torch versions. Entries are +1 / -1.
"""
import hashlib
import math

import numpy as np

SCHEME = "projection-v1"


def load_key(path) -> bytes:
    with open(path, "rb") as f:
        key = f.read()
    if len(key) < 16:
        raise ValueError("watermark key looks too short (%d bytes)" % len(key))
    return key


def key_fingerprint(key: bytes) -> str:
    """Non-reversible short tag, only to detect 'wrong key used' mistakes."""
    return hashlib.sha256(b"wm-key-fingerprint|" + key).hexdigest()[:16]


def projection_matrix_np(key: bytes, layer_name: str, n_bits: int, dim: int) -> np.ndarray:
    seed = hashlib.sha256(
        key + b"|" + SCHEME.encode() + b"|" + layer_name.encode() + b"|%dx%d" % (n_bits, dim)
    ).digest()
    stream = hashlib.shake_256(seed).digest((n_bits * dim + 7) // 8)
    bits = np.unpackbits(np.frombuffer(stream, dtype=np.uint8))[: n_bits * dim]
    return (bits.astype(np.float32) * 2.0 - 1.0).reshape(n_bits, dim)


def hex_to_bits(hex_string: str, n_bits=None):
    bits = [int(b) for ch in hex_string.strip() for b in format(int(ch, 16), "04b")]
    return bits if n_bits is None else bits[:n_bits]


def load_payload_bits(path, n_bits):
    """Read release/payload.hex (256 bits) and return its first n_bits bits."""
    with open(path) as f:
        bits = hex_to_bits(f.read())
    if n_bits > len(bits):
        raise ValueError("payload file has only %d bits, asked for %d" % (len(bits), n_bits))
    return bits[:n_bits]


def bit_error_rate(a, b) -> float:
    a, b = list(a), list(b)
    if len(a) != len(b):
        raise ValueError("length mismatch")
    return sum(int(x != y) for x, y in zip(a, b)) / len(a)


def false_accept_probability(n_bits: int, max_errors: int) -> float:
    """Chance that RANDOM bits match a payload with at most `max_errors` wrong bits."""
    return sum(math.comb(n_bits, k) for k in range(max_errors + 1)) / 2 ** n_bits

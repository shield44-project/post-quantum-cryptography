"""Manifest: the signed JSON record that describes dataset + model (Phase 2).

payload = first `payload_bits` bits of SHA-256(canonical manifest bytes).
The manifest does NOT contain the payload (that would be circular).
"""
import hashlib
import json
from datetime import datetime, timezone

from crypto.dataset import LEAF_FORMAT, NODE_FORMAT
from crypto.signing import ALG

FORMAT_VERSION = 1
WATERMARK_SCHEME = "projection-v1"


def expected_smallcnn_params(width: int, num_classes: int = 10) -> int:
    """Closed-form parameter count of SmallCNN (width 32 -> 160,234)."""
    w = width
    convs = 3 * w * 9 + w * w * 9 + w * 2 * w * 9 + 2 * w * 2 * w * 9 + 2 * w * 4 * w * 9
    bns = 2 * (w + w + 2 * w + 2 * w + 4 * w)
    linear = 4 * w * 4 * 4 * num_classes + num_classes
    return convs + bns + linear


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_manifest(developer_id, key_id, merkle_root_hex, num_samples, width,
                   num_params, payload_bits=256, created_utc=None):
    return {
        "format_version": FORMAT_VERSION,
        "developer_id": developer_id,
        "key_id": key_id,
        "signature_algorithm": ALG,
        "created_utc": created_utc or utc_now(),
        "dataset": {
            "name": "CIFAR-10",
            "split": "train",
            "num_samples": int(num_samples),
            "merkle_root_sha256": merkle_root_hex,
            "leaf_format": LEAF_FORMAT,
            "node_format": NODE_FORMAT,
        },
        "model": {"architecture": "SmallCNN", "width": int(width), "num_params": int(num_params)},
        "watermark": {"scheme": WATERMARK_SCHEME, "payload_bits": int(payload_bits)},
    }


def canonical_bytes(manifest: dict) -> bytes:
    """Deterministic JSON: sorted keys, no spaces. This is the exact byte string that is signed."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def payload_bits(manifest: dict, n_bits=None) -> list:
    n = manifest["watermark"]["payload_bits"] if n_bits is None else n_bits
    if not 1 <= n <= 256:
        raise ValueError("payload_bits must be between 1 and 256")
    digest = hashlib.sha256(canonical_bytes(manifest)).digest()
    bits = [(byte >> k) & 1 for byte in digest for k in range(7, -1, -1)]  # MSB first
    return bits[:n]


def bits_to_hex(bits) -> str:
    if len(bits) % 4:
        raise ValueError("bit count must be a multiple of 4")
    return "".join("%x" % int("".join(str(b) for b in bits[i:i + 4]), 2) for i in range(0, len(bits), 4))


def hex_to_bits(hex_string: str, n_bits=None) -> list:
    hex_string = hex_string.strip()
    bits = [int(b) for ch in hex_string for b in format(int(ch, 16), "04b")]
    return bits if n_bits is None else bits[:n_bits]

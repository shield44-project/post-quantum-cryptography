"""Run from the project root:  python -m pytest tests/test_phase2.py -v   (expect 5 passed)"""
import numpy as np
import pytest

from crypto.dataset import dataset_root_from_arrays
from crypto.manifest import (bits_to_hex, build_manifest, canonical_bytes,
                             expected_smallcnn_params, hex_to_bits, payload_bits)
from crypto.merkle import build_levels, leaf_hash, merkle_proof, merkle_root, verify_proof


def _leaves(n):
    return [leaf_hash(i, i % 10, bytes([i % 256]) * 8) for i in range(n)]


def test_merkle_proofs_all_sizes():
    for n in [1, 2, 3, 4, 5, 7, 8, 9, 16, 17, 33, 100]:
        leaves = _leaves(n)
        levels = build_levels(leaves)
        root = levels[-1][0]
        assert root == merkle_root(leaves)
        for i in range(n):
            proof = merkle_proof(levels, i)
            assert verify_proof(leaves[i], proof, root), (n, i)
            assert not verify_proof(leaf_hash(i, 99, b"x"), proof, root)   # wrong leaf
        if n > 1:
            bad = list(merkle_proof(levels, 0))
            sib, side = bad[0]
            bad[0] = (bytes([sib[0] ^ 1]) + sib[1:], side)
            assert not verify_proof(leaves[0], bad, root)                  # tampered proof


def test_one_changed_leaf_changes_root():
    leaves = _leaves(37)
    root = merkle_root(leaves)
    for i in (0, 18, 36):
        changed = list(leaves)
        changed[i] = leaf_hash(i, 5, b"different")
        assert merkle_root(changed) != root
    assert merkle_root(list(reversed(leaves))) != root                     # order matters


def _manifest():
    return build_manifest("dev", "ab" * 16, "00" * 32, 50000, 32,
                          expected_smallcnn_params(32), 256, created_utc="2026-10-25T00:00:00Z")


def test_signature_tamper_wrong_key_tampered_manifest():
    pytest.importorskip("oqs")
    from crypto.signing import generate_keys, sign, verify
    pk, sk = generate_keys()
    pk2, _ = generate_keys()
    msg = canonical_bytes(_manifest())
    sig = sign(sk, msg)
    assert verify(pk, msg, sig)                                            # good
    assert not verify(pk, msg, bytes([sig[0] ^ 1]) + sig[1:])              # signature tampered
    assert not verify(pk2, msg, sig)                                       # wrong key
    m2 = _manifest()
    m2["developer_id"] = "mallory"
    assert not verify(pk, canonical_bytes(m2), sig)                        # manifest tampered
    assert not verify(pk, msg, b"short")                                   # garbage -> False, no crash


def test_payload_depends_on_manifest():
    m = _manifest()
    p = payload_bits(m)
    assert len(p) == 256 and set(p) <= {0, 1}
    assert p == payload_bits(_manifest())                                  # deterministic
    m2 = _manifest()
    m2["dataset"]["merkle_root_sha256"] = "11" * 32
    assert payload_bits(m2) != p                                           # depends on manifest
    assert hex_to_bits(bits_to_hex(p)) == p                                # hex round trip
    assert expected_smallcnn_params(32) == 160234


def test_one_cifar_pixel_changes_dataset_root():
    rng = np.random.default_rng(0)
    images = rng.integers(0, 256, size=(200, 32, 32, 3), dtype=np.uint8)
    labels = list(rng.integers(0, 10, size=200))
    root = dataset_root_from_arrays(images, labels)
    assert root == dataset_root_from_arrays(images.copy(), labels)         # reproducible
    images2 = images.copy()
    images2[123, 5, 7, 1] ^= 1                                             # flip one bit of one pixel
    assert dataset_root_from_arrays(images2, labels) != root
    labels2 = list(labels)
    labels2[3] = (labels2[3] + 1) % 10                                     # change one label
    assert dataset_root_from_arrays(images, labels2) != root

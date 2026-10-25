"""Merkle tree used to commit to a whole dataset with a single hash (Phase 2).

Leaf hash : SHA-256(0x00 | index (u64, big-endian) | label (u16, big-endian) | image bytes)
Node hash : SHA-256(0x01 | left | right)
Odd node  : when a level has an odd number of nodes, the last node is promoted
            unchanged to the next level (no duplication).

The 0x00 / 0x01 prefixes keep leaf hashes and node hashes in separate domains,
and putting the index inside the leaf means two samples can not be swapped
without changing the root.
"""
import hashlib
import struct

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(index: int, label: int, image_bytes: bytes) -> bytes:
    return _sha256(LEAF_PREFIX + struct.pack(">QH", index, label) + image_bytes)


def node_hash(left: bytes, right: bytes) -> bytes:
    return _sha256(NODE_PREFIX + left + right)


def build_levels(leaves):
    """Return every level of the tree, from the leaves (levels[0]) up to [root]."""
    if len(leaves) == 0:
        raise ValueError("cannot build a Merkle tree with zero leaves")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        nxt = [node_hash(cur[i], cur[i + 1]) for i in range(0, len(cur) - 1, 2)]
        if len(cur) % 2 == 1:
            nxt.append(cur[-1])  # promote the odd node unchanged
        levels.append(nxt)
    return levels


def merkle_root(leaves) -> bytes:
    return build_levels(leaves)[-1][0]


def merkle_proof(levels, index: int):
    """Proof for leaf `index`: a list of (sibling_hash, "L" or "R") from bottom to top.

    "R" means the sibling sits on the right of the running hash, "L" on the left.
    A promoted (odd) node has no sibling at that level, so nothing is added.
    """
    if not 0 <= index < len(levels[0]):
        raise IndexError("leaf index out of range")
    proof = []
    idx = index
    for level in levels[:-1]:
        if idx % 2 == 0:
            if idx + 1 < len(level):
                proof.append((level[idx + 1], "R"))
        else:
            proof.append((level[idx - 1], "L"))
        idx //= 2
    return proof


def verify_proof(leaf: bytes, proof, root: bytes) -> bool:
    cur = leaf
    for sibling, side in proof:
        if side == "R":
            cur = node_hash(cur, sibling)
        elif side == "L":
            cur = node_hash(sibling, cur)
        else:
            return False
    return cur == root

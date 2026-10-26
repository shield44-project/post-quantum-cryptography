"""Phase 5: create a SECOND developer, "Mallory", for the negative-case tests (runs LOCALLY, needs liboqs).

    python -m experiments.phase5_make_mallory

Writes mallory/keys/ (ML-DSA-65 key pair + watermark key, git-ignored) and mallory/release/
(signed manifest, payload.hex, public key), with the same layout as our own keys/ and release/.
Mallory claims the same public CIFAR-10 dataset, so the Merkle root is copied from our signed
manifest (pass --cifar-root to hash the dataset instead). Refuses to overwrite without --force.
"""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from crypto.dataset import cifar10_train_root
from crypto.manifest import bits_to_hex, build_manifest, canonical_bytes, payload_bits
from crypto.signing import ALG, generate_keys, key_id, sign
from embedding.keys import key_fingerprint
from experiments.phase2_make_release import count_params


def write_release(rel_dir, manifest, secret_key, public_key):
    """Sign `manifest` and write signed_manifest.json, payload.hex, public_key.bin (Phase 2 layout)."""
    rel_dir = Path(rel_dir)
    rel_dir.mkdir(parents=True, exist_ok=True)
    signed = {"format": "pq-signed-manifest-v1", "algorithm": ALG, "manifest": manifest,
              "signature_hex": sign(secret_key, canonical_bytes(manifest)).hex()}
    (rel_dir / "signed_manifest.json").write_text(json.dumps(signed, indent=2, sort_keys=True))
    (rel_dir / "payload.hex").write_text(bits_to_hex(payload_bits(manifest)) + "\n")
    (rel_dir / "public_key.bin").write_bytes(public_key)
    return signed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--developer-id", default="Mallory")
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--payload-bits", type=int, default=256)
    ap.add_argument("--our-release", default="release", help="Merkle root is copied from here")
    ap.add_argument("--cifar-root", default=None, help="hash CIFAR-10 here instead of copying the root")
    ap.add_argument("--out", default="mallory")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    keys_dir, rel_dir = Path(args.out) / "keys", Path(args.out) / "release"
    if (rel_dir / "signed_manifest.json").exists() and not args.force:
        sys.exit("%s exists. Re-running gives Mallory new keys and a new payload, so any Mallory model "
                 "trained on the old ones stops verifying. Use --force only if you mean it." % rel_dir)

    pk, sk = generate_keys()
    wm_key = secrets.token_bytes(32)
    keys_dir.mkdir(parents=True, exist_ok=True)
    (keys_dir / "public_key.bin").write_bytes(pk)
    (keys_dir / "secret_key.bin").write_bytes(sk)
    (keys_dir / "watermark_key.bin").write_bytes(wm_key)
    os.chmod(keys_dir / "secret_key.bin", 0o600)
    os.chmod(keys_dir / "watermark_key.bin", 0o600)

    if args.cifar_root:
        root = cifar10_train_root(args.cifar_root).hex()
    else:
        root = json.loads((Path(args.our_release) / "signed_manifest.json").read_text())["manifest"]["dataset"]["merkle_root_sha256"]

    manifest = build_manifest(args.developer_id, key_id(pk), root, 50000, args.width,
                              count_params(args.width), args.payload_bits)
    write_release(rel_dir, manifest, sk, pk)
    print("developer id : %s" % args.developer_id)
    print("key id       : %s" % key_id(pk))
    print("wm key       : fingerprint %s" % key_fingerprint(wm_key))
    print("merkle root  : %s (%s)" % (root, "hashed" if args.cifar_root else "copied from " + args.our_release))
    print("payload      : %s" % bits_to_hex(payload_bits(manifest)))
    print("wrote        : %s (git-ignored) and %s" % (keys_dir, rel_dir))


if __name__ == "__main__":
    main()

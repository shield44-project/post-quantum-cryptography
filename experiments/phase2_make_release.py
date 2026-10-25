"""Phase 2: build and sign the release (runs LOCALLY, needs liboqs).

    python -m experiments.phase2_make_release --developer-id "your-name" --width 32

Creates (or loads) ML-DSA-65 keys in keys/, computes the Merkle root of the
CIFAR-10 train set, builds the manifest, signs it and writes release/.
Refuses to overwrite an existing release unless you pass --force.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from crypto.dataset import cifar10_train_root
from crypto.manifest import (bits_to_hex, build_manifest, canonical_bytes,
                             expected_smallcnn_params, payload_bits)
from crypto.signing import ALG, generate_keys, key_id, sign


def count_params(width):
    try:  # prefer the real model if it is importable
        from training.model import SmallCNN
        return sum(p.numel() for p in SmallCNN(width=width).parameters())
    except Exception:
        return expected_smallcnn_params(width)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--developer-id", required=True)
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--payload-bits", type=int, default=256)
    ap.add_argument("--cifar-root", default=os.environ.get("CIFAR_ROOT", "data"))
    ap.add_argument("--keys-dir", default="keys")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    keys_dir, rel_dir = Path(args.keys_dir), Path(args.release_dir)
    signed_path = rel_dir / "signed_manifest.json"
    if signed_path.exists() and not args.force:
        sys.exit("release/ already exists. A new release changes the payload. Use --force only if you mean it.")

    # 1. keys
    keys_dir.mkdir(exist_ok=True)
    pk_path, sk_path = keys_dir / "public_key.bin", keys_dir / "secret_key.bin"
    if pk_path.exists() and sk_path.exists():
        pk, sk = pk_path.read_bytes(), sk_path.read_bytes()
        print("loaded existing keys from", keys_dir)
    else:
        pk, sk = generate_keys()
        pk_path.write_bytes(pk)
        sk_path.write_bytes(sk)
        os.chmod(sk_path, 0o600)
        print("generated new %s keys (public %d B, secret %d B)" % (ALG, len(pk), len(sk)))

    # 2. dataset commitment
    print("hashing CIFAR-10 train set (50,000 leaves)...")
    root = cifar10_train_root(args.cifar_root, download=True)
    print("merkle root:", root.hex())

    # 3. manifest + signature
    manifest = build_manifest(args.developer_id, key_id(pk), root.hex(), 50000,
                              args.width, count_params(args.width), args.payload_bits)
    message = canonical_bytes(manifest)
    signature = sign(sk, message)
    payload_hex = bits_to_hex(payload_bits(manifest))

    # 4. write release/
    rel_dir.mkdir(exist_ok=True)
    signed = {"format": "pq-signed-manifest-v1", "algorithm": ALG,
              "manifest": manifest, "signature_hex": signature.hex()}
    signed_path.write_text(json.dumps(signed, indent=2, sort_keys=True))
    (rel_dir / "payload.hex").write_text(payload_hex + "\n")
    (rel_dir / "public_key.bin").write_bytes(pk)

    print("key id      :", key_id(pk))
    print("signature   : %d bytes" % len(signature))
    print("payload     :", payload_hex)
    print("wrote       :", signed_path, rel_dir / "payload.hex", rel_dir / "public_key.bin")
    print("NEVER commit keys/secret_key.bin. Back it up somewhere private.")


if __name__ == "__main__":
    main()

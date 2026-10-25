"""Phase 2: verify a signed release (runs LOCALLY, needs liboqs).

    python -m verify.verify_release --release-dir release --public-key keys/public_key.bin
    python -m verify.verify_release --release-dir release --public-key keys/public_key.bin --check-dataset

Use a public key you obtained SEPARATELY and trust (--public-key). The copy inside
release/ travels with the files, so an attacker could swap both together.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from crypto.manifest import bits_to_hex, canonical_bytes, payload_bits
from crypto.signing import ALG, key_id, verify


def verify_release(release_dir, public_key_path, check_dataset=False, cifar_root=None):
    """Return (ok, checks) where checks is a list of (name, passed, detail)."""
    checks = []

    def add(name, passed, detail=""):
        checks.append((name, bool(passed), detail))

    rd = Path(release_dir)
    try:
        signed = json.loads((rd / "signed_manifest.json").read_text())
        manifest = signed["manifest"]
        signature = bytes.fromhex(signed["signature_hex"])
        public_key = Path(public_key_path).read_bytes()
    except Exception as e:
        add("load release files", False, str(e))
        return False, checks
    add("load release files", True)

    try:
        add("key id matches manifest", manifest.get("key_id") == key_id(public_key),
            "manifest=%s key=%s" % (manifest.get("key_id"), key_id(public_key)))
        add("algorithm is " + ALG, manifest.get("signature_algorithm") == ALG)
        add("signature valid", verify(public_key, canonical_bytes(manifest), signature))
    except Exception as e:
        add("signature checks", False, str(e))

    try:
        expected = bits_to_hex(payload_bits(manifest))
        on_disk = (rd / "payload.hex").read_text().strip()
        add("payload.hex matches manifest", expected == on_disk)
    except Exception as e:
        add("payload.hex matches manifest", False, str(e))

    if check_dataset:
        try:
            from crypto.dataset import cifar10_train_root
            root = cifar10_train_root(cifar_root or os.environ.get("CIFAR_ROOT", "data"))
            add("dataset Merkle root matches manifest",
                root.hex() == manifest["dataset"]["merkle_root_sha256"])
        except Exception as e:
            add("dataset Merkle root matches manifest", False, str(e))

    return all(c[1] for c in checks), checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--public-key", default="keys/public_key.bin")
    ap.add_argument("--check-dataset", action="store_true")
    ap.add_argument("--cifar-root", default=os.environ.get("CIFAR_ROOT", "data"))
    args = ap.parse_args()

    ok, checks = verify_release(args.release_dir, args.public_key, args.check_dataset, args.cifar_root)
    for name, passed, detail in checks:
        print("%s  %s%s" % ("PASS" if passed else "FAIL", name, "" if passed or not detail else "  (" + detail + ")"))
    print("VERIFIED" if ok else "REJECTED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

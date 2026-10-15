import json
from datetime import datetime
from pathlib import Path

import sys
sys.path.append(".")

from crypto.hashing import sha256_file, sha256_directory
from crypto.ml_dsa import sign_message, verify_message


DEFAULT_MANIFEST_DIR = Path("results")


def get_manifest_dir(output_dir=None):

    directory = Path(output_dir) if output_dir is not None else DEFAULT_MANIFEST_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_manifest(
    dataset_name,
    dataset_path,
    model_name="Not trained",
    watermark_id=None,
    created_at=None
):

    dataset_path = Path(dataset_path)

    if dataset_path.is_file():
        dataset_hash = sha256_file(dataset_path)
    else:
        dataset_hash = sha256_directory(dataset_path)

    manifest = {
        "dataset_name": dataset_name,
        "dataset_path": str(dataset_path),
        "dataset_hash": dataset_hash,
        "hash_algorithm": "SHA-256",

        "model": model_name,

        "watermark_id": watermark_id,

        "signature_algorithm": "ML-DSA-65",

        "created_at": created_at or datetime.now().isoformat()
    }

    return manifest


def save_manifest(manifest, output_dir=None):

    manifest_dir = get_manifest_dir(output_dir)
    path = manifest_dir / "manifest.json"

    with open(path, "w") as f:
        json.dump(
            manifest,
            f,
            indent=4
        )

    return path


def sign_manifest(manifest, output_dir=None, key_dir=None):

    # Deterministic JSON representation
    data = json.dumps(
        manifest,
        sort_keys=True
    ).encode()

    signature = sign_message(data, key_dir=key_dir)

    manifest_dir = get_manifest_dir(output_dir)
    path = manifest_dir / "manifest.sig"

    with open(path, "wb") as f:
        f.write(signature)

    return path


def verify_manifest(manifest_path=None, signature_path=None, key_dir=None):

    manifest_dir = get_manifest_dir()
    manifest_path = Path(manifest_path) if manifest_path is not None else manifest_dir / "manifest.json"
    signature_path = Path(signature_path) if signature_path is not None else manifest_dir / "manifest.sig"

    with open(manifest_path, "rb") as f:
        manifest_data = f.read()

    with open(signature_path, "rb") as f:
        signature = f.read()

    valid = verify_message(manifest_data, signature, key_dir=key_dir)

    print(
        "Manifest:",
        "VALID" if valid else "INVALID"
    )

    return valid


if __name__ == "__main__":

    manifest = create_manifest(
        dataset_name="CIFAR-10",
        dataset_path="data/original",
        model_name="ResNet-18",
        watermark_id="PQAIP-001"
    )

    save_manifest(manifest)

    sign_manifest(manifest)

    verify_manifest()

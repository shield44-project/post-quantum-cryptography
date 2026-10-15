import hashlib
from pathlib import Path


def sha256_file(filepath):
    sha256 = hashlib.sha256()

    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha256.update(chunk)

    return sha256.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_directory(directory):
    """
    Creates one SHA-256 fingerprint for all files in a directory.
    Files are processed in sorted order.
    """

    directory = Path(directory)
    sha256 = hashlib.sha256()

    files = sorted(
        file for file in directory.rglob("*")
        if file.is_file()
    )

    for file in files:
        sha256.update(file.relative_to(directory).as_posix().encode())

        with open(file, "rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)

    return sha256.hexdigest()


if __name__ == "__main__":
    test_data = b"Post Quantum AI Provenance"

    print("SHA-256:")
    print(sha256_bytes(test_data))

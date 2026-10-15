from pathlib import Path

import oqs


ALGORITHM = "ML-DSA-65"

DEFAULT_KEY_DIR = Path("crypto/keys")


def get_key_dir(key_dir=None):

    directory = Path(key_dir) if key_dir is not None else DEFAULT_KEY_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def generate_keys(key_dir=None):

    key_dir = get_key_dir(key_dir)

    signer = oqs.Signature(ALGORITHM)

    public_key = signer.generate_keypair()
    secret_key = signer.export_secret_key()

    with open(key_dir / "public_key.bin", "wb") as f:
        f.write(public_key)

    with open(key_dir / "secret_key.bin", "wb") as f:
        f.write(secret_key)

    print("Keys generated")
    print("Algorithm:", ALGORITHM)
    print("Public key size:", len(public_key), "bytes")
    print("Secret key size:", len(secret_key), "bytes")


def load_keys(key_dir=None):

    key_dir = get_key_dir(key_dir)

    with open(key_dir / "public_key.bin", "rb") as f:
        public_key = f.read()

    with open(key_dir / "secret_key.bin", "rb") as f:
        secret_key = f.read()

    return public_key, secret_key


def sign_message(message, key_dir=None):

    public_key, secret_key = load_keys(key_dir=key_dir)

    signer = oqs.Signature(
        ALGORITHM,
        secret_key=secret_key
    )

    signature = signer.sign(message)

    return signature


def verify_message(message, signature, key_dir=None):

    key_dir = get_key_dir(key_dir)

    with open(key_dir / "public_key.bin", "rb") as f:
        public_key = f.read()

    verifier = oqs.Signature(ALGORITHM)

    return verifier.verify(
        message,
        signature,
        public_key
    )


def sign_file(filepath, key_dir=None):

    with open(filepath, "rb") as f:
        data = f.read()

    signature = sign_message(data, key_dir=key_dir)

    signature_file = str(filepath) + ".sig"

    with open(signature_file, "wb") as f:
        f.write(signature)

    print("Signature created:")
    print(signature_file)

    return signature


def verify_file(filepath, key_dir=None):

    signature_file = str(filepath) + ".sig"

    with open(filepath, "rb") as f:
        data = f.read()

    with open(signature_file, "rb") as f:
        signature = f.read()

    valid = verify_message(data, signature, key_dir=key_dir)

    print("Verification:", "VALID" if valid else "INVALID")

    return valid


if __name__ == "__main__":

    print("Generating ML-DSA-65 keys...")
    generate_keys()

    message = b"Hello Post Quantum AI"

    signature = sign_message(message)

    print("Signature size:", len(signature))

    result = verify_message(
        message,
        signature
    )

    print("Signature valid:", result)

    modified_message = b"Hello HACKED AI"

    result = verify_message(
        modified_message,
        signature
    )

    print("Modified message valid:", result)

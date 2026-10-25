"""ML-DSA-65 wrappers around liboqs-python (module name: oqs)  (Phase 2)."""
import hashlib

ALG = "ML-DSA-65"


def _oqs():
    import oqs  # imported lazily so other modules work without liboqs

    return oqs


def generate_keys():
    """Return (public_key, secret_key) as bytes."""
    oqs = _oqs()
    with oqs.Signature(ALG) as signer:
        public_key = signer.generate_keypair()
        secret_key = signer.export_secret_key()
    return public_key, secret_key


def sign(secret_key: bytes, message: bytes) -> bytes:
    oqs = _oqs()
    with oqs.Signature(ALG, secret_key) as signer:
        return signer.sign(message)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """True only for a valid signature. Any error (bad length, wrong key...) -> False."""
    try:
        oqs = _oqs()
        with oqs.Signature(ALG) as verifier:
            return bool(verifier.verify(message, signature, public_key))
    except Exception:
        return False


def key_id(public_key: bytes) -> str:
    """Short, public identifier of a key: first 32 hex chars of SHA-256(public key)."""
    return hashlib.sha256(public_key).hexdigest()[:32]

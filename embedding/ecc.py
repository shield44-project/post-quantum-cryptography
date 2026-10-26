"""Error-correcting codes for the watermark payload (Phase 4).

The payload (256 bits) is ENCODED into a longer codeword before embedding. At
extraction time the raw scores (logits = X @ v) are DECODED back to the payload.

    "none"     codeword = payload                         (Phase 3 behaviour)
    "rep{r}"   every payload bit written r times          rep2: 256 -> 512 bits
    "rs{p}"    Reed-Solomon over bytes, p parity bytes     rs32: 32 -> 64 bytes = 512 bits
               repairs e wrong bytes + f erased bytes as long as 2e + f <= p
               (the decoder erases at most p/2 bytes, see ReedSolomon.decode)

Soft decoding: decoders take the LOGITS, not 0/1 bits. A logit's sign is the bit,
its size is how sure we are. Repetition adds up the logits of the copies;
Reed-Solomon marks the least sure bytes as erasures, which cost half as much to
repair as errors. Bit order is MSB first, same as crypto.manifest.payload_bits.
"""
import numpy as np


def hard_bits(logits):
    """Phase 3 extraction rule: bit 1 if logit > 0, else 0."""
    return (np.asarray(logits, dtype=np.float64) > 0).astype(np.uint8)


def _check_bits(bits, n):
    b = np.asarray(bits, dtype=np.uint8).ravel()
    if b.size != n or b.max(initial=0) > 1:
        raise ValueError("expected %d bits of 0/1, got %d values" % (n, b.size))
    return b


def _check_logits(logits, n):
    z = np.asarray(logits, dtype=np.float64).ravel()
    if z.size != n:
        raise ValueError("expected %d logits, got %d" % (n, z.size))
    return z


def _result(ok, bits=None, corrected=0, erasures=0):
    return {"ok": ok, "bits": bits, "corrected": corrected, "erasures": erasures}


class NoCode:
    def __init__(self, k_bits):
        self.name, self.k_bits, self.n_bits = "none", k_bits, k_bits

    def encode(self, bits):
        return _check_bits(bits, self.k_bits).tolist()

    def decode(self, logits, soft=True):
        return _result(True, hard_bits(_check_logits(logits, self.n_bits)).tolist())


class Repetition:
    """Layout: [payload, payload, ...], r full copies one after another."""

    def __init__(self, k_bits, r):
        if r < 2:
            raise ValueError("repetition factor must be at least 2")
        self.name, self.k_bits, self.r, self.n_bits = "rep%d" % r, k_bits, r, k_bits * r

    def encode(self, bits):
        return np.tile(_check_bits(bits, self.k_bits), self.r).tolist()

    def decode(self, logits, soft=True):
        z = _check_logits(logits, self.n_bits).reshape(self.r, self.k_bits)
        if soft:
            bits = hard_bits(z.sum(axis=0))                        # confident copies outvote shaky ones
        else:
            bits = (2 * hard_bits(z).sum(axis=0) > self.r).astype(np.uint8)   # majority vote, tie -> 0
        corrected = int((hard_bits(z) != bits).sum())              # copies that lost the vote
        return _result(True, bits.tolist(), corrected)


class ReedSolomon:
    """RS over GF(256) via `reedsolo`. Codeword = data bytes followed by parity bytes."""

    def __init__(self, k_bits, parity_bytes):
        if k_bits % 8:
            raise ValueError("Reed-Solomon needs a payload that is a whole number of bytes")
        if k_bits // 8 + parity_bytes > 255:
            raise ValueError("Reed-Solomon over GF(256): data + parity must be at most 255 bytes")
        from reedsolo import RSCodec  # imported here so "none" / "rep" work without reedsolo

        self.rsc = RSCodec(parity_bytes)
        self.name, self.k_bits, self.parity = "rs%d" % parity_bytes, k_bits, parity_bytes
        self.n_bits = (k_bits // 8 + parity_bytes) * 8

    def encode(self, bits):
        data = np.packbits(_check_bits(bits, self.k_bits)).tobytes()
        return np.unpackbits(np.frombuffer(bytes(self.rsc.encode(data)), dtype=np.uint8)).tolist()

    def decode(self, logits, soft=True):
        """Try plain decoding first, then erase the 2, 4, ... least sure bytes until it works.

        At most parity/2 bytes are erased. Erasing all parity bytes would leave no
        redundancy, so ANY input (even pure noise) would "decode" and ok would mean nothing.
        """
        from reedsolo import ReedSolomonError

        z = _check_logits(logits, self.n_bits)
        received = np.packbits(hard_bits(z))
        sureness = np.abs(z).reshape(-1, 8).min(axis=1)            # a byte is as sure as its least sure bit
        order = np.argsort(sureness, kind="stable").tolist()       # least sure first
        for n_erase in range(0, self.parity // 2 + 1, 2) if soft else [0]:
            try:
                _, codeword, _ = self.rsc.decode(bytearray(received.tobytes()),
                                                 erase_pos=order[:n_erase] or None)
            except ReedSolomonError:
                continue
            fixed = np.frombuffer(bytes(codeword), dtype=np.uint8)
            return _result(True, np.unpackbits(fixed[: self.k_bits // 8]).tolist(),
                           int((fixed != received).sum()), n_erase)
        return _result(False)


def get_code(name, k_bits=256):
    if name == "none":
        return NoCode(k_bits)
    if name.startswith("rep"):
        return Repetition(k_bits, int(name[3:]))
    if name.startswith("rs"):
        return ReedSolomon(k_bits, int(name[2:]))
    raise ValueError("unknown code %r (use none, rep<r> or rs<parity bytes>)" % name)

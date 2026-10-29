"""Signing lab: show ML-DSA-65 on any text with a throwaway key pair (never the project's real keys).

    python -m pqctl.actions.sign_lab --message "hello" --check "hello"
    python -m pqctl.actions.sign_lab --message "hello" --check "hellp"
"""
import argparse
import hashlib
import time

from pqctl.actions import emit, run_main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", required=True)
    ap.add_argument("--check", default=None, help="the text the verifier receives (default: the same message)")
    args = ap.parse_args()

    from crypto.signing import ALG, generate_keys, key_id, sign, verify

    check = args.message if args.check is None else args.check
    t0 = time.perf_counter()
    pk, sk = generate_keys()
    t1 = time.perf_counter()
    sig = sign(sk, args.message.encode("utf-8"))
    t2 = time.perf_counter()
    ok = verify(pk, check.encode("utf-8"), sig)
    t3 = time.perf_counter()
    print("algorithm : %s (NIST FIPS 204), fresh throwaway key pair" % ALG)
    print("public key: %d bytes, key id %s" % (len(pk), key_id(pk)))
    print("secret key: %d bytes (never shown)" % len(sk))
    print("signature : %d bytes" % len(sig))
    print("signed    : %r" % args.message)
    print("checked   : %r" % check)
    print("timing    : keygen %.1f ms, sign %.1f ms, verify %.1f ms" % (1e3 * (t1 - t0), 1e3 * (t2 - t1), 1e3 * (t3 - t2)))
    print("VERIFIED" if ok else "REJECTED")
    emit({"alg": ALG, "pk_bytes": len(pk), "sk_bytes": len(sk), "sig_bytes": len(sig), "key_id": key_id(pk),
          "pk_hex": pk[:48].hex(), "sig_hex": sig[:96].hex(), "message": args.message, "check": check,
          "sha_message": hashlib.sha256(args.message.encode()).hexdigest(), "sha_check": hashlib.sha256(check.encode()).hexdigest(),
          "ok": bool(ok), "ms": {"keygen": round(1e3 * (t1 - t0), 2), "sign": round(1e3 * (t2 - t1), 2), "verify": round(1e3 * (t3 - t2), 2)}})
    return 0


if __name__ == "__main__":
    run_main(main)

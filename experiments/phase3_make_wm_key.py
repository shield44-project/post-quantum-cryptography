"""Phase 3: create the secret watermark key (runs LOCALLY, once).

    python -m experiments.phase3_make_wm_key

Writes keys/watermark_key.bin (32 random bytes). This key decides WHERE the watermark
lives (it generates the projection matrix). Share it only with trusted auditors.
It is NOT the ML-DSA key. keys/ is git-ignored; back this file up privately.
"""
import argparse
import os
import secrets
import sys
from pathlib import Path

from embedding.keys import key_fingerprint


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="keys/watermark_key.bin")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    p = Path(args.path)
    if p.exists() and not args.force:
        sys.exit("%s exists. Overwriting it makes every watermark made with the old key unreadable. Use --force only if you mean it." % p)
    p.parent.mkdir(exist_ok=True)
    key = secrets.token_bytes(32)
    p.write_bytes(key)
    os.chmod(p, 0o600)
    print("wrote", p, "| fingerprint", key_fingerprint(key), "(safe to write down; it does not reveal the key)")


if __name__ == "__main__":
    main()

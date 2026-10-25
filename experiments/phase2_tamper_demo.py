"""Phase 2 'done when' demo: every tampering must flip the result to REJECTED.

    python -m experiments.phase2_tamper_demo
"""
import json
import shutil
import tempfile
from pathlib import Path

from crypto.signing import generate_keys
from verify.verify_release import verify_release

REL, PK = Path("release"), Path("keys/public_key.bin")


def case(name, mutate, public_key_path=PK):
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(REL, tmp / "release")
    mutate(tmp / "release")
    ok, _ = verify_release(tmp / "release", public_key_path)
    shutil.rmtree(tmp)
    return name, ok


def edit_manifest(fn):
    def run(rd):
        p = rd / "signed_manifest.json"
        d = json.loads(p.read_text())
        fn(d)
        p.write_text(json.dumps(d, indent=2, sort_keys=True))
    return run


def flip_signature(d):
    s = d["signature_hex"]
    d["signature_hex"] = ("0" if s[0] != "0" else "1") + s[1:]


def flip_root(d):
    r = d["manifest"]["dataset"]["merkle_root_sha256"]
    d["manifest"]["dataset"]["merkle_root_sha256"] = ("0" if r[0] != "0" else "1") + r[1:]


def edit_payload(rd):
    p = rd / "payload.hex"
    t = p.read_text().strip()
    p.write_text(("0" if t[0] != "0" else "1") + t[1:] + "\n")


def main():
    other_pk, _ = generate_keys()
    other = Path(tempfile.mkdtemp()) / "other_pk.bin"
    other.write_bytes(other_pk)

    results = [
        case("untouched release (expect VERIFIED)", lambda rd: None),
        case("developer_id edited", edit_manifest(lambda d: d["manifest"].__setitem__("developer_id", "mallory"))),
        case("one dataset root character changed", edit_manifest(flip_root)),
        case("model width edited", edit_manifest(lambda d: d["manifest"]["model"].__setitem__("width", 64))),
        case("one signature character changed", edit_manifest(flip_signature)),
        case("payload.hex edited", edit_payload),
        case("wrong public key", lambda rd: None, public_key_path=other),
    ]
    for name, ok in results:
        print("%-45s -> %s" % (name, "VERIFIED" if ok else "REJECTED"))
    first_ok = results[0][1]
    rest_rejected = all(not ok for _, ok in results[1:])
    print("\nDONE-WHEN CHECK:", "PASSED" if first_ok and rest_rejected else "FAILED")


if __name__ == "__main__":
    main()

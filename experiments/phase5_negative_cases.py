"""Phase 5 'done when' check (runs LOCALLY, needs liboqs): each negative case must be REJECTED for the
right reason, and both our own model and Mallory's own model must be VERIFIED.

    python -m experiments.phase5_negative_cases --seeds 0 1 2                    # Phase 4 rs32 models (default)
    python -m experiments.phase5_negative_cases --seeds 0 1 2 \
        --model-pattern "runs/wm_v1/lam20_n256_rs16/seed{seed}/model.pt"         # another Phase 4 run
    python -m experiments.phase5_negative_cases --seeds 0 1 2 --n-bits 32 --allow-short \
        --model-pattern "runs/wm_v0/lam1_n32/seed{seed}/model.pt" \
        --mallory-model mallory/runs/standin_lam5_n32/seed1/model.pt             # legacy 32-bit Phase 3 models

Tampered copies, wrong keys etc. live in a temporary folder; nothing is written to release/ or runs/.
"""
import argparse
import json
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

from crypto.signing import generate_keys
from verify.verify_model import resolve_settings, verify_model

NO_WATERMARK = ("watermark read", "extracted payload")   # failing here = "this watermark is not in the model"


def first_failure(checks):
    for name, passed, detail in checks:
        if not passed:
            return name, detail
    return None, ""


def run_cases(seed, args, tmp):
    ours = args.model_pattern.format(seed=seed)
    base = args.baseline_pattern.format(seed=seed)
    m_dir = Path(args.mallory_dir)
    mine = dict(public_key_path=args.public_key, wm_key_path=args.wm_key, release_dir=args.release_dir)
    mallory = dict(public_key_path=m_dir / "keys" / "public_key.bin", wm_key_path=m_dir / "keys" / "watermark_key.bin",
                   release_dir=m_dir / "release")
    s, _ = resolve_settings(ours, args.ecc, args.n_bits)          # our settings, also used for the baseline
    ours_s = {k: s[k] for k in ("ecc", "n_bits", "layer", "mode")}

    wrong_pk = tmp / "wrong_public_key.bin"
    wrong_pk.write_bytes(generate_keys()[0])
    wrong_wm = tmp / "wrong_watermark_key.bin"
    wrong_wm.write_bytes(secrets.token_bytes(32))
    tampered = tmp / "tampered_release"
    if not tampered.exists():
        shutil.copytree(args.release_dir, tampered)
        p = tampered / "signed_manifest.json"
        d = json.loads(p.read_text())
        d["manifest"]["developer_id"] = "mallory"
        p.write_text(json.dumps(d, indent=2, sort_keys=True))

    cases = [  # (name, model, files, settings, expected verdict, acceptable failing checks)
        ("own model + own files", ours, mine, ours_s, True, None),
        ("wrong public key", ours, dict(mine, public_key_path=wrong_pk), ours_s, False, ("key id matches manifest",)),
        ("wrong watermark key", ours, dict(mine, wm_key_path=wrong_wm), ours_s, False, NO_WATERMARK),
        ("tampered manifest (developer_id)", ours, dict(mine, release_dir=tampered), ours_s, False, ("signature valid",)),
        ("unmarked baseline model", base, mine, ours_s, False, NO_WATERMARK),
        ("Mallory's model + OUR files", args.mallory_model, mine, {}, False, NO_WATERMARK),
        ("our model + MALLORY's files", ours, mallory, ours_s, False, NO_WATERMARK),
        ("Mallory's model + Mallory's files", args.mallory_model, mallory, {}, True, None),
    ]
    rows = []
    for name, model, files, settings, expect_ok, reasons in cases:
        ok, checks, _ = verify_model(model, ecc=settings.get("ecc"), n_bits=settings.get("n_bits"),
                                     layer=settings.get("layer"), mode=settings.get("mode"),
                                     allow_short=args.allow_short, **files)
        fail, detail = first_failure(checks)
        right = (ok == expect_ok) and (reasons is None or any(fail.startswith(r) for r in reasons))
        rows.append((name, expect_ok, ok, fail, detail, right))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--model-pattern", default="runs/wm_v1/lam20_n256_rs32/seed{seed}/model.pt")
    ap.add_argument("--baseline-pattern", default="runs/baseline/seed{seed}/model.pt")
    ap.add_argument("--mallory-dir", default="mallory")
    ap.add_argument("--mallory-model", default="mallory/runs/lam20_n256_rs32/seed3/model.pt")
    ap.add_argument("--public-key", default="keys/public_key.bin")
    ap.add_argument("--wm-key", default="keys/watermark_key.bin")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--ecc", default=None)
    ap.add_argument("--n-bits", type=int, default=None)
    ap.add_argument("--allow-short", action="store_true",
                    help="needed for legacy 32-bit (Phase 3) models; weaker proof")
    args = ap.parse_args()

    if args.allow_short:
        print("NOTE: --allow-short is on, models embedding fewer bits than the manifest signs are accepted")
    all_right = True
    with tempfile.TemporaryDirectory() as t:
        for seed in args.seeds:
            rows = run_cases(seed, args, Path(t))
            print("\nseed %d  (our model: %s)" % (seed, args.model_pattern.format(seed=seed)))
            print(" %-34s | %-8s | %-8s | %-30s | %-24s | right reason"
                  % ("case", "expected", "got", "first failing check", "detail"))
            for name, expect_ok, ok, fail, detail, right in rows:
                print(" %-34s | %-8s | %-8s | %-30s | %-24s | %s" % (
                    name, "VERIFIED" if expect_ok else "REJECTED", "VERIFIED" if ok else "REJECTED",
                    "-" if fail is None else fail[:30], (detail or "-")[:24], "yes" if right else "NO"))
                all_right &= right
    print("\nDONE-WHEN (4 negative cases rejected, own model passes): %s" % ("PASSED" if all_right else "FAILED"))
    sys.exit(0 if all_right else 1)


if __name__ == "__main__":
    main()

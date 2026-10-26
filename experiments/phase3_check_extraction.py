"""Phase 3 'done when' checks (runs LOCALLY on CPU).

    python -m experiments.phase3_check_extraction \
        --model runs/wm_v0/lam1_n32/seed0/model.pt \
        --baseline-model runs/baseline/seed0/model.pt --n-bits 32

Prints: bit errors with the right key, with 50 random wrong keys, and on an unmarked
baseline model, plus the chance that random bits would pass.
"""
import argparse
import secrets

from embedding.extract import load_smallcnn, report
from embedding.keys import false_accept_probability, load_key, load_payload_bits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--baseline-model", default=None)
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--n-bits", type=int, default=32)
    ap.add_argument("--layer", default="features.6.0.weight")
    ap.add_argument("--mode", choices=["mean", "full"], default="mean")
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--payload", default="release/payload.hex")
    args = ap.parse_args()

    key = load_key(args.key)
    payload = load_payload_bits(args.payload, args.n_bits)
    model = load_smallcnn(args.model, args.width)

    r = report(model, key, args.layer, payload, args.mode)
    print("1) watermarked model, right key : %d/%d bit errors (BER %.3f), min|logit| %.2f, mean|logit| %.2f"
          % (r["bit_errors"], args.n_bits, r["ber"], r["min_abs_logit"], r["mean_abs_logit"]))

    bers = [report(model, secrets.token_bytes(32), args.layer, payload, args.mode)["ber"] for _ in range(50)]
    print("2) watermarked model, 50 wrong keys: BER min %.3f / mean %.3f / max %.3f (expect about 0.5)"
          % (min(bers), sum(bers) / len(bers), max(bers)))

    if args.baseline_model:
        base = load_smallcnn(args.baseline_model, args.width)
        rb = report(base, key, args.layer, payload, args.mode)
        print("3) UNMARKED baseline, right key : %d/%d bit errors (BER %.3f) (expect about 0.5)"
              % (rb["bit_errors"], args.n_bits, rb["ber"]))

    print("\nChance random bits match with 0 errors   : %.2e" % false_accept_probability(args.n_bits, 0))
    print("Chance random bits match with <=%d errors : %.2e" % (args.n_bits // 8, false_accept_probability(args.n_bits, args.n_bits // 8)))
    ok = r["bit_errors"] == 0
    print("\nDONE-WHEN (0 bit errors on the clean model):", "PASSED" if ok else "NOT YET")


if __name__ == "__main__":
    main()

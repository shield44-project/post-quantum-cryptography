"""Phase 7, task P7.1: gather every finished watermark run into ONE table (no training, no liboqs).

    python -m experiments.phase7.collect_runs
    python -m experiments.phase7.collect_runs --roots runs/wm_v1 runs/wm_v1_payload --out results/phase7

Reads   runs/<root>/<run name>/seed<N>/final.json   (written by training/train_watermarked.py)
        runs/baseline/seed<N>/final.json            (written by training/train_baseline.py)
Writes  results/phase7/wm_runs.csv        one row per trained model
        results/phase7/wm_config_summary.csv   one row per (ecc, n_bits, layer, lam), mean +- std over seeds
Accuracy differences are PAIRED: watermarked seed N minus baseline seed N (same as experiments/run_phase4.py).
"""
import argparse
import json
import statistics as st
from pathlib import Path

import pandas as pd


def load_baselines(baseline_dir):
    """{seed: test accuracy} from runs/baseline/seed*/final.json."""
    out = {}
    for f in sorted(Path(baseline_dir).glob("seed*/final.json")):
        d = json.loads(f.read_text())
        out[int(d["seed"])] = float(d["test_acc"])
    return out


def load_runs(roots, baselines):
    rows = []
    for root in roots:
        for f in sorted(Path(root).glob("*/seed*/final.json")):
            d = json.loads(f.read_text())
            if "lam" not in d:                      # not a watermark run (e.g. an attack folder)
                continue
            seed = int(d["seed"])
            base = baselines.get(seed)
            rows.append({
                "root": str(root), "run": f.parent.parent.name, "seed": seed,
                "lam": d["lam"], "n_bits": d["n_bits"], "ecc": d["ecc"],
                "codeword_bits": d["codeword_bits"], "layer": d["layer"], "mode": d.get("mode", "mean"),
                "epochs": d.get("epochs"), "acc": d["final_test_acc"], "base_acc": base,
                "acc_diff": None if base is None else d["final_test_acc"] - base,
                "raw_bit_errors": d["bit_errors"], "raw_ber": d["ber"],
                "decoded_ok": bool(d["decoded_ok"]), "decoded_errors": d["decoded_errors"],
                "min_margin": d["min_abs_logit"], "train_seconds": d.get("seconds"),
            })
    return pd.DataFrame(rows)


def summarize(df):
    keys = ["ecc", "n_bits", "codeword_bits", "layer", "lam"]
    out = []
    for k, g in df.groupby(keys, sort=True):
        diffs = g["acc_diff"].dropna().tolist()
        out.append({
            **dict(zip(keys, k)),
            "seeds": ",".join(str(s) for s in sorted(g["seed"])),
            "n_runs": len(g),
            "mean_acc": g["acc"].mean(),
            "mean_diff": st.mean(diffs) if diffs else None,
            "std_diff": st.stdev(diffs) if len(diffs) > 1 else None,
            "raw_errors_total": int(g["raw_bit_errors"].sum()),
            "decoded_errors_total": int(g["decoded_errors"].sum()),
            "all_decoded": bool(g["decoded_ok"].all() and (g["decoded_errors"] == 0).all()),
            "min_margin": g["min_margin"].min(),
        })
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", default=["runs/wm_v1"])
    ap.add_argument("--baseline-dir", default="runs/baseline")
    ap.add_argument("--out", default="results/phase7")
    args = ap.parse_args()

    baselines = load_baselines(args.baseline_dir)
    print("baseline seeds found:", {s: round(a, 4) for s, a in baselines.items()})
    df = load_runs(args.roots, baselines)
    if df.empty:
        raise SystemExit("no watermark runs found under %s" % args.roots)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "wm_runs.csv", index=False)
    summ = summarize(df)
    summ.to_csv(out / "wm_config_summary.csv", index=False)

    pd.set_option("display.width", 200, "display.max_columns", 30)
    show = summ.copy()
    for c in ("mean_acc", "mean_diff", "std_diff"):
        show[c] = show[c].map(lambda v: "n/a" if pd.isna(v) else "%.4f" % v)
    show["min_margin"] = show["min_margin"].map(lambda v: "%.2f" % v)
    print(show.to_string(index=False))
    print("\nwrote %s and %s (%d runs, %d configs)" % (out / "wm_runs.csv", out / "wm_config_summary.csv", len(df), len(summ)))


if __name__ == "__main__":
    main()

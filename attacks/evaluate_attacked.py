"""Stage B: verify every attacked model with your Phase 5 verifier (LOCAL, needs liboqs).

    python -m attacks.evaluate_attacked --jobs 3

Reads  runs/attacks/**/attack.json, writes verify.json next to each model and one table:
results/phase6/attack_results.csv.  Finished models are skipped, so you can run it again after adding more attacks.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from attacks.measure import Probe, run_verifier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="runs/attacks")
    ap.add_argument("--clean-model", default="runs/wm_v1/lam20_n256_rs32/seed{seed}/model.pt")
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--csv", default="results/phase6/attack_results.csv")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    metas = sorted(Path(args.root).glob("*/seed*/*/rep*/attack.json"))
    print("%d attacked models found" % len(metas))

    # one probe per model seed, built from the clean watermarked model
    probes = {}
    for seed in sorted({json.loads(p.read_text())["seed"] for p in metas}):
        clean = Path(args.clean_model.format(seed=seed))
        if clean.exists():
            rep = run_verifier(clean)
            probes[seed] = Probe.from_clean(clean, rep, args.key)
            print("seed %d: clean verdict %s | probe %s (%s)" % (seed, rep["verdict"], "on" if probes[seed].enabled else "off", probes[seed].reason))

    def work(meta_path):
        d = meta_path.parent
        out = d / "verify.json"
        if out.exists() and not args.force:
            return
        meta = json.loads(meta_path.read_text())
        rep = run_verifier(d / "model.pt")
        pr = probes.get(meta["seed"])
        rep["flip_rate"] = pr.flip_rate(d / "model.pt") if pr is not None else None
        rep.pop("checks", None)
        out.write_text(json.dumps(rep, indent=2))
        print("%-9s seed%d %-26s rep%d -> %s" % (meta["source"], meta["seed"], meta["attack_id"], meta["rep"], rep["verdict"]), flush=True)

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        list(ex.map(work, metas))

    rows = []
    for p in metas:
        v = p.parent / "verify.json"
        if not v.exists():
            continue
        row = json.loads(p.read_text())
        row["params"] = json.dumps(row["params"], sort_keys=True)
        rep = json.loads(v.read_text())
        for k in ("verdict", "wm_read", "payload_match", "min_margin", "corrected", "erasures", "flip_rate"):
            row[k] = rep.get(k)
        rows.append(row)
    df = pd.DataFrame(rows)
    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.csv, index=False)
    print("wrote %s (%d rows)" % (args.csv, len(df)))


if __name__ == "__main__":
    main()

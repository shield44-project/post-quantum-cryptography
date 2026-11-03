"""Phase 7, task P7.4: the naive sign-based scheme as a comparison baseline (runs LOCALLY on CPU, ~40 min).

    python -m experiments.phase7.naive_baseline                     # build, attack, read, write the table
    python -m experiments.phase7.naive_baseline --seeds 0 --quick   # 1 seed, a few attacks (~3 min)

The project's first design (skill section 2, flaw 2): bit = 1 if a chosen weight is > 0. Here it is built as fairly
as possible, so the comparison isolates the EMBEDDING and nothing else:
  - same carrier layer (features.6.0.weight), same 256-bit signed payload, same rs32 codeword (512 values),
  - 512 weight positions chosen by SHAKE-256 from the same secret watermark key,
  - embedding: set the sign of each chosen weight to its codeword bit (|w| kept), applied to the trained BASELINE
    models (no retraining, as a naive developer would do),
  - reading: the 512 weights are the soft values; same soft Reed-Solomon decoding,
  - same decision rule as verify_model: exact payload -> VERIFIED, >= 358/512 agreement -> DAMAGED, else REJECTED.
Then the same Phase 6 / 6b weight attacks (attacks/make_attacked.py: apply_attack) are applied to both schemes.
Writes results/phase7/naive_vs_projection.csv. The projection scheme's numbers are read from results/phase6b.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from attacks import registry
from attacks.common import device, evaluate, load_model, seed_everything, stable_seed, test_loader
from attacks.make_attacked import apply_attack
from crypto.manifest import payload_bits
from embedding.align import agreement, evidence_threshold
from embedding.ecc import get_code
from embedding.keys import load_key

LAYER = "features.6.0.weight"
SCHEME = "naive-sign-v0"
QUICK = ["none", "noise_all_s0.1", "prune_global_0.5", "quant_pt_4", "permute_out_carrier", "permute_in_carrier"]


def positions(key, n, numel):
    """n distinct weight positions in the flattened carrier, from SHAKE-256(key | scheme | layer)."""
    stream = hashlib.shake_256(key + b"|" + SCHEME.encode() + b"|" + LAYER.encode()).digest(8 * n * 4)
    idx = np.frombuffer(stream, dtype=">u8") % numel
    out, seen = [], set()
    for i in idx.tolist():
        if i not in seen:
            seen.add(i)
            out.append(i)
            if len(out) == n:
                return np.array(out)
    raise RuntimeError("not enough distinct positions")


def embed(model, pos, codeword):
    w = dict(model.named_parameters())[LAYER]
    with torch.no_grad():
        flat = w.view(-1)
        s = torch.tensor(2.0 * np.asarray(codeword) - 1.0, dtype=flat.dtype)
        flat[pos] = flat[pos].abs().clamp_min(1e-8) * s       # sign = codeword bit, magnitude kept
    return model


def read(model, pos, code, codeword, expected, need):
    z = dict(model.named_parameters())[LAYER].detach().reshape(-1)[pos].double().numpy()
    d = code.decode((z / max(np.abs(z).max(), 1e-12)).tolist())
    k = agreement(z, codeword)
    verdict = "VERIFIED" if d["ok"] and d["bits"] == expected else ("DAMAGED" if k >= need else "REJECTED")
    return verdict, k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--quick", action="store_true", help="only a few attacks, for a smoke test")
    ap.add_argument("--out", default="results/phase7/naive_vs_projection.csv")
    args = ap.parse_args()

    manifest = json.loads((Path(args.release_dir) / "signed_manifest.json").read_text())["manifest"]
    code = get_code("rs32", 256)
    expected = payload_bits(manifest, 256)
    codeword = code.encode(expected)
    need = evidence_threshold(code.n_bits)
    key = load_key(args.key)
    dev = device()
    test = test_loader(args.data_root)
    # one draw per random attack (the projection scheme had 3; its rates are averaged per attack below)
    cfgs = [c for c in registry.select(cost="cheap") if not args.quick or c["id"] in QUICK]
    print("%d cheap attacks x %d seeds | %s vs projection (results/phase6b)" % (len(cfgs), len(args.seeds), SCHEME))

    rows = []
    for seed in args.seeds:
        base = load_model("runs/baseline/seed%d/model.pt" % seed)
        pos = positions(key, code.n_bits, dict(base.named_parameters())[LAYER].numel())
        base_acc = evaluate(base, test, dev)
        unmarked_verdict, unmarked_k = read(base, pos, code, codeword, expected, need)
        marked = embed(load_model("runs/baseline/seed%d/model.pt" % seed), pos, codeword)
        clean_acc = evaluate(marked, test, dev)
        print("\nseed %d: baseline acc %.4f (read as unmarked: %s, %d/512) -> naive-marked acc %.4f (cost %+.2f pts)"
              % (seed, base_acc, unmarked_verdict, unmarked_k, clean_acc, 100 * (clean_acc - base_acc)), flush=True)
        rows.append({"scheme": "naive", "seed": seed, "attack_id": "unmarked baseline", "family": "control",
                     "verdict": unmarked_verdict, "agree": unmarked_k, "acc": base_acc, "acc_drop": 0.0})
        for cfg in cfgs:
            s = stable_seed("naive", seed, cfg["id"], 0)
            seed_everything(s)
            t0 = time.time()
            attacked, _ = apply_attack(cfg, marked, s, LAYER, dev, args.data_root)
            acc = evaluate(attacked, test, dev)
            verdict, k = read(attacked, pos, code, codeword, expected, need)
            rows.append({"scheme": "naive", "seed": seed, "attack_id": cfg["id"], "family": cfg["family"],
                         "verdict": verdict, "agree": k, "acc": acc, "acc_drop": clean_acc - acc})
            print("  %-26s %-9s agree %3d/512  acc %.4f  %.0fs" % (cfg["id"], verdict, k, acc, time.time() - t0), flush=True)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(args.out, index=False)          # after every seed: an interrupted run keeps its work
        print("saved %s (%d rows so far)" % (args.out, len(rows)), flush=True)
    print("\nwrote %s (%d rows)" % (args.out, len(rows)))


if __name__ == "__main__":
    main()

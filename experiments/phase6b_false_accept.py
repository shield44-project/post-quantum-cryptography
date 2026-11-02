"""Phase 6b: false-accept stress test for the permutation / scaling defence (runs LOCALLY on CPU, no liboqs).

    python -m experiments.phase6b_false_accept                    # ~5-10 min
    python -m experiments.phase6b_false_accept --wrong-keys 50 --random-models 20      # quick

The verifier now also tries re-aligned and re-scaled readings of the carrier (embedding/align.py) and accepts any that
decodes EXACTLY to the signed payload. That extra search must never make a model that does not carry our codeword pass.
Null cases, every one read with our signed codeword and the rs32 settings:
  - wrong key   : our real watermarked models read with random watermark keys (a marked model, but not this key)
  - baseline    : the unmarked baseline models, also after a random permutation and random x10 scaling
  - mallory     : Mallory's model (her own watermark)
  - random init : freshly initialised SmallCNNs
For each case: does any candidate reading decode exactly (must be 0), and the raw agreement used by the DAMAGED rule
(must stay below its 2^-64 threshold). Writes results/phase6b/false_accept.csv and prints a summary.
"""
import argparse
import json
import math
import secrets
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from crypto.manifest import payload_bits
from embedding.align import agreement, candidate_readouts, evidence_threshold
from embedding.ecc import get_code
from embedding.extract import load_smallcnn
from embedding.keys import load_key
from embedding.projection import ProjectionWatermark, carrier_vector, get_weight
from training.model import SmallCNN

LAYER = "features.6.0.weight"


def scramble(model, seed):
    """Random input-channel permutation + x10 positive scaling of the carrier (function-preserving)."""
    from attacks.common import carrier_block_index, conv_blocks
    from attacks.weight_attacks import permute_channels
    m = permute_channels(model, "in_carrier", seed, LAYER)
    k = carrier_block_index(m, LAYER)
    bn, conv = conv_blocks(m)[k - 1][1], conv_blocks(m)[k][0]
    s = torch.exp((torch.rand(conv.in_channels, generator=torch.Generator().manual_seed(seed)) * 2 - 1) * math.log(10))
    with torch.no_grad():
        bn.weight.mul_(s)
        bn.bias.mul_(s)
        conv.weight.div_(s.view(1, -1, 1, 1))
    return m


def read(model, key, code, codeword, expected):
    w = get_weight(model, LAYER)
    wm = ProjectionWatermark(key, LAYER, code.n_bits, "mean", w.shape)
    X = wm.matrix().astype(np.float64)
    v = carrier_vector(w.detach(), "mean").double().numpy()
    raw_agree, accepted_by = agreement(X @ v, codeword), None
    for label, _, vv in candidate_readouts(X, v, codeword, w.shape):
        d = code.decode((X @ vv).tolist())
        if d["ok"] and d["bits"] == expected:
            accepted_by = label
            break
    return raw_agree, accepted_by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrong-keys", type=int, default=200, help="random keys per watermarked model")
    ap.add_argument("--random-models", type=int, default=100)
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--out", default="results/phase6b/false_accept.csv")
    args = ap.parse_args()

    manifest = json.loads((Path(args.release_dir) / "signed_manifest.json").read_text())["manifest"]
    code = get_code("rs32", 256)
    expected = payload_bits(manifest, 256)
    codeword = code.encode(expected)
    ours = load_key(args.key)
    need = evidence_threshold(code.n_bits)

    cases = []        # (group, name, model, key)
    for s in (0, 1, 2):
        m = load_smallcnn("runs/wm_v1/lam20_n256_rs32/seed%d/model.pt" % s)
        cases += [("wrong key", "wm seed%d key%d" % (s, i), m, secrets.token_bytes(32)) for i in range(args.wrong_keys)]
    for s in (0, 1, 2):
        b = load_smallcnn("runs/baseline/seed%d/model.pt" % s)
        cases += [("baseline", "seed%d" % s, b, ours)] + [("baseline scrambled", "seed%d r%d" % (s, r), scramble(b, 100 + r), ours)
                                                          for r in range(5)]
    mal = Path("mallory/runs/lam20_n256_rs32/seed3/model.pt")
    if mal.exists():
        mm = load_smallcnn(str(mal))
        cases += [("mallory", "seed3", mm, ours)] + [("mallory scrambled", "r%d" % r, scramble(mm, 200 + r), ours) for r in range(5)]
    for i in range(args.random_models):
        torch.manual_seed(10_000 + i)
        cases.append(("random init", "init%d" % i, SmallCNN(width=32).eval(), ours))

    rows = []
    for n, (group, name, model, key) in enumerate(cases, 1):
        raw_agree, by = read(model, key, code, codeword, expected)
        rows.append({"group": group, "case": name, "raw_agree": raw_agree, "evidence": raw_agree >= need, "accepted_by": by or ""})
        if n % 100 == 0:
            print("%d / %d cases" % (n, len(cases)), flush=True)
    df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    g = df.groupby("group", sort=False).agg(cases=("case", "size"), exact_accepts=("accepted_by", lambda x: int((x != "").sum())),
                                           damaged_verdicts=("evidence", "sum"), max_raw_agree=("raw_agree", "max"),
                                           mean_raw_agree=("raw_agree", "mean")).reset_index()
    pd.set_option("display.width", 200)
    print(g.to_string(index=False, float_format=lambda x: "%.1f" % x))
    bad = int((df["accepted_by"] != "").sum()) + int(df["evidence"].sum())
    print("\nDAMAGED threshold %d of %d. Worst raw agreement on any null case: %d." % (need, code.n_bits, df["raw_agree"].max()))
    print("DONE-WHEN (0 false VERIFIED, 0 false DAMAGED over %d null cases): %s" % (len(df), "PASSED" if bad == 0 else "FAILED"))
    print("wrote", args.out)


if __name__ == "__main__":
    main()

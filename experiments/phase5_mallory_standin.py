"""Phase 5: a cheap STAND-IN Mallory model for the negative-case suite (runs LOCALLY on CPU, ~2 to 5 min).

    python -m experiments.phase5_mallory_standin --data-root data

Fine-tunes OUR baseline seed 1 for one epoch with CE + lam * BCE, embedding Mallory's payload with
Mallory's watermark key (Phase 3 style: ecc none, 32 bits, features.6.0.weight, mean). It stands
for "a model watermarked by someone else". The real Mallory model is trained in the Phase 4
config once Phase 4 is finished (train_watermarked.py with --key/--payload pointing at mallory/).
"""
import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from embedding.ecc import get_code
from embedding.extract import load_smallcnn
from embedding.keys import key_fingerprint, load_key, load_payload_bits
from embedding.projection import ProjectionWatermark, get_weight
from training.seed import set_seed
from training.train_watermarked import evaluate, make_loaders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="runs/baseline/seed1/model.pt")
    ap.add_argument("--key", default="mallory/keys/watermark_key.bin")
    ap.add_argument("--payload", default="mallory/release/payload.hex")
    ap.add_argument("--data-root", default="data")
    ap.add_argument("--lam", type=float, default=5.0)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--n-bits", type=int, default=32)
    ap.add_argument("--ecc", default="none")
    ap.add_argument("--layer", default="features.6.0.weight")
    ap.add_argument("--mode", default="mean")
    ap.add_argument("--out", default="mallory/runs/standin_lam5_n32/seed1")
    args = ap.parse_args()

    set_seed(1)
    key = load_key(args.key)
    payload = load_payload_bits(args.payload, args.n_bits)
    code = get_code(args.ecc, args.n_bits)
    codeword = code.encode(payload)
    target = torch.tensor(codeword, dtype=torch.float32)
    model = load_smallcnn(args.start)
    wm = ProjectionWatermark(key, args.layer, code.n_bits, args.mode, get_weight(model, args.layer).shape)
    train_loader, test_loader = make_loaders(args.data_root, 128)
    opt = torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, nesterov=True, weight_decay=5e-4)

    t0 = time.time()
    model.train()
    for x, y in train_loader:
        loss = F.cross_entropy(model(x), y) + args.lam * wm.loss(model, target)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    acc = evaluate(model, test_loader, "cpu")
    got, logits = wm.extract(model)
    errors = sum(int(a != b) for a, b in zip(got, codeword))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")
    final = {"STAND_IN": True,
             "note": "Mallory stand-in: our baseline seed1 fine-tuned 1 epoch with Mallory's key and payload. "
                     "Not a from-scratch model; for the Phase 5 negative-case suite only.",
             "start": args.start, "epochs": 1, "lam": args.lam, "lr": args.lr, "n_bits": args.n_bits,
             "ecc": args.ecc, "codeword_bits": code.n_bits, "layer": args.layer, "mode": args.mode, "width": 32,
             "final_test_acc": acc, "bit_errors": errors, "min_abs_logit": min(abs(z) for z in logits),
             "key_fingerprint": key_fingerprint(key), "seconds": time.time() - t0}
    (out / "final.json").write_text(json.dumps(final, indent=2))
    print("acc %.4f | bit errors %d/%d | min|logit| %.2f | %.0f s | saved %s"
          % (acc, errors, code.n_bits, final["min_abs_logit"], final["seconds"], out))


if __name__ == "__main__":
    main()

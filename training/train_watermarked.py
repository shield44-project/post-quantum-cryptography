"""Phase 3/4: train SmallCNN with the projection watermark  (runs on COLAB, GPU).

    python -m training.train_watermarked --seed 0 --epochs 30 --lam 1.0 --n-bits 32                  # Phase 3
    python -m training.train_watermarked --seed 0 --epochs 30 --lam 1.0 --n-bits 256 --ecc rs32      # Phase 4

Total_Loss = CrossEntropy + lam * BCE(sigmoid(X @ v), codeword_bits)
codeword = ECC-encoded first n_bits of the payload (with --ecc none it is the payload itself).

Same recipe as the baseline: SGD lr 0.05, momentum 0.9, Nesterov, wd 5e-4,
cosine annealing over the epochs, batch 128, final-epoch metrics only.
Needs: release/payload.hex and keys/watermark_key.bin (NOT the ML-DSA secret key).
"""
import argparse
import csv
import json
import os
import time
from pathlib import Path

import torch
import torch.nn.functional as F
import torchvision
import torchvision.transforms as T
from torch.utils.data import DataLoader

from embedding.ecc import get_code
from embedding.keys import key_fingerprint, load_key, load_payload_bits
from embedding.projection import ProjectionWatermark, get_weight
from training.model import SmallCNN
from training.seed import set_seed

MEAN, STD = (0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)
DEFAULT_LAYER = "features.6.0.weight"


def run_dir(out_root, lam, n_bits, ecc, layer, seed):
    """Phase 3 runs keep their old names (lam1_n32); ECC and a non-default layer extend the name."""
    name = "lam%g_n%d" % (lam, n_bits)
    if ecc != "none":
        name += "_" + ecc
    if layer != DEFAULT_LAYER:
        name += "_" + layer.replace(".weight", "")
    return Path(out_root) / name / ("seed%d" % seed)


def make_loaders(root, batch_size, workers=2):
    train_tf = T.Compose([T.RandomCrop(32, padding=4), T.RandomHorizontalFlip(),
                          T.ToTensor(), T.Normalize(MEAN, STD)])
    test_tf = T.Compose([T.ToTensor(), T.Normalize(MEAN, STD)])
    train = torchvision.datasets.CIFAR10(root, train=True, download=True, transform=train_tf)
    test = torchvision.datasets.CIFAR10(root, train=False, download=True, transform=test_tf)
    return (DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=workers, pin_memory=True),
            DataLoader(test, batch_size=256, shuffle=False, num_workers=workers, pin_memory=True))


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    correct = total = 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        correct += (model(x).argmax(1) == y).sum().item()
        total += y.numel()
    return correct / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lam", type=float, default=1.0)
    ap.add_argument("--n-bits", type=int, default=32, help="payload bits to embed (prefix of payload.hex)")
    ap.add_argument("--ecc", default="none", help="none, rep<r> or rs<parity bytes>, see embedding/ecc.py")
    ap.add_argument("--layer", default=DEFAULT_LAYER)
    ap.add_argument("--mode", choices=["mean", "full"], default="mean")
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--payload", default="release/payload.hex")
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--data-root", default=os.environ.get("CIFAR_ROOT", "data"))
    ap.add_argument("--out-root", default="runs/wm_v0")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = run_dir(args.out_root, args.lam, args.n_bits, args.ecc, args.layer, args.seed)
    if (out / "final.json").exists() and not args.force:
        print("already finished, skipping:", out)
        return
    out.mkdir(parents=True, exist_ok=True)

    set_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    key = load_key(args.key)
    payload = load_payload_bits(args.payload, args.n_bits)
    code = get_code(args.ecc, args.n_bits)
    codeword = code.encode(payload)
    bits = torch.tensor(codeword, dtype=torch.float32, device=device)

    model = SmallCNN(width=args.width).to(device)
    num_params = sum(p.numel() for p in model.parameters())
    wm = ProjectionWatermark(key, args.layer, code.n_bits, args.mode, get_weight(model, args.layer).shape)
    print("params %d | layer %s %s | carrier dim %d | payload %d bits | ecc %s -> %d embedded bits | lam %g | device %s"
          % (num_params, args.layer, tuple(get_weight(model, args.layer).shape), wm.dim, args.n_bits,
             args.ecc, code.n_bits, args.lam, device))

    train_loader, test_loader = make_loaders(args.data_root, args.batch_size)
    opt = torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, nesterov=True, weight_decay=5e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    with open(out / "metrics.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "loss_cls", "loss_wm", "test_acc", "bit_errors", "ber", "min_abs_logit", "seconds",
                    "decoded_errors"])
        t0 = time.time()
        for epoch in range(1, args.epochs + 1):
            model.train()
            s_cls = s_wm = 0.0
            n = 0
            for x, y in train_loader:
                x, y = x.to(device), y.to(device)
                loss_cls = F.cross_entropy(model(x), y)
                loss_wm = wm.loss(model, bits)
                loss = loss_cls + args.lam * loss_wm
                opt.zero_grad(set_to_none=True)
                loss.backward()
                opt.step()
                s_cls += loss_cls.item() * y.numel()
                s_wm += loss_wm.item() * y.numel()
                n += y.numel()
            sched.step()

            acc = evaluate(model, test_loader, device)
            got, logits = wm.extract(model)
            errors = sum(int(a != b) for a, b in zip(got, codeword))          # raw, before ECC
            dec = code.decode(logits)
            dec_errors = (sum(int(a != b) for a, b in zip(dec["bits"], payload))
                          if dec["ok"] else args.n_bits)                     # failed decode counts as all wrong
            row = [epoch, s_cls / n, s_wm / n, acc, errors, errors / code.n_bits,
                   min(abs(z) for z in logits), time.time() - t0, dec_errors]
            w.writerow(row)
            f.flush()
            print("ep %2d  cls %.3f  wm %.4f  acc %.4f  bit_errors %d/%d  decoded %d/%d  min|logit| %.2f"
                  % (epoch, row[1], row[2], acc, errors, code.n_bits, dec_errors, args.n_bits, row[6]))

    torch.save(model.state_dict(), out / "model.pt")
    final = {"seed": args.seed, "epochs": args.epochs, "lam": args.lam, "n_bits": args.n_bits,
             "ecc": args.ecc, "codeword_bits": code.n_bits,
             "layer": args.layer, "mode": args.mode, "width": args.width, "num_params": num_params,
             "final_test_acc": acc, "bit_errors": errors, "ber": errors / code.n_bits,
             "decoded_ok": dec["ok"], "decoded_errors": dec_errors,
             "min_abs_logit": row[6], "payload_bits": "".join(map(str, payload)),
             "key_fingerprint": key_fingerprint(key), "seconds": time.time() - t0}
    (out / "final.json").write_text(json.dumps(final, indent=2))
    print("saved", out)


if __name__ == "__main__":
    main()

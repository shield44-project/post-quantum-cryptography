import argparse
import csv
import json
import time
from pathlib import Path

import torch
import torch.nn as nn

from training.data import get_loaders
from training.model import SmallCNN
from training.seed import set_seed


def evaluate(model, loader, device):
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            correct += (model(x).argmax(dim=1) == y).sum().item()
            total += y.size(0)
    return correct / total


def train_one_epoch(model, loader, optimizer, criterion, device):
    model.train()
    loss_sum, correct, total = 0.0, 0, 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        loss_sum += loss.item() * y.size(0)
        correct += (out.argmax(dim=1) == y).sum().item()
        total += y.size(0)
    return loss_sum / total, correct / total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--weight-decay", type=float, default=5e-4)
    parser.add_argument("--out-dir", type=str, default="runs/baseline")
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = Path(args.out_dir) / f"seed{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)

    train_loader, test_loader = get_loaders(batch_size=args.batch_size, seed=args.seed)

    model = SmallCNN(width=args.width).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"device={device}  params={n_params}  seed={args.seed}")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(
        model.parameters(), lr=args.lr, momentum=0.9,
        nesterov=True, weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    start = time.time()
    with open(out_dir / "metrics.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["epoch", "train_loss", "train_acc", "test_acc", "seconds"])
        for epoch in range(1, args.epochs + 1):
            train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, criterion, device)
            test_acc = evaluate(model, test_loader, device)
            scheduler.step()
            elapsed = time.time() - start
            writer.writerow([epoch, f"{train_loss:.4f}", f"{train_acc:.4f}", f"{test_acc:.4f}", f"{elapsed:.0f}"])
            f.flush()
            print(f"epoch {epoch:3d}/{args.epochs}  loss {train_loss:.3f}  "
                  f"train {train_acc:.3f}  test {test_acc:.3f}  ({elapsed:.0f}s)")

    torch.save(model.state_dict(), out_dir / "model.pt")

    final = {
        "seed": args.seed,
        "test_acc": evaluate(model, test_loader, device),
        "params": n_params,
        "train_seconds": round(time.time() - start),
        "torch_version": torch.__version__,
        "device": str(device),
        "config": vars(args),
    }
    with open(out_dir / "final.json", "w") as f:
        json.dump(final, f, indent=2)
    print(f"final test accuracy: {final['test_acc']:.4f}")


if __name__ == "__main__":
    main()

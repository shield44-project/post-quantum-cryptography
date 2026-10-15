from pathlib import Path

import torch
from torchvision.models import resnet18

from model.watermark import detect_watermark


DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)
MODEL_PATH = Path("results/resnet18_watermarked.pth")


def main(model_path=MODEL_PATH, watermark="PQAIP-RVCE-2026-001"):
    model_path = Path(model_path)

    model = resnet18(weights=None, num_classes=10)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model = model.to(DEVICE)

    score = detect_watermark(model, watermark)
    print(f"Watermark detection accuracy: {score * 100:.2f}%")

    if score >= 0.90:
        print("✓ WATERMARK DETECTED")
    else:
        print("✗ WATERMARK NOT DETECTED")

    return score


if __name__ == "__main__":
    main()

from pathlib import Path

import torch
from torchvision.models import resnet18

from model.watermark import embed_watermark


DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


MODEL_PATH = Path("results/resnet18_original.pth")
OUTPUT_PATH = Path("results/resnet18_watermarked.pth")


def main(model_path=MODEL_PATH, output_path=OUTPUT_PATH, watermark="PQAIP-RVCE-2026-001"):
    model_path = Path(model_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = resnet18(weights=None, num_classes=10)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model = model.to(DEVICE)
    model = embed_watermark(model, watermark)

    torch.save(model.state_dict(), output_path)
    print("Watermarked model saved:")
    print(output_path)
    return output_path


if __name__ == "__main__":
    main()

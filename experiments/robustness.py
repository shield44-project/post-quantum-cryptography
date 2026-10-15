import torch

from torchvision.models import resnet18

from model.watermark import detect_watermark


DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


MODEL = (
    "results/resnet18_watermarked.pth"
)


WATERMARK = (
    "PQAIP-RVCE-2026-001"
)


def load_model(model_path=MODEL):

    model_path = model_path

    model = resnet18(
        weights=None,
        num_classes=10
    )

    model.load_state_dict(
        torch.load(
            model_path,
            map_location=DEVICE
        )
    )

    return model.to(DEVICE)


def prune_model(
    model,
    percentage
):

    with torch.no_grad():

        for param in model.parameters():

            flat = param.view(-1)

            n = int(
                len(flat)
                * percentage
                / 100
            )

            indices = torch.randperm(
                len(flat)
            )[:n]

            flat[indices] = 0

    return model


def test(model_path=MODEL, watermark=WATERMARK):

    model = load_model(model_path)

    score = detect_watermark(
        model,
        watermark
    )

    print(
        "Original:",
        score
    )

    for percentage in [
        10,
        20,
        30
    ]:

        model = load_model(model_path)

        model = prune_model(
            model,
            percentage
        )

        score = detect_watermark(
            model,
            watermark
        )

        print(
            f"{percentage}% pruning:",
            score
        )


if __name__ == "__main__":
    test()

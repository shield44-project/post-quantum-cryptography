import torch

from torchvision import datasets
from torchvision import transforms
from torchvision.models import resnet18

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score
)


DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


def evaluate(model_path):

    transform = transforms.Compose([
        transforms.ToTensor(),

        transforms.Normalize(
            (0.4914, 0.4822, 0.4465),
            (0.2470, 0.2435, 0.2616)
        )
    ])

    dataset = datasets.CIFAR10(
        root="data",
        train=False,
        download=True,
        transform=transform
    )

    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=128,
        shuffle=False
    )

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

    model = model.to(DEVICE)

    model.eval()

    predictions = []
    actual = []

    with torch.no_grad():

        for images, labels in loader:

            images = images.to(DEVICE)

            outputs = model(images)

            preds = outputs.argmax(1).cpu()

            predictions.extend(
                preds.numpy()
            )

            actual.extend(
                labels.numpy()
            )

    print(
        "Accuracy:",
        accuracy_score(
            actual,
            predictions
        )
    )

    print(
        "Precision:",
        precision_score(
            actual,
            predictions,
            average="macro"
        )
    )

    print(
        "Recall:",
        recall_score(
            actual,
            predictions,
            average="macro"
        )
    )

    print(
        "F1:",
        f1_score(
            actual,
            predictions,
            average="macro"
        )
    )


if __name__ == "__main__":

    evaluate(
        "results/resnet18_original.pth"
    )

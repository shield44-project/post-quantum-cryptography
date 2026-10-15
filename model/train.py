import torch
import torch.nn as nn
import torch.optim as optim

from torchvision import datasets
from torchvision import transforms
from torchvision.models import resnet18

from pathlib import Path


DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


BATCH_SIZE = 128
EPOCHS = 10
LEARNING_RATE = 0.001


def get_data():

    transform = transforms.Compose([
        transforms.ToTensor(),

        transforms.Normalize(
            (0.4914, 0.4822, 0.4465),
            (0.2470, 0.2435, 0.2616)
        )
    ])

    train_dataset = datasets.CIFAR10(
        root="data",
        train=True,
        download=True,
        transform=transform
    )

    test_dataset = datasets.CIFAR10(
        root="data",
        train=False,
        download=True,
        transform=transform
    )

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=2
    )

    test_loader = torch.utils.data.DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=2
    )

    return train_loader, test_loader


def create_model():

    model = resnet18(
        weights=None,
        num_classes=10
    )

    return model.to(DEVICE)


def train():

    train_loader, test_loader = get_data()

    model = create_model()

    criterion = nn.CrossEntropyLoss()

    optimizer = optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE
    )

    for epoch in range(EPOCHS):

        model.train()

        running_loss = 0

        correct = 0
        total = 0

        for images, labels in train_loader:

            images = images.to(DEVICE)
            labels = labels.to(DEVICE)

            optimizer.zero_grad()

            outputs = model(images)

            loss = criterion(
                outputs,
                labels
            )

            loss.backward()

            optimizer.step()

            running_loss += loss.item()

            _, predicted = outputs.max(1)

            total += labels.size(0)

            correct += (
                predicted == labels
            ).sum().item()

        accuracy = 100 * correct / total

        print(
            f"Epoch {epoch + 1}/{EPOCHS}"
        )

        print(
            f"Loss: {running_loss:.3f}"
        )

        print(
            f"Train Accuracy: {accuracy:.2f}%"
        )

    Path("results").mkdir(
        exist_ok=True
    )

    torch.save(
        model.state_dict(),
        "results/resnet18_original.pth"
    )

    print("Model saved.")


if __name__ == "__main__":
    train()

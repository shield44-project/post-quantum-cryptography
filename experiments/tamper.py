import random
from pathlib import Path

import torch
from torchvision import datasets


DATA_DIR = Path("data")

DATA_DIR.mkdir(exist_ok=True)


def download_cifar():

    dataset = datasets.CIFAR10(
        root=DATA_DIR,
        train=True,
        download=True
    )

    return dataset


def create_tampered_dataset(
    dataset,
    percentage,
    output_file
):

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    data = dataset.data.copy()
    labels = dataset.targets.copy()

    n = len(data)

    number_to_modify = int(
        n * percentage / 100
    )

    indices = random.sample(
        range(n),
        number_to_modify
    )

    for idx in indices:

        original_label = labels[idx]

        new_label = random.randint(0, 9)

        while new_label == original_label:
            new_label = random.randint(0, 9)

        labels[idx] = new_label

    torch.save(
        {
            "data": torch.tensor(data),
            "labels": torch.tensor(labels)
        },
        output_file
    )

    print(
        f"Created {percentage}% tampered dataset"
    )

    print(
        f"Modified samples: {number_to_modify}"
    )

    return output_file


def run(percentages=(1, 5, 10), output_dir=DATA_DIR / "tampered"):

    dataset = download_cifar()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for percentage in percentages:
        output_file = output_dir / f"cifar_{percentage}_percent.pt"
        results.append(
            create_tampered_dataset(
                dataset,
                percentage,
                output_file
            )
        )

    return results


if __name__ == "__main__":
    run()


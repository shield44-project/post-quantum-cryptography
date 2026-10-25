import os

import torch
import torchvision
import torchvision.transforms as T
from torch.utils.data import DataLoader

CIFAR_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR_STD = (0.2470, 0.2435, 0.2616)


def get_loaders(batch_size: int = 128, num_workers: int = 2, seed: int = 42):
    root = os.environ.get("CIFAR_ROOT", "data")

    train_tf = T.Compose([
        T.RandomCrop(32, padding=4),
        T.RandomHorizontalFlip(),
        T.ToTensor(),
        T.Normalize(CIFAR_MEAN, CIFAR_STD),
    ])
    test_tf = T.Compose([
        T.ToTensor(),
        T.Normalize(CIFAR_MEAN, CIFAR_STD),
    ])

    train_set = torchvision.datasets.CIFAR10(root=root, train=True, download=True, transform=train_tf)
    test_set = torchvision.datasets.CIFAR10(root=root, train=False, download=True, transform=test_tf)

    generator = torch.Generator()
    generator.manual_seed(seed)

    pin = torch.cuda.is_available()
    train_loader = DataLoader(
        train_set, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, generator=generator, pin_memory=pin,
    )
    test_loader = DataLoader(
        test_set, batch_size=256, shuffle=False,
        num_workers=num_workers, pin_memory=pin,
    )
    return train_loader, test_loader

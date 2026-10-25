import torch.nn as nn


def conv_block(cin: int, cout: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(cin, cout, kernel_size=3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
    )


class SmallCNN(nn.Module):
    def __init__(self, width: int = 32, num_classes: int = 10):
        super().__init__()
        w = width
        self.features = nn.Sequential(
            conv_block(3, w), conv_block(w, w), nn.MaxPool2d(2),
            conv_block(w, 2 * w), conv_block(2 * w, 2 * w), nn.MaxPool2d(2),
            conv_block(2 * w, 4 * w), nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.3),
            nn.Linear(4 * w * 4 * 4, num_classes),
        )

    def forward(self, x):
        return self.classifier(self.features(x))

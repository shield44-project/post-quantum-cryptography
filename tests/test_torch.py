import torch
import torchvision
import torchvision.transforms as T

print("torch:", torch.__version__)
print("GPU available:", torch.cuda.is_available())

x = torch.randn(2, 3)
print("tensor math works:", (x @ x.T).shape)

dataset = torchvision.datasets.CIFAR10(root="data", train=True, download=True, transform=T.ToTensor())
print("CIFAR-10 training images:", len(dataset))
image, label = dataset[0]
print("image shape:", tuple(image.shape), "label:", label)
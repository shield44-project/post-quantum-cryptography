from __future__ import annotations

import io
import json
import random
import shutil
import statistics
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

try:
    import torch
    from torchvision import datasets, transforms
    from torchvision.models import resnet18
except Exception:  # pragma: no cover - handled at runtime with a user-facing message
    torch = None
    datasets = None
    transforms = None
    resnet18 = None

from crypto.hashing import sha256_directory, sha256_file
from crypto.ml_dsa import generate_keys, sign_message, verify_message
from model.watermark import detect_watermark, embed_watermark


@dataclass(slots=True)
class WorkflowPaths:
    workspace_root: Path
    data_dir: Path
    results_dir: Path
    keys_dir: Path
    models_dir: Path


class PQAIService:
    CIFAR10_CLASSES = (
        "airplane",
        "automobile",
        "bird",
        "cat",
        "deer",
        "dog",
        "frog",
        "horse",
        "ship",
        "truck",
    )

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path.home() / ".pqai_provenance")
        self.paths = WorkflowPaths(
            workspace_root=self.base_dir,
            data_dir=self.base_dir / "data",
            results_dir=self.base_dir / "results",
            keys_dir=self.base_dir / "keys",
            models_dir=self.base_dir / "models",
        )

        for path in self.paths.__dict__.values():
            path.mkdir(parents=True, exist_ok=True)

    def _require_ml_stack(self) -> None:
        if torch is None or datasets is None or transforms is None or resnet18 is None:
            raise RuntimeError(
                "PyTorch and Torchvision are required for model training and image testing. "
                "Install the project dependencies before using model actions."
            )

    def _dataset_hash(self, dataset_path: Path) -> tuple[str, int]:
        if dataset_path.is_file():
            return sha256_file(dataset_path), 1

        file_count = sum(1 for item in dataset_path.rglob("*") if item.is_file())
        return sha256_directory(dataset_path), file_count

    def ensure_keys(self) -> Path:
        public_key = self.paths.keys_dir / "public_key.bin"
        secret_key = self.paths.keys_dir / "secret_key.bin"

        if not public_key.exists() or not secret_key.exists():
            generate_keys(key_dir=self.paths.keys_dir)

        return self.paths.keys_dir

    def _image_transform(self) -> transforms.Compose:
        self._require_ml_stack()
        return transforms.Compose(
            [
                transforms.Resize((32, 32)),
                transforms.ToTensor(),
                transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
            ]
        )

    def _load_cifar_model(self, model_path: str | Path, device: str) -> torch.nn.Module:
        self._require_ml_stack()
        model_path = Path(model_path).expanduser().resolve()
        checkpoint = torch.load(model_path, map_location=device)

        if isinstance(checkpoint, dict):
            state_dict = checkpoint
            for key in ("state_dict", "model_state_dict", "model"):
                nested = checkpoint.get(key)
                if isinstance(nested, dict):
                    state_dict = nested
                    break
        else:
            state_dict = checkpoint

        model = resnet18(weights=None, num_classes=10)
        model.load_state_dict(state_dict)
        return model.to(device).eval()

    def predict_image(
        self,
        model_path: str | Path,
        image_path: str | Path,
        top_k: int = 3,
    ) -> dict[str, Any]:
        model_path = Path(model_path).expanduser().resolve()
        image_path = Path(image_path).expanduser().resolve()
        self._require_ml_stack()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        image = Image.open(image_path).convert("RGB")
        tensor = self._image_transform()(image).unsqueeze(0).to(device)
        model = self._load_cifar_model(model_path, device)

        with torch.no_grad():
            logits = model(tensor)
            probabilities = torch.softmax(logits, dim=1)[0]

        top_k = max(1, min(top_k, probabilities.numel()))
        values, indices = torch.topk(probabilities, k=top_k)
        predictions = [
            {
                "rank": rank + 1,
                "class_index": int(index.item()),
                "class_name": self.CIFAR10_CLASSES[int(index.item())],
                "confidence": float(value.item()),
            }
            for rank, (value, index) in enumerate(zip(values, indices, strict=True))
        ]

        return {
            "model_path": str(model_path),
            "image_path": str(image_path),
            "predicted_class": predictions[0]["class_name"],
            "predicted_class_index": predictions[0]["class_index"],
            "confidence": predictions[0]["confidence"],
            "top_k": predictions,
        }

    def predict_cifar10_sample(
        self,
        model_path: str | Path,
        data_root: str | Path | None = None,
        sample_index: int | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        data_root = Path(data_root or self.paths.data_dir).expanduser().resolve()
        self._require_ml_stack()
        dataset = datasets.CIFAR10(root=data_root, train=False, download=True, transform=None)

        if not len(dataset):
            raise ValueError("CIFAR-10 test dataset is empty")

        if sample_index is None:
            sample_index = random.randrange(len(dataset))

        sample_index = sample_index % len(dataset)
        image, true_label = dataset[sample_index]
        preview_path = self.paths.results_dir / "cifar10_sample_preview.png"
        image.save(preview_path)

        prediction = self.predict_image(model_path, preview_path, top_k=top_k)
        prediction.update(
            {
                "sample_index": sample_index,
                "true_class_index": int(true_label),
                "true_class_name": self.CIFAR10_CLASSES[int(true_label)],
                "preview_path": str(preview_path),
            }
        )
        return prediction

    def predict_image_batch(
        self,
        model_path: str | Path,
        image_paths: list[str | Path],
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for image_path in image_paths:
            try:
                result = self.predict_image(model_path, image_path, top_k=top_k)
                result["status"] = "ok"
            except Exception as error:
                result = {
                    "model_path": str(Path(model_path).expanduser().resolve()),
                    "image_path": str(Path(image_path).expanduser().resolve()),
                    "status": "error",
                    "error": str(error),
                }
            results.append(result)

        return results

    def create_manifest(
        self,
        dataset_name: str,
        dataset_path: str | Path,
        model_name: str = "ResNet-18",
        watermark_id: str | None = None,
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        dataset_path = Path(dataset_path).expanduser().resolve()
        output_dir = Path(output_dir).expanduser().resolve() if output_dir else self.paths.results_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        dataset_hash, file_count = self._dataset_hash(dataset_path)
        manifest = {
            "schema_version": "1.0",
            "dataset_name": dataset_name,
            "dataset_path": str(dataset_path),
            "dataset_hash": dataset_hash,
            "dataset_file_count": file_count,
            "hash_algorithm": "SHA-256",
            "model": model_name,
            "watermark_id": watermark_id,
            "signature_algorithm": "ML-DSA-65",
            "created_at": datetime.now().isoformat(),
        }

        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        self.ensure_keys()
        signature = sign_message(
            json.dumps(manifest, sort_keys=True).encode("utf-8"),
            key_dir=self.paths.keys_dir,
        )
        signature_path = output_dir / "manifest.sig"
        signature_path.write_bytes(signature)

        verified = verify_message(
            json.dumps(manifest, sort_keys=True).encode("utf-8"),
            signature,
            key_dir=self.paths.keys_dir,
        )

        manifest["manifest_path"] = str(manifest_path)
        manifest["signature_path"] = str(signature_path)
        manifest["signature_valid"] = verified
        return manifest

    def verify_manifest(
        self,
        manifest_path: str | Path,
        signature_path: str | Path,
    ) -> bool:
        manifest_bytes = Path(manifest_path).read_bytes()
        signature = Path(signature_path).read_bytes()
        self.ensure_keys()
        return verify_message(manifest_bytes, signature, key_dir=self.paths.keys_dir)

    def train_model(
        self,
        data_root: str | Path | None = None,
        epochs: int = 1,
        batch_size: int = 64,
        learning_rate: float = 0.001,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        data_root = Path(data_root or self.paths.data_dir).expanduser().resolve()
        output_path = Path(output_path or (self.paths.models_dir / "resnet18_original.pth")).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._require_ml_stack()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
            ]
        )

        train_dataset = datasets.CIFAR10(root=data_root, train=True, download=True, transform=transform)
        train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)

        model = resnet18(weights=None, num_classes=10).to(device)
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

        epoch_summaries: list[dict[str, Any]] = []

        for epoch in range(epochs):
            model.train()
            running_loss = 0.0
            correct = 0
            total = 0

            print(f"Epoch {epoch + 1}/{epochs}")

            for images, labels in train_loader:
                images = images.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()
                outputs = model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                running_loss += loss.item()
                predicted = outputs.argmax(1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

            accuracy = 100.0 * correct / total if total else 0.0
            print(f"Loss: {running_loss:.3f}")
            print(f"Train Accuracy: {accuracy:.2f}%")

            epoch_summaries.append(
                {
                    "epoch": epoch + 1,
                    "loss": running_loss,
                    "accuracy": accuracy,
                }
            )

        torch.save(model.state_dict(), output_path)
        print(f"Model saved to {output_path}")

        return {
            "device": device,
            "output_path": str(output_path),
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "history": epoch_summaries,
        }

    def evaluate_model(
        self,
        model_path: str | Path,
        data_root: str | Path | None = None,
        batch_size: int = 128,
    ) -> dict[str, Any]:
        data_root = Path(data_root or self.paths.data_dir).expanduser().resolve()
        model_path = Path(model_path).expanduser().resolve()

        self._require_ml_stack()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
            ]
        )

        dataset = datasets.CIFAR10(root=data_root, train=False, download=True, transform=transform)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False)

        model = resnet18(weights=None, num_classes=10)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model = model.to(device)
        model.eval()

        predictions: list[int] = []
        actual: list[int] = []

        with torch.no_grad():
            for images, labels in loader:
                images = images.to(device)
                outputs = model(images)
                preds = outputs.argmax(1).cpu()
                predictions.extend(preds.numpy().tolist())
                actual.extend(labels.numpy().tolist())

        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

        metrics = {
            "accuracy": accuracy_score(actual, predictions),
            "precision": precision_score(actual, predictions, average="macro", zero_division=0),
            "recall": recall_score(actual, predictions, average="macro", zero_division=0),
            "f1": f1_score(actual, predictions, average="macro", zero_division=0),
            "model_path": str(model_path),
            "data_root": str(data_root),
        }

        print(f"Accuracy: {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall: {metrics['recall']:.4f}")
        print(f"F1: {metrics['f1']:.4f}")
        return metrics

    def embed_watermark(
        self,
        model_path: str | Path,
        watermark_text: str,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        model_path = Path(model_path).expanduser().resolve()
        output_path = Path(output_path or self.paths.models_dir / "resnet18_watermarked.pth").expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._require_ml_stack()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = resnet18(weights=None, num_classes=10)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model = model.to(device)
        model = embed_watermark(model, watermark_text)
        torch.save(model.state_dict(), output_path)

        print(f"Watermarked model saved to {output_path}")
        return {
            "model_path": str(model_path),
            "output_path": str(output_path),
            "watermark_text": watermark_text,
        }

    def check_watermark(
        self,
        model_path: str | Path,
        watermark_text: str,
    ) -> dict[str, Any]:
        model_path = Path(model_path).expanduser().resolve()

        self._require_ml_stack()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = resnet18(weights=None, num_classes=10)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model = model.to(device)
        score = detect_watermark(model, watermark_text)

        print(f"Watermark detection accuracy: {score * 100:.2f}%")
        return {
            "model_path": str(model_path),
            "watermark_text": watermark_text,
            "detection_rate": score,
        }

    def create_tampered_dataset(
        self,
        percentage: float,
        output_path: str | Path,
        data_root: str | Path | None = None,
    ) -> dict[str, Any]:
        data_root = Path(data_root or self.paths.data_dir).expanduser().resolve()
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._require_ml_stack()

        dataset = datasets.CIFAR10(root=data_root, train=True, download=True)
        data = dataset.data.copy()
        labels = dataset.targets.copy()
        total = len(data)
        number_to_modify = int(total * percentage / 100)
        indices = random.sample(range(total), number_to_modify)

        for index in indices:
            original_label = labels[index]
            new_label = random.randint(0, 9)
            while new_label == original_label:
                new_label = random.randint(0, 9)
            labels[index] = new_label

        torch.save({"data": torch.tensor(data), "labels": torch.tensor(labels)}, output_path)
        print(f"Created {percentage}% tampered dataset at {output_path}")
        return {
            "data_root": str(data_root),
            "output_path": str(output_path),
            "percentage": percentage,
            "modified_samples": number_to_modify,
        }

    def benchmark_signature(self, runs: int = 20) -> dict[str, Any]:
        from crypto.benchmark import benchmark

        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            benchmark(runs=runs)
        output = buffer.getvalue()
        print(output.rstrip())
        return {"runs": runs, "output": output}

    def run_robustness_test(
        self,
        model_path: str | Path,
        watermark_text: str,
        prune_percentages: tuple[int, ...] = (10, 20, 30),
    ) -> dict[str, Any]:
        model_path = Path(model_path).expanduser().resolve()
        self._require_ml_stack()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        scores: list[dict[str, Any]] = []

        def _load_model() -> torch.nn.Module:
            model = resnet18(weights=None, num_classes=10)
            model.load_state_dict(torch.load(model_path, map_location=device))
            return model.to(device)

        def _prune_model(model: torch.nn.Module, percentage: int) -> torch.nn.Module:
            with torch.no_grad():
                for param in model.parameters():
                    flat = param.view(-1)
                    count = int(len(flat) * percentage / 100)
                    indices = torch.randperm(len(flat))[:count]
                    flat[indices] = 0
            return model

        original_model = _load_model()
        original_score = detect_watermark(original_model, watermark_text)
        scores.append({"percentage": 0, "score": original_score})
        print(f"Original: {original_score:.4f}")

        for percentage in prune_percentages:
            pruned_model = _prune_model(_load_model(), percentage)
            score = detect_watermark(pruned_model, watermark_text)
            scores.append({"percentage": percentage, "score": score})
            print(f"{percentage}% pruning: {score:.4f}")

        return {
            "model_path": str(model_path),
            "watermark_text": watermark_text,
            "scores": scores,
        }

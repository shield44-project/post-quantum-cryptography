---
name: mlexperiments
description: Build, train, evaluate, and reproduce PyTorch computer vision experiments using CIFAR-10 and ResNet-18. Use for model training, dataset preparation, metrics, checkpoints, reproducibility, and tampering experiments.
---

# PyTorch ML Experiments Skill

## Project context

PQ-AI Provenance uses machine-learning experiments to evaluate how dataset tampering affects model performance and how model watermarks behave under model modifications.

The baseline model is ResNet-18 trained on CIFAR-10 using PyTorch and Torchvision.

## Dataset handling

- Use supported Torchvision dataset APIs and documented download mechanisms.
- Keep dataset storage outside application source files and packaged executables.
- Separate training, validation, and test datasets.
- Apply augmentation to training data only unless an experiment explicitly requires otherwise.
- Use consistent normalization and preprocessing during training and evaluation.
- Set and document random seeds where reproducibility is required.
- Avoid downloading datasets again when valid local copies already exist.
- Report dataset size, class distribution, transformations, and split configuration.

## Training workflow

1. Validate the dataset and configuration.
2. Initialize the model and select the device.
3. Configure the optimizer, loss function, and learning-rate schedule.
4. Train for the configured number of epochs.
5. Evaluate on the appropriate validation or test set.
6. Save model checkpoints and experiment metadata.
7. Export results in a structured format.

## Reproducibility

- Use configurable seeds for Python, NumPy, and PyTorch where applicable.
- Configure deterministic operations when supported, and document performance trade-offs.
- Record model architecture, hyperparameters, package versions, dataset fingerprint, device, and training configuration.
- Do not claim that a seed guarantees bit-for-bit reproducibility across all hardware and library versions.
- Store checkpoints and outputs in user-configurable data directories.

## Evaluation metrics

Report metrics appropriate to the task, including:
- Accuracy
- Precision
- Recall
- F1 score
- Confusion matrix
- Training duration and inference duration when relevant

Specify the averaging method for precision, recall, and F1 in multiclass experiments. Avoid evaluating a model on training data and presenting the result as generalization performance.

## Dataset tampering experiments

Support controlled experiments at configurable rates, initially 1%, 5%, and 10%.

- Preserve the original dataset.
- Generate separate tampered copies or reproducible tampering configurations.
- Record which samples and labels were changed.
- Clearly define whether tampering means label changes, image modifications, file replacement, or another operation.
- Use identical baseline settings when comparing conditions.
- Record the actual number and percentage of modified samples.
- Compare performance against the unmodified baseline.
- Never silently modify the original dataset.

## Code quality

- Separate dataset loading, training, evaluation, checkpoint management, and experiment orchestration.
- Support CPU execution and detect CUDA availability safely.
- Avoid hardcoded machine-specific paths.
- Report errors clearly, including insufficient memory, corrupted data, and unavailable devices.
- Keep training configuration separate from GUI code.

## Validation

Test dataset loading, model initialization, metric calculations, checkpoint save/load, and tampering-rate calculations. Use small synthetic datasets for fast automated tests rather than launching full training runs during every test.
# PQ-AI Provenance

### A Post-Quantum Framework for AI Dataset Integrity, Provenance Verification, Model Watermarking, and Tampering Analysis

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![PyTorch](https://img.shields.io/badge/PyTorch-Deep%20Learning-orange)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![Cryptography](https://img.shields.io/badge/Cryptography-ML--DSA--65-purple)
![Hashing](https://img.shields.io/badge/Hashing-SHA--256-blue)
![Database](https://img.shields.io/badge/Database-SQLite-lightgrey)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-informational)
![License](https://img.shields.io/badge/License-TBD-lightgrey)

**PQ-AI Provenance** is a local-first desktop application that brings together post-quantum digital signatures, cryptographic dataset fingerprinting, machine-learning experiments, AI model watermarking, and tampering analysis in a unified environment.

The project's objective is to investigate how cryptographic provenance mechanisms can help establish the integrity and authenticity of AI dataset records, while controlled machine-learning experiments measure the effects of dataset and model modifications.

Instead of treating dataset verification, AI training, and model watermarking as isolated activities, PQ-AI Provenance connects them through a reproducible experimental workflow.

> **Project status:** The repository now includes a PySide6 dashboard shell, background workers, and a root launcher. Some research workflows still rely on the current backend scripts and should be validated before release.

---

## Table of Contents

- [1. Introduction](#1-introduction)
- [2. Problem Statement](#2-problem-statement)
- [3. Motivation](#3-motivation)
- [4. Project Objectives](#4-project-objectives)
- [5. Proposed Solution](#5-proposed-solution)
- [6. Scope and Boundaries](#6-scope-and-boundaries)
- [7. Key Features](#7-key-features)
- [8. Technology Stack](#8-technology-stack)
- [9. System Architecture](#9-system-architecture)
- [10. Repository Structure](#10-repository-structure)
- [11. Complete System Workflow](#11-complete-system-workflow)
- [12. Dataset Integrity and SHA-256](#12-dataset-integrity-and-sha-256)
- [13. Provenance Manifest](#13-provenance-manifest)
- [14. Post-Quantum Cryptography](#14-post-quantum-cryptography)
- [15. Digital Signature Verification](#15-digital-signature-verification)
- [16. AI Dataset Management](#16-ai-dataset-management)
- [17. Machine-Learning Pipeline](#17-machine-learning-pipeline)
- [18. Dataset Tampering Experiments](#18-dataset-tampering-experiments)
- [19. AI Model Watermarking](#19-ai-model-watermarking)
- [20. Model Robustness Experiments](#20-model-robustness-experiments)
- [21. Experimental Metrics](#21-experimental-metrics)
- [22. Desktop Application Design](#22-desktop-application-design)
- [23. Database Design](#23-database-design)
- [24. Data Storage and File Management](#24-data-storage-and-file-management)
- [25. Configuration and Reproducibility](#25-configuration-and-reproducibility)
- [26. Installation](#26-installation)
- [27. Running the Application](#27-running-the-application)
- [28. Command-Line Interface](#28-command-line-interface)
- [29. Testing and Quality Assurance](#29-testing-and-quality-assurance)
- [30. Security Considerations](#30-security-considerations)
- [31. Threat Model](#31-threat-model)
- [32. Limitations](#32-limitations)
- [33. Cross-Platform Packaging](#33-cross-platform-packaging)
- [34. Troubleshooting](#34-troubleshooting)
- [35. Development Roadmap](#35-development-roadmap)
- [36. Future Enhancements](#36-future-enhancements)
- [37. Skills for GitHub Copilot](#37-skills-for-github-copilot)
- [38. Contribution Guidelines](#38-contribution-guidelines)
- [39. Academic and Research Applications](#39-academic-and-research-applications)
- [40. Glossary](#40-glossary)
- [41. References](#41-references)
- [42. License](#42-license)

---

# 1. Introduction

Artificial intelligence systems depend on datasets, training configurations, model checkpoints, and evaluation procedures. The reliability of an AI system can be affected when any of these components are altered, replaced, corrupted, or inadequately documented.

Traditional machine-learning workflows often focus primarily on model accuracy. However, accuracy alone does not explain whether the dataset used for training is the expected dataset, whether a recorded training configuration is authentic, or whether a model checkpoint has changed since it was produced.

PQ-AI Provenance investigates these problems through an integrated experimental framework.

The application combines five major components:

1. **Dataset fingerprinting:** Generate SHA-256 hashes to identify file contents and detect subsequent changes.
2. **Cryptographic provenance:** Create structured manifests describing datasets, training runs, and models.
3. **Post-quantum signatures:** Use ML-DSA-65 to sign provenance records and verify their authenticity.
4. **Machine-learning experiments:** Train and evaluate a ResNet-18 model using CIFAR-10.
5. **Model watermarking and tampering analysis:** Study whether an ownership signal remains detectable after specified model modifications and measure how dataset changes affect model performance.

A PySide6 desktop interface is intended to make these operations accessible through a unified workflow. SQLite provides local persistence for experiment metadata, while CSV and JSON exports support external analysis and reporting.

The project is designed for educational research, experimental evaluation, and investigation of the relationship between cryptographic integrity and machine-learning reliability.

## 1.1 Core idea

The central idea is to connect the history of a machine-learning experiment with cryptographically verifiable records.

For example, a user can:

1. Select a dataset.
2. Calculate its fingerprint.
3. Create a provenance manifest.
4. Sign the manifest using an ML-DSA-65 private key.
5. Verify the signature later using the corresponding public key.
6. Train a model using the recorded dataset and configuration.
7. Associate the resulting checkpoint with the training record.
8. Introduce controlled dataset modifications and compare the results.
9. Apply model transformations and evaluate watermark detection.
10. Export the experimental results for analysis.

This workflow helps distinguish changes that can be detected cryptographically from changes whose consequences must be evaluated experimentally.

## 1.2 Design philosophy

The application follows these principles:

- **Local-first:** Dataset processing, cryptographic operations, model training, and experiment history are intended to run locally.
- **Verifiable records:** Important records should contain hashes, identifiers, and signatures where appropriate.
- **Reproducible experiments:** Configurations, seeds, software versions, and results should be recorded.
- **Modular implementation:** Cryptography, ML, watermarking, persistence, and GUI code should remain separate.
- **Explicit limitations:** Security claims must reflect what was actually verified or experimentally demonstrated.
- **Cross-platform development:** Windows, Linux, and macOS should be supported through platform-specific builds and testing.

---

# 2. Problem Statement

Machine-learning pipelines involve multiple files and processing stages. A dataset may be downloaded from an external source, preprocessed, divided into training and testing subsets, modified, and then used to train a model. The resulting model may be saved, transferred, fine-tuned, compressed, or reused in another environment.

Without reliable records, it can be difficult to establish whether the current files correspond to the files originally used, whether a provenance record has changed, or how a modification affected the final model.

Three related problems motivate this project.

### 2.1 Dataset integrity and provenance

Dataset names and filenames are not sufficient to establish file identity. Two files can have the same name but different contents. A dataset can also change after its initial inspection.

A cryptographic fingerprint can detect a change relative to a previously recorded fingerprint. A digital signature can authenticate a manifest, provided the verification key is trusted.

However, these mechanisms need to be integrated into the machine-learning workflow to provide a useful record of which data and configurations were associated with a particular training run.

### 2.2 Post-quantum authenticity

Many conventional public-key cryptographic systems rely on mathematical problems that could be threatened by sufficiently capable quantum computers.

Post-quantum cryptography provides standardized cryptographic algorithms designed to resist known classical and quantum attacks under their security assumptions.

PQ-AI Provenance uses ML-DSA-65, a standardized module-lattice-based digital signature algorithm, to investigate post-quantum authentication of dataset and training provenance records.

### 2.3 AI model modification and ownership signals

A model checkpoint can be modified after training. Fine-tuning, pruning, quantization, compression, or other transformations may affect model performance and any embedded watermark.

A model watermark experiment can evaluate whether a designated signal remains detectable after such transformations. The result depends on the watermarking method, detection procedure, transformation, model, and evaluation conditions.

PQ-AI Provenance aims to provide a controlled environment for measuring these outcomes rather than assuming that a watermark is universally robust.

## 2.4 Problem statement summary

The project addresses the need for an integrated, reproducible desktop workflow that combines dataset fingerprinting, signed provenance records, machine-learning experiments, and model-watermark robustness evaluation.

It seeks to demonstrate what these mechanisms can establish, what changes they can detect, and what limitations remain when cryptographic provenance is applied to AI development.

---

# 3. Motivation

The motivation is to explore AI integrity as a lifecycle problem rather than a single model-evaluation problem.

A high-performing model is not necessarily associated with trustworthy provenance. A valid signature does not establish model quality. A watermark detection result does not establish that the dataset was authentic. Each mechanism answers a different question.

The project makes these distinctions visible and experimentally testable.

Potential applications of the underlying concepts include:

- Research dataset management.
- Reproducible AI experiments.
- Model checkpoint auditing.
- Controlled dataset corruption studies.
- Model ownership research.
- Post-quantum signature evaluation.
- Local AI artifact verification.
- Educational demonstrations of cryptographic integrity.

These are potential applications, not claims that the application already meets production auditing or regulatory requirements.

---

# 4. Project Objectives

## 4.1 Primary objectives

### Objective 1: Dataset integrity

Implement SHA-256 fingerprinting for dataset files and structured dataset manifests.

The system should detect differences between observed contents and previously recorded fingerprints.

### Objective 2: Cryptographic provenance

Represent relevant dataset and training metadata in a structured, versioned manifest.

The manifest should be suitable for canonical serialization, hashing, signing, storage, and later verification.

### Objective 3: Post-quantum digital signatures

Integrate ML-DSA-65 using a maintained cryptographic implementation.

The application should support key generation, manifest signing, public-key verification, and cryptographic performance measurements.

### Objective 4: Reproducible machine learning

Establish a baseline image-classification experiment using CIFAR-10 and ResNet-18.

Record the model configuration, training parameters, dataset identity, metrics, and checkpoint metadata.

### Objective 5: Controlled dataset tampering

Introduce reproducible dataset modifications at configurable rates, initially 1%, 5%, and 10%.

Measure how the selected modifications affect model training and evaluation.

### Objective 6: AI model watermarking

Implement a documented watermarking method and evaluate its detection behavior under controlled conditions.

### Objective 7: Robustness evaluation

Measure changes in model performance and watermark detection after transformations such as fine-tuning, pruning, and compression or quantization.

### Objective 8: Usable desktop interface

Build a PySide6 interface that allows users to run experiments, inspect verification results, view metrics, and export reports.

### Objective 9: Local experiment history

Store experiment metadata and provenance relationships in SQLite and support portable exports.

### Objective 10: Cross-platform distribution

Prepare platform-specific packages for Windows, Linux, and macOS and verify their behavior in appropriate environments.

## 4.2 Success criteria

The project should be evaluated against observable outcomes.

| Area | Success criterion |
|---|---|
| Fingerprinting | A changed file is detected against its recorded hash. |
| Provenance | A manifest can be created, serialized, stored, and loaded. |
| Digital signatures | Valid records verify; modified signed content fails verification. |
| ML-DSA-65 | The selected backend performs real key generation, signing, and verification. |
| ML pipeline | A baseline model can train, evaluate, save, and reload. |
| Tampering | Experiments apply documented changes at the configured rates. |
| Watermarking | The implemented detector produces measurable outcomes on defined test cases. |
| Robustness | Baseline and transformed models are compared using recorded conditions. |
| Persistence | Experiment metadata survives application restarts. |
| GUI | Long-running tasks do not freeze the interface. |
| Testing | Automated tests cover core success and failure cases. |
| Packaging | Each supported OS has a separately built and tested release artifact. |

These criteria are intended targets. They should not be interpreted as proof that all listed features are already complete.

---

# 5. Proposed Solution

PQ-AI Provenance uses a modular pipeline in which cryptographic verification and ML evaluation complement one another.

## 5.1 High-level process

```text
                  DATASET INPUT
                       |
                       v
              Dataset File Scanner
                       |
                       v
                 SHA-256 Hashing
                       |
                       v
               Provenance Manifest
                       |
                       v
              ML-DSA-65 Signature
                       |
                       v
             Signature Verification
                       |
                       v
               Training Configuration
                       |
                       v
              CIFAR-10 / ResNet-18
                       |
                       v
                Baseline Checkpoint
                       |
              +--------+--------+
              |                 |
              v                 v
       Dataset Tampering    Model Watermark
              |                 |
              v                 v
       Retrain / Evaluate   Model Transformations
              |                 |
              v                 v
       Model Performance    Watermark Detection
              |                 |
              +--------+--------+
                       |
                       v
              Results and Reports
                       |
                       v
               SQLite / CSV / JSON
```

The exact implementation may split these steps into separate screens and services. The diagram represents the intended logical workflow, not a requirement to run every operation in one uninterrupted session.

## 5.2 Separation of responsibilities

The system should maintain clear boundaries between:

- File scanning and hashing.
- Manifest generation and validation.
- Cryptographic key management and signatures.
- Dataset preparation and training.
- Watermark embedding and detection.
- Experiment orchestration.
- Database persistence.
- GUI presentation.
- Export and reporting.

This separation improves testability, reduces coupling, and allows individual components to be modified without rewriting the whole application.

---

# 6. Scope and Boundaries

## 6.1 Included in the planned scope

- Desktop application using Python and PySide6.
- Local dataset file scanning and fingerprinting.
- SHA-256 hashing.
- Structured provenance manifests.
- ML-DSA-65 digital signatures and verification.
- CIFAR-10 baseline image-classification experiments.
- ResNet-18 model training and evaluation.
- Controlled dataset tampering experiments.
- Model watermark embedding and detection.
- Fine-tuning, pruning, and quantization or compression experiments.
- SQLite experiment history.
- CSV and JSON exports.
- Visualizations and performance measurements.
- Automated tests.
- Platform-specific application packaging.

## 6.2 Excluded from the initial scope

- Mandatory cloud storage.
- Mandatory web dashboard or hosted backend.
- Blockchain-based provenance.
- Automatic certification that a dataset is ethically or scientifically valid.
- Proof that model training was honest.
- Guaranteed watermark survival under every transformation.
- Guaranteed protection against all classical or quantum attacks.
- Enterprise identity management or centralized trust infrastructure.
- Formal certification for regulated AI deployments.

Additional functionality may be considered after the core experimental workflow is stable.

---

# 7. Key Features

The following table describes the intended feature set.

| Feature | Purpose |
|---|---|
| Dataset scanner | Identify and enumerate files to be included in a dataset record. |
| SHA-256 fingerprinting | Produce content-derived fingerprints for files and manifests. |
| Provenance manifest | Record dataset and training metadata in a structured format. |
| ML-DSA-65 signing | Sign provenance records using a post-quantum signature algorithm. |
| Signature verification | Verify the signature and detect changes to signed content. |
| Dataset comparison | Compare current fingerprints with recorded fingerprints. |
| ML experiment manager | Configure, launch, and track training experiments. |
| ResNet-18 baseline | Establish a reference image-classification model. |
| Dataset tampering | Generate controlled, reproducible dataset modifications. |
| Watermark embedding | Apply the selected model-watermarking technique. |
| Watermark detection | Evaluate whether the designated signal is detectable. |
| Robustness evaluation | Measure outcomes after model transformations. |
| Experiment dashboard | Present metrics, status, and comparisons. |
| SQLite history | Store metadata and relationships between records. |
| Report export | Export selected records and results. |
| Desktop packaging | Distribute builds for supported operating systems. |

---

# 8. Technology Stack

The following technologies are planned for the project. Exact versions should be established and tested during implementation.

| Technology | Role |
|---|---|
| Python 3.11+ | Application language; the final supported version depends on dependency compatibility. |
| PySide6 | Desktop interface and event-driven UI. |
| PyTorch | Model training, inference, and tensor operations. |
| Torchvision | CIFAR-10 support, image transforms, and ResNet-18 architecture. |
| SHA-256 | Dataset and artifact fingerprinting. |
| ML-DSA-65 | Post-quantum digital signatures. |
| liboqs / liboqs-python or another supported backend | Cryptographic implementation, subject to API and compatibility validation. |
| SQLite | Local structured persistence. |
| CSV | Tabular experiment exports. |
| JSON | Structured manifests, configuration, and portable records. |
| Matplotlib | Experiment visualizations. |
| pytest | Automated tests. |
| PyInstaller | Platform-specific desktop packaging. |
| Git | Version control. |
| GitHub Copilot Agent Skills | Repository-aware development assistance. |

## 8.1 Why Python?

Python provides mature ecosystems for machine learning, numerical computing, cryptographic integration, desktop interfaces, and testing. Using one primary language allows the project to connect these components without introducing unnecessary inter-process communication.

## 8.2 Why PySide6?

PySide6 provides Qt-based desktop UI components, event handling, background-worker integration, tables, dialogs, and plotting integration.

It supports desktop interfaces across major operating systems, although packaging and testing must account for platform-specific behavior.

## 8.3 Why PyTorch and ResNet-18?

PyTorch supports flexible training and experimentation. ResNet-18 is a manageable baseline architecture for image-classification studies.

Its relative simplicity makes it suitable for comparing baseline and modified training conditions without requiring a very large model.

## 8.4 Why SQLite?

SQLite stores structured experiment records in a local database file. It does not require a separate database server and is suitable for a single-user desktop application.

## 8.5 Why both SHA-256 and ML-DSA-65?

They provide different capabilities.

- SHA-256 generates a fingerprint of content.
- ML-DSA-65 signs a message and allows a verifier to check that signature against a public key.

A hash alone does not establish who created a record. A signature does not replace hashing, data validation, or secure key management.

---

# 9. System Architecture

The application is organized into logical layers.

## 9.1 Presentation layer

Responsible for the user interface.

Expected responsibilities:

- Main application window.
- Navigation between modules.
- Forms for dataset and experiment configuration.
- Progress indicators.
- Tables and charts.
- Verification status.
- Error dialogs.
- Export controls.

The presentation layer should not directly implement cryptographic algorithms or training loops.

## 9.2 Application services layer

Coordinates workflows across components.

Examples include:

- Creating a provenance record.
- Running a signature verification workflow.
- Starting an ML experiment.
- Launching a dataset tampering experiment.
- Running a watermark robustness evaluation.
- Persisting the resulting metadata.

Services should orchestrate lower-level operations without duplicating their implementations.

## 9.3 Cryptography layer

Responsible for:

- SHA-256 file hashing.
- Canonical manifest serialization.
- ML-DSA-65 key generation.
- Signing and verification.
- Public-key and signature encoding.
- Cryptographic error handling.

The implementation should use a maintained library and should not implement ML-DSA from scratch.

## 9.4 Provenance layer

Responsible for:

- Manifest schema.
- Dataset identity records.
- Training configuration metadata.
- Model checkpoint metadata.
- Relationships between datasets, manifests, and models.
- Schema versioning.
- Provenance validation.

## 9.5 Machine-learning layer

Responsible for:

- Dataset loading.
- Preprocessing and augmentation.
- Model initialization.
- Training and evaluation.
- Checkpoint management.
- Metric calculations.
- Dataset tampering operations.

## 9.6 Watermarking layer

Responsible for:

- Watermark configuration.
- Embedding.
- Detection.
- Threshold selection.
- Robustness experiments.
- Watermark evaluation reports.

The exact watermarking algorithm must be documented and validated before robustness results can be meaningfully interpreted.

## 9.7 Persistence layer

Responsible for:

- SQLite schema and migrations.
- Experiment metadata.
- Provenance records.
- Model artifact references.
- Verification history.
- Export formatting.

Large datasets and model checkpoints should generally remain in the filesystem rather than being inserted as large binary objects into SQLite.

## 9.8 Worker and execution layer

Responsible for long-running operations, including:

- Hashing large files.
- Downloading or loading datasets.
- Training models.
- Running robustness experiments.
- Generating reports.

In the desktop interface, these tasks should run outside the main UI thread. Qt signals and slots should communicate progress and completion.

---

# 10. Repository Structure

The repository uses a root-level layout with a desktop launcher, a PySide6 dashboard package, and backend modules grouped by concern.

```text
PQ-AI-Provenance/
├── main.py
├── PQAI.spec
├── dashboard/
│   ├── __init__.py
│   ├── main_window.py
│   ├── services.py
│   └── workers.py
├── crypto/
│   ├── hashing.py
│   ├── ml_dsa.py
│   └── benchmark.py
├── data/
├── experiments/
│   ├── tamper.py
│   └── robustness.py
├── model/
│   ├── train.py
│   ├── evaluate.py
│   ├── watermark.py
│   ├── add_watermark.py
│   └── check_watermark.py
├── provenance/
│   └── manifest.py
├── results/
├── requirements.txt
└── README.md
```

### Structure notes

- `dashboard/` contains the PySide6 GUI, background workers, and high-level workflow services.
- `crypto/` contains hashing, ML-DSA signing, and benchmark utilities.
- `model/` contains training, evaluation, watermarking, and watermark checks.
- `experiments/` contains tamper and robustness workflows.
- `provenance/` contains manifest generation and verification helpers.
- `main.py` is the desktop entry point for development.
- `PQAI.spec` is the PyInstaller build definition for packaging the app.

The repository is intentionally flat enough to keep the research workflow easy to inspect.

---

# 11. Complete System Workflow

## 11.0 What you need to prepare

Before running the full workflow, you should have these inputs ready:

1. A dataset directory or dataset file to hash.
2. A clean baseline model checkpoint, or enough time to train one from CIFAR-10.
3. A separate output path for the watermarked model.
4. A separate output path for any tampered dataset exports.
5. A writable results directory for manifests, signatures, metrics, and logs.
6. A key directory for ML-DSA-65 public and secret keys.

If you are starting from scratch, the usual sequence is: train the original model, save it, create the tampered dataset copy, hash the dataset, create a signed manifest, then run watermark and robustness tests on the clean and modified checkpoints.

This section describes the intended end-to-end workflow.

## Phase 1: Dataset selection

The user selects an existing local dataset or configures the CIFAR-10 dataset source.

The application identifies the files included in the operation and validates the selected path.

Checks should include:

- Whether the path exists.
- Whether it is a file or directory as expected.
- Whether the application can read it.
- Whether supported file types are present.
- Whether the directory contains unexpected symbolic links or files that should be excluded.
- Whether the dataset is already recorded.

The scanner should define how directory contents are enumerated and sorted. Reproducible ordering is essential when producing aggregate dataset fingerprints.

## Phase 2: Dataset fingerprinting

The application calculates SHA-256 hashes for the selected files.

For a directory-based dataset, it can record individual file hashes and generate a deterministic aggregate fingerprint from a canonical list of relative paths and file hashes.

The original dataset remains unchanged.

## Phase 3: Manifest generation

The application generates a structured manifest containing the dataset identity, fingerprint information, timestamps, schema version, and other relevant metadata.

Training-specific fields can be added later when a training run is created.

## Phase 4: Manifest signing

The user selects or creates an ML-DSA-65 signing key.

The application serializes the manifest deterministically and signs the exact byte sequence.

The signature is stored alongside the manifest or in an associated signature record. The public key or a public-key identifier is made available for verification.

## Phase 5: Verification

The application loads the manifest and signature, verifies the signature against the supplied public key, and reports the result.

Where dataset integrity is being checked, it also recomputes the current fingerprint and compares it with the fingerprint recorded in the manifest.

These checks must be reported separately.

A valid signature and a matching dataset fingerprint are related but distinct results.

## Phase 6: Baseline training

The user configures the training experiment and launches the CIFAR-10 / ResNet-18 pipeline.

The experiment records its configuration, dataset identifier, seed, metrics, software environment, and checkpoint metadata.

## Phase 7: Dataset tampering

The user chooses a tampering method and a rate, such as 1%, 5%, or 10%.

The system creates a modified experimental dataset or a controlled modification configuration without overwriting the baseline.

The modified dataset receives its own fingerprint and provenance record.

## Phase 8: Model watermarking

The selected watermarking procedure is applied according to its documented design.

The application records the model identifier, watermark configuration, detector configuration, and the relevant evaluation results.

## Phase 9: Robustness evaluation

The baseline model or watermarked model is subjected to a controlled transformation, such as fine-tuning, pruning, or quantization.

The application compares model performance and watermark detection before and after the transformation.

## Phase 10: Reporting

The application saves experiment metadata and presents the results through tables, charts, and exportable reports.

The report should make it possible to identify:

- Which dataset was used.
- Which manifest was signed.
- Which signature and public key were verified.
- Which training configuration produced a checkpoint.
- Which tampering or model transformation was applied.
- Which metrics were measured.
- Which experimental limitations apply.

---

# 12. Dataset Integrity and SHA-256

## 12.1 What is a cryptographic hash?

A cryptographic hash function transforms input data of arbitrary length into a fixed-length digest.

SHA-256 produces a 256-bit digest, usually displayed as 64 hexadecimal characters.

The same byte sequence produces the same digest. A different byte sequence will normally produce a different digest, with accidental collisions expected to be computationally infeasible under the security assumptions of SHA-256.

## 12.2 Why use SHA-256?

SHA-256 is useful for identifying file contents and detecting changes relative to a previously recorded digest.

Examples include:

- Dataset images.
- Dataset metadata.
- Provenance manifests.
- Model checkpoints.
- Exported experiment records.
- Configuration files.

## 12.3 File hashing

The implementation should read files in chunks rather than loading an entire large file into memory.

Illustrative implementation:

```python
from hashlib import sha256
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()
```

This code illustrates the intended hashing behavior. Production code should additionally consider file-read errors, file changes during hashing, and validation of the path.

## 12.4 Dataset-level fingerprints

Hashing only the directory name is insufficient because a directory name does not describe its contents.

A deterministic directory fingerprint can be derived from:

1. A defined root directory.
2. A stable list of included files.
3. Normalized relative paths.
4. Individual SHA-256 digests.
5. A canonical serialization of the file list.
6. A final SHA-256 digest over that serialization.

Conceptually:

```text
dataset/
├── image_001.png
├── image_002.png
└── labels.csv
```

The system records something like:

```text
image_001.png -> SHA256(file contents)
image_002.png -> SHA256(file contents)
labels.csv    -> SHA256(file contents)
```

The relative paths and hashes are then serialized deterministically to produce a dataset-level fingerprint.

This detects changes to file contents and, if paths are included, changes to the file layout.

### Important implementation details

The aggregate fingerprint design must specify:

- Path separator normalization.
- Unicode normalization, if required.
- Sorting rules.
- Treatment of symbolic links.
- Treatment of empty directories.
- Excluded files.
- Duplicate paths.
- File metadata included in the record.
- Serialization format and schema version.

A change in these rules may change the aggregate fingerprint even if the underlying image contents remain identical.

## 12.5 Hashes are not signatures

A hash is not proof of authorship.

If an attacker can change a dataset and also replace an unsigned hash record, a simple hash comparison against that record may still succeed.

The signature provides a mechanism to authenticate the recorded manifest, assuming the verification key is trusted.

## 12.6 Dataset integrity workflow

```text
Original Dataset
      |
      v
Enumerate Included Files
      |
      v
Hash Each File
      |
      v
Canonical File Inventory
      |
      v
Dataset Fingerprint
      |
      v
Store Fingerprint in Manifest
      |
      v
Sign Manifest
      |
      v
Later: Recompute and Compare
```

The resulting verification report should state whether the observed files match the recorded fingerprints and whether the manifest signature is valid.

---

# 13. Provenance Manifest

## 13.1 Purpose

A provenance manifest is a structured record describing a dataset, model, training run, or another relevant artifact.

It acts as a machine-readable reference that can be stored, signed, compared, exported, and linked to experiment history.

## 13.2 Proposed manifest fields

A dataset manifest may contain:

| Field | Purpose |
|---|---|
| `schema_version` | Identifies the manifest schema. |
| `manifest_id` | Unique record identifier. |
| `created_at` | Record creation timestamp. |
| `dataset` | Dataset identity and description. |
| `dataset_fingerprint` | Aggregate content fingerprint. |
| `files` | Optional inventory of included files and hashes. |
| `hash_algorithm` | Fingerprinting algorithm identifier. |
| `signature_algorithm` | Algorithm used to sign the record. |
| `signer_key_id` | Identifier for the signing public key. |
| `source_description` | Source information or a user-provided claim. |
| `application_version` | Version of the software that created the record. |

A training record can additionally contain:

- Training run ID.
- Dataset manifest ID.
- Model architecture.
- Hyperparameters.
- Random seed.
- Training and evaluation split references.
- Software versions.
- Start and completion timestamps.
- Model checkpoint path or artifact identifier.
- Checkpoint SHA-256 hash.
- Evaluation metrics.
- Experiment status.

## 13.3 Example unsigned manifest

The following is an illustrative example, not a generated record or a claim that a real dataset has been verified.

```json
{
  "schema_version": "1.0",
  "manifest_id": "example-dataset-record-001",
  "created_at": "2026-10-16T12:00:00Z",
  "dataset": {
    "name": "CIFAR-10",
    "description": "Image-classification dataset",
    "source_description": "Dataset obtained through a configured source"
  },
  "fingerprint": {
    "algorithm": "SHA-256",
    "scope": "defined-dataset-file-inventory",
    "value": "REPLACE_WITH_ACTUAL_FINGERPRINT"
  },
  "signature": {
    "algorithm": "ML-DSA-65",
    "signer_key_id": "example-public-key-id"
  },
  "application": {
    "name": "PQ-AI Provenance",
    "version": "0.1.0"
  }
}
```

The `fingerprint.value` and key identifier are placeholders. A real manifest must use actual computed values.

## 13.4 Canonical serialization

Digital signatures operate on bytes, not abstract JSON objects.

Two JSON documents may represent the same data but differ in whitespace, key order, escaping, or number formatting. Signing one serialization and verifying another may therefore produce different bytes and fail verification.

The application must define a stable serialization procedure before signing.

Possible approaches include:

- A carefully specified deterministic JSON serialization.
- A standardized canonical JSON representation.

The selected format should define the handling of Unicode, numbers, keys, null values, and unsupported types.

The application should sign the exact canonical bytes and retain sufficient information to reproduce those bytes during verification.

## 13.5 Manifest lifecycle

A manifest should be treated as an immutable record once signed.

If a dataset is changed or new training metadata becomes available, the application should create a new record or version linked to the earlier record.

It should not silently edit signed content while retaining the original signature.

---

# 14. Post-Quantum Cryptography

## 14.1 Overview

Post-quantum cryptography refers to cryptographic algorithms designed to resist attacks from both classical and known quantum computing models.

PQ-AI Provenance uses ML-DSA-65 for digital signature experiments.

ML-DSA is standardized in NIST FIPS 204. It is derived from the CRYSTALS-Dilithium signature scheme and uses module-lattice-based cryptographic constructions.

## 14.2 Why ML-DSA-65?

ML-DSA-65 is the middle parameter set in the ML-DSA standard.

It provides a practical target for experimenting with post-quantum signatures in an application that needs to sign and verify structured records.

The project can measure:

- Key-generation duration.
- Signing duration.
- Verification duration.
- Public-key size.
- Private-key size.
- Signature size.
- Error-handling behavior.
- Operational overhead for provenance records.

Actual measurements depend on the implementation, hardware, operating system, library version, and execution conditions.

## 14.3 Key generation

Key generation creates a public/private key pair.

- The **public key** is used for verification.
- The **private key** is used for signing.

The public key can be distributed with a signed record, but the verifier still needs a trustworthy way to establish which public key belongs to the claimed signer.

A key identifier is useful for referencing keys, but a key identifier alone does not establish trust.

## 14.4 Signing

The signing process receives:

- Canonical manifest bytes.
- The signing private key.
- The required algorithm and parameter configuration.

It produces a digital signature.

The signature should be stored as a binary artifact or an explicitly encoded representation such as Base64, with its encoding documented.

The application should not sign arbitrary display text if the actual record uses a different byte representation.

## 14.5 Verification

Verification uses:

- The exact bytes of the manifest.
- The signature.
- The corresponding public key.

A successful result means that the signature verifies for the supplied message and public key under the selected algorithm.

It does not independently establish that the public key belongs to a particular person or organization.

## 14.6 Cryptographic backend

A supported implementation may be provided by liboqs and its Python bindings, or by another compatible implementation that supports ML-DSA-65.

Before integrating a backend, verify:

- Supported algorithm identifiers.
- Library and binding versions.
- Actual Python API signatures.
- Key and signature byte formats.
- Installation requirements.
- Native-library dependencies.
- Platform compatibility.
- Maintenance status and security guidance.

Do not assume that a library's older Dilithium API is identical to its ML-DSA API.

Do not silently fall back to a different algorithm when ML-DSA-65 is unavailable.

## 14.7 Cryptographic performance measurements

The application should benchmark key generation, signing, and verification independently.

A useful methodology is:

1. Record the environment and library version.
2. Use a fixed set of manifest sizes.
3. Perform warm-up operations where appropriate.
4. Execute multiple repetitions.
5. Record individual durations.
6. Report the median and a suitable variability measure.
7. Record public-key, private-key, and signature sizes.
8. Separate setup time from the measured operation.

Avoid comparing measurements taken under materially different conditions without documenting those differences.

## 14.8 Security claims

ML-DSA-65 is a standardized post-quantum signature scheme. Its use does not make every part of the application quantum-proof.

SHA-256, operating-system security, private-key storage, application dependencies, and the provenance process have their own security considerations.

The project should use precise terminology and avoid absolute guarantees.

---

# 15. Digital Signature Verification

## 15.1 Verification goals

The application should distinguish between at least two verification operations:

**Manifest signature verification**

Checks whether the signature is valid for the exact manifest bytes and supplied public key.

**Dataset fingerprint verification**

Checks whether the current dataset contents match the fingerprint recorded in the manifest.

These checks should produce independent results.

## 15.2 Verification outcomes

Possible status categories include:

- Signature valid.
- Signature invalid.
- Manifest malformed.
- Public key missing.
- Unsupported signature algorithm.
- Dataset fingerprint matches.
- Dataset fingerprint mismatch.
- Dataset unavailable.
- Verification incomplete.

An inability to verify must not be displayed as a successful verification.

## 15.3 Verification example

Suppose the original manifest records the fingerprint of a dataset and is signed using an ML-DSA-65 private key.

Later, the application loads the manifest and verifies its signature using the corresponding public key.

If the signed content has been altered, verification should fail unless the altered content also has a valid signature under an accepted signing key.

If the manifest signature is valid but the dataset fingerprint differs from the current files, the application should report that the signed record is authentic while the observed dataset does not match the recorded fingerprint.

This distinction is central to the project's design.

## 15.4 Trust establishment

A valid signature proves neither the real-world identity of the signer nor that the signing key was authorized to certify the dataset.

For meaningful provenance, the application should retain the public key or key fingerprint associated with the record and document how that key was obtained and trusted.

An attacker who replaces the manifest, signature, and public key together may defeat a workflow that blindly trusts all three files from the same untrusted source.

---

# 16. AI Dataset Management

## 16.1 Initial dataset

The initial baseline experiment uses CIFAR-10, a commonly used image-classification dataset containing 60,000 color images across 10 classes.

The standard dataset contains:

- 50,000 training images.
- 10,000 test images.
- 10 classes.
- Images of size 32 × 32 pixels with three color channels.

The application should document its actual dataset version, source, download configuration, preprocessing, and split usage.

## 16.2 Dataset lifecycle

The expected lifecycle is:

1. Configure the dataset source.
2. Download or select local files.
3. Validate the dataset structure.
4. Record dataset metadata.
5. Calculate fingerprints.
6. Create and sign a provenance manifest.
7. Use a defined training configuration.
8. Preserve the original data for comparison.
9. Create isolated experimental variants when needed.

## 16.3 Data separation

Training, validation, and test data should serve distinct purposes.

- **Training set:** Used to update model parameters.
- **Validation set:** Used to select configurations or tune hyperparameters.
- **Test set:** Used for final evaluation after experimental choices are established.

Repeatedly tuning against a test set can make the test results overly optimistic.

For the initial CIFAR-10 workflow, the application should define whether a validation subset is derived from the training data and how its membership is recorded.

## 16.4 Preprocessing and augmentation

The experiment configuration should specify:

- Input image dimensions.
- Pixel normalization.
- Training augmentation.
- Batch size.
- Number of workers.
- Data-loader shuffle behavior.
- Training and evaluation split identifiers.

Augmentation should normally be applied to training data only, unless a separate experiment explicitly studies another condition.

## 16.5 Dataset isolation

The application should never silently modify the original dataset.

Tampered datasets should be written to isolated experiment directories or generated from reproducible modification configurations.

Each experimental variant should have its own fingerprint and record.

---

# 17. Machine-Learning Pipeline

## 17.1 Baseline architecture

The planned baseline is ResNet-18, a residual convolutional neural network.

ResNet introduces skip connections that allow information and gradients to flow through deeper networks more effectively than a plain stack of layers in many training settings.

For CIFAR-10, the implementation must explicitly decide whether to use the standard ImageNet-oriented ResNet-18 stem or a CIFAR-adapted stem. This choice should be recorded in the configuration because it affects the model architecture.

## 17.2 Training configuration

A training run should record at least:

- Model architecture and architecture variant.
- Dataset manifest identifier.
- Training and validation split references.
- Batch size.
- Number of epochs.
- Optimizer.
- Learning rate.
- Learning-rate scheduler, if any.
- Loss function.
- Weight decay.
- Data augmentation.
- Random seed.
- Device used.
- Software versions.
- Start and end times.
- Checkpoint path or artifact ID.

Values such as batch size, learning rate, and epoch count should be configurable rather than silently hardcoded.

## 17.3 Training loop

A typical training workflow consists of:

1. Load and validate the dataset.
2. Create data loaders.
3. Initialize the model.
4. Configure the loss function and optimizer.
5. Iterate through the training batches.
6. Calculate the loss.
7. Backpropagate gradients.
8. Update model parameters.
9. Evaluate on validation data.
10. Record epoch-level metrics.
11. Save the selected checkpoint.
12. Evaluate the final model on the designated test set.

The exact loop depends on the experiment design.

## 17.4 Hardware support

The training service should detect available hardware and select an appropriate execution device.

Potential execution targets include:

- CPU.
- CUDA-compatible GPU when available and supported.
- Other acceleration backends only when explicitly implemented and validated.

The application must not assume that a GPU is present.

## 17.5 Checkpoint management

Checkpoints should include or be associated with:

- Model parameters.
- Architecture identifier.
- Relevant configuration.
- Training run ID.
- Dataset manifest ID.
- Epoch or training stage.
- Software and library versions.
- Checkpoint fingerprint.

If optimizer state is needed to resume training, it should also be saved.

PyTorch checkpoint files should be treated as potentially untrusted inputs. Loading options and file provenance should be considered carefully, and the application should not load arbitrary checkpoint files without appropriate safeguards.

## 17.6 Evaluation

At minimum, report:

- Accuracy.
- Precision.
- Recall.
- F1 score.
- Confusion matrix.

For multiclass classification, the application must specify whether precision, recall, and F1 use macro, micro, or weighted averaging.

Accuracy alone may conceal poor performance on individual classes.

## 17.7 Training reproducibility

Record seeds and settings for Python, NumPy, and PyTorch where applicable.

Deterministic execution is not guaranteed across all devices, platforms, or library versions. Any reproducibility claims should state the conditions under which the results were obtained.

---

# 18. Dataset Tampering Experiments

## 18.1 Purpose

Dataset tampering experiments investigate how specific dataset modifications affect integrity verification and model performance.

The application initially plans to support tampering rates of:

- 1%.
- 5%.
- 10%.

These rates describe the proportion of eligible samples or items selected for modification, according to the experiment's documented definition.

## 18.2 Define the tampering operation

A percentage alone does not describe a complete experiment. The application must specify what changes.

Possible experimental operations include:

### Label corruption

Replace selected training labels with incorrect labels according to a documented selection and replacement strategy.

### Image modification

Modify selected image contents through a controlled transformation.

### File replacement

Replace selected files with alternate files and record the replacement procedure.

### Metadata modification

Alter relevant dataset metadata or label records.

These operations are not equivalent. They should be implemented as separate experiment types, not treated as interchangeable examples of a single generic attack.

## 18.3 Tampering-rate calculation

For a dataset with \(N\) eligible samples and a requested tampering rate \(r\), the number of modified samples can be defined as:

\[
K = \lfloor N \cdot r \rfloor
\]

The implementation should explicitly document the rounding rule. If a different rounding rule is chosen, it must be used consistently and recorded.

For example, with 50,000 eligible training samples:

| Requested rate | Modified samples under floor rounding |
|---:|---:|
| 1% | 500 |
| 5% | 2,500 |
| 10% | 5,000 |

These are illustrative counts for a 50,000-sample eligible dataset.

The application should record the actual numerator, denominator, and resulting proportion for every run.

## 18.4 Controlled experiment design

A reliable experiment should:

1. Fingerprint the original dataset.
2. Define the eligible sample set.
3. Record the requested tampering operation and rate.
4. Select samples using a documented random seed.
5. Apply the modifications to an isolated experimental copy or transformation.
6. Calculate the modified dataset fingerprint.
7. Create a new provenance record.
8. Train using the specified configuration.
9. Evaluate using the same defined evaluation procedure.
10. Compare against a baseline.

For label-corruption experiments, the test set should remain untouched unless the experiment specifically investigates test-set corruption.

## 18.5 Experimental comparison

The application should compare the baseline and tampered runs using:

- Dataset fingerprints.
- Requested and actual tampering rates.
- Number of modified samples.
- Model configuration.
- Training settings.
- Test-set metrics.
- Confusion matrices.
- Training duration.
- Random seeds.

Where training is stochastic, multiple independent runs may be needed to distinguish a consistent effect from ordinary run-to-run variation.

## 18.6 Integrity verification after tampering

If a signed manifest describes the original dataset, a modified dataset should not match its original recorded fingerprint.

The application should generate a new fingerprint for the modified data and create a new record rather than changing the original manifest.

The signature of the original manifest can remain valid even when the currently inspected dataset no longer matches the recorded fingerprint.

This is expected behavior: signature verification and dataset matching answer different questions.

---

# 19. AI Model Watermarking

## 19.1 What is a model watermark?

A model watermark is a deliberately embedded signal that can be detected through a specified verification procedure.

Depending on the method, the signal may be associated with model parameters, responses to selected inputs, or another defined model behavior.

The exact method determines what the watermark proves and what attacks it may resist.

## 19.2 Purpose in this project

The project uses model watermarking to investigate whether an ownership-related signal remains detectable after defined transformations.

The purpose is experimental evaluation, not a claim that every model can be uniquely identified or that watermarking prevents model theft.

## 19.3 Watermark lifecycle

The intended workflow is:

1. Select a baseline model.
2. Configure the chosen watermark method.
3. Embed the watermark.
4. Save a new checkpoint.
5. Record the watermark configuration and model identifiers.
6. Evaluate clean-model accuracy.
7. Run the detector on the expected watermark signal.
8. Apply selected transformations.
9. Evaluate the transformed model.
10. Run the detector again.
11. Record the results and limitations.

## 19.4 Method selection

The project must select and document a specific watermark method before implementing final evaluation metrics.

A possible research direction is a trigger-based watermark, where a model is trained or fine-tuned to produce designated behavior for a controlled set of inputs.

Other methods may encode signals in parameters or use alternative verification mechanisms.

Different methods have different assumptions and security properties. Their results should not be combined without a clear justification.

## 19.5 Required records

For each watermark experiment, record:

- Model architecture and checkpoint ID.
- Baseline checkpoint hash.
- Watermark method and version.
- Embedding configuration.
- Detector configuration.
- Detection threshold.
- Secret or trigger material reference, where applicable.
- Clean accuracy before embedding.
- Accuracy after embedding.
- Watermark detection results.
- False-positive and false-negative measurements where applicable.
- Model transformation details.
- Random seeds and software versions.

Secret trigger data or watermark keys should not be included in public reports when their disclosure would undermine the intended verification process.

## 19.6 Watermark quality

Watermark evaluation should examine at least three dimensions:

**Utility:** Does embedding significantly affect normal model performance?

**Detectability:** Can the intended watermark be detected under the specified conditions?

**Robustness:** Does detection remain successful after the tested transformations?

A watermark that is easy to detect but causes severe performance degradation may not be useful. A watermark that survives one transformation may still fail under another.

---

# 20. Model Robustness Experiments

## 20.1 Fine-tuning

Fine-tuning continues training a model on additional data or under modified training conditions.

The experiment should record the data used, optimizer, learning rate, number of steps or epochs, and other relevant parameters.

Compare both model utility and watermark detection before and after fine-tuning.

## 20.2 Pruning

Pruning removes or reduces selected model parameters, connections, channels, or other components according to a specified strategy.

Record the pruning method and target amount. Do not describe all pruning procedures as equivalent because their effects on model accuracy and watermark detection may differ.

## 20.3 Quantization and compression

Quantization changes the numerical representation used by a model or its parameters. Compression may refer to quantization, file compression, parameter reduction, or another transformation.

The experiment should state exactly which operation is applied.

File compression alone may leave the underlying model parameters unchanged. Quantization can change model behavior, and those two cases should not be reported as the same attack.

## 20.4 Evaluation procedure

For each transformation:

1. Load a known baseline checkpoint.
2. Create an isolated transformed checkpoint.
3. Record the transformation and parameters.
4. Calculate the transformed checkpoint hash.
5. Evaluate normal model performance.
6. Run the watermark detector.
7. Compare with the baseline.
8. Save a structured result record.

## 20.5 Results interpretation

Watermark detection after a transformation is an empirical result for that particular method, model, dataset, and configuration.

It does not prove that the watermark is universally robust or that no alternative modification could remove it.

---

# 21. Experimental Metrics

The application should separate cryptographic, machine-learning, and watermarking metrics.

## 21.1 Cryptographic metrics

| Metric | Description |
|---|---|
| Key-generation time | Duration of a key-generation operation. |
| Signing time | Duration of signing a specified manifest. |
| Verification time | Duration of verifying a specified signature. |
| Public-key size | Size of the encoded public key. |
| Private-key size | Size of the encoded private key. |
| Signature size | Size of the generated signature. |
| Manifest size | Size of the canonical signed payload. |
| Verification outcome | Valid, invalid, or unable to verify. |

Record units and the measurement methodology.

## 21.2 Classification metrics

For classification with true labels and predicted labels:

\[
\text{Accuracy} =
\frac{\text{Correct predictions}}{\text{Total predictions}}
\]

For a defined positive class:

\[
\text{Precision} =
\frac{TP}{TP+FP}
\]

\[
\text{Recall} =
\frac{TP}{TP+FN}
\]

\[
F_1 =
2\cdot\frac{\text{Precision}\cdot\text{Recall}}
{\text{Precision}+\text{Recall}}
\]

For multiclass CIFAR-10, the implementation should explicitly document the averaging strategy. These equations alone do not specify how to aggregate results across all ten classes.

The implementation must also handle cases where a denominator is zero.

## 21.3 Dataset tampering metrics

- Requested tampering rate.
- Actual tampering rate.
- Number of modified samples.
- Number of eligible samples.
- Original dataset fingerprint.
- Modified dataset fingerprint.
- Baseline accuracy and F1.
- Tampered-model accuracy and F1.
- Difference from baseline.

A simple accuracy difference can be reported as:

\[
\Delta A = A_{\text{tampered}} - A_{\text{baseline}}
\]

A negative result indicates a reduction in accuracy relative to the baseline. A positive result does not automatically mean tampering improved generalization; stochastic variation and the exact experimental design must be considered.

## 21.4 Watermark metrics

Potential metrics include:

- Watermark detection rate.
- False-positive rate.
- False-negative rate.
- Clean-model accuracy.
- Accuracy after embedding.
- Accuracy after transformation.
- Detection rate after transformation.

For a specified evaluation set:

\[
\text{Detection Rate} =
\frac{\text{Correctly detected watermark cases}}
{\text{Total positive watermark cases}}
\]

The definition of a positive watermark case and the detection threshold must be documented.

## 21.5 Model transformation metrics

For each transformation, record:

- Transformation type.
- Transformation parameters.
- Original checkpoint hash.
- Transformed checkpoint hash.
- Model size before and after.
- Accuracy before and after.
- Watermark detection before and after.
- Execution duration.
- Hardware and software environment.

## 21.6 Reporting standards

A useful report should state:

- What was measured.
- How it was measured.
- Which dataset and model were used.
- Which configuration produced the result.
- Whether the result is from one run or repeated runs.
- What the result does and does not demonstrate.

Plots should include labelled axes, units, legends, and identifiable baselines.

---

# 22. Desktop Application Design

## 22.1 Design objective

The PySide6 application should provide a consistent interface for configuring, executing, and reviewing the project's workflows.

The interface should not require users to manually run every backend operation from a terminal.

## 22.2 Proposed screens

### Dashboard

Displays an overview of local experiment activity.

Potential elements:

- Total experiment records.
- Recent verification results.
- Latest training runs.
- Recent watermark experiments.
- Quick actions.
- Recent failures or incomplete operations.

The dashboard should show only information supported by persisted records.

### Dataset management

Allows users to select datasets, inspect file inventories, calculate fingerprints, and view existing provenance records.

Potential actions:

- Select a directory.
- Select supported dataset files.
- Scan dataset contents.
- Calculate file hashes.
- Generate an aggregate fingerprint.
- Compare with a previous record.
- Export an inventory.

### Provenance management

Allows users to create, inspect, sign, and verify manifests.

Potential actions:

- Create a manifest.
- View manifest metadata.
- Export a manifest.
- Select a signing key.
- Sign the canonical record.
- Verify a signature.
- Compare a current dataset with the recorded fingerprint.

### Cryptography

Provides access to key generation, key metadata, signing, verification, and benchmarking.

The interface should not expose private-key contents unnecessarily. Sensitive operations should have explicit status messages and safe error handling.

### Model training

Allows users to configure and launch the baseline ML pipeline.

Potential controls include:

- Dataset selection.
- Model architecture.
- Batch size.
- Epoch count.
- Optimizer settings.
- Learning rate.
- Random seed.
- Execution device.
- Output directory.

### Dataset tampering

Allows users to select a tampering operation, configure its rate, choose the random seed, and launch a controlled experiment.

The original dataset should be protected from accidental modification.

### Watermarking

Allows users to configure the implemented watermark method, embed the signal, run detection, and inspect the results.

The UI must explain which method is being used rather than presenting all watermarking techniques as equivalent.

### Robustness experiments

Allows users to select a model checkpoint and transformation, configure its parameters, run the experiment, and compare model utility and watermark detection.

### Reports and history

Displays experiment records, metrics, verification outcomes, and export options.

## 22.3 Background execution

Training and large-file processing must not block the Qt event loop.

A worker object, normally moved to a suitable `QThread`, can emit signals for:

- Progress updates.
- Current stage.
- Informational messages.
- Successful completion.
- Failure details.
- Cancellation status, where supported.

The UI should update only through safe Qt mechanisms.

## 22.4 Error handling

Errors should be actionable and understandable.

For example, instead of reporting only that a model failed to load, the application should indicate that the checkpoint could not be read and suggest checking its path, format, and compatibility.

Detailed diagnostic information can be logged locally without exposing private keys or other secrets.

---

# 23. Database Design

## 23.1 Purpose

SQLite is intended to maintain local metadata and relationships between datasets, manifests, training runs, checkpoints, and experiments.

The database should not be treated as an immutable audit log unless additional mechanisms are implemented to protect its history against alteration.

## 23.2 Proposed entities

### `datasets`

Stores dataset metadata.

Potential fields:

- `id`
- `name`
- `source_description`
- `dataset_path`
- `fingerprint`
- `hash_algorithm`
- `created_at`
- `schema_version`

### `manifests`

Stores provenance record metadata and references to manifest files.

Potential fields:

- `id`
- `dataset_id`
- `manifest_path`
- `manifest_hash`
- `signature_path`
- `signature_algorithm`
- `signer_key_id`
- `created_at`
- `verification_status`

The database status should be considered a cached observation. Verification should be rerun when the underlying record or trust configuration changes.

### `keys`

Stores non-secret metadata about cryptographic keys.

Potential fields:

- `id`
- `key_id`
- `algorithm`
- `public_key_path`
- `public_key_fingerprint`
- `created_at`
- `status`

Private-key bytes should not be stored in an ordinary metadata table.

### `training_runs`

Stores training configuration and outcomes.

Potential fields:

- `id`
- `dataset_id`
- `manifest_id`
- `model_architecture`
- `configuration_json`
- `seed`
- `started_at`
- `completed_at`
- `status`
- `checkpoint_path`
- `checkpoint_hash`

### `experiments`

Stores tampering, watermarking, and robustness experiment metadata.

Potential fields:

- `id`
- `training_run_id`
- `experiment_type`
- `configuration_json`
- `started_at`
- `completed_at`
- `status`
- `result_path`

### `metrics`

Stores metric records.

Potential fields:

- `id`
- `experiment_id`
- `metric_name`
- `metric_value`
- `metric_unit`
- `split_name`
- `recorded_at`

### `verification_events`

Stores verification observations.

Potential fields:

- `id`
- `manifest_id`
- `checked_at`
- `signature_result`
- `fingerprint_result`
- `public_key_fingerprint`
- `details_json`

These schemas are conceptual. Actual tables, constraints, indexes, and migrations should be designed based on the implemented data model.

## 23.3 Database practices

- Use parameterized SQL statements.
- Enable appropriate foreign-key constraints.
- Use transactions for multi-record operations.
- Add indexes for frequently queried relationships.
- Validate serialized JSON before storing it.
- Define schema migrations.
- Handle locked databases and disk errors.
- Back up records before destructive migrations.
- Avoid storing private-key material in the database.
- Do not claim database records are tamper-proof without additional protection.

---

# 24. Data Storage and File Management

## 24.1 Separate application and user data

The application executable and user-generated data should be stored separately.

A packaged application should not depend on writing into its installation directory.

The implementation should use platform-appropriate per-user application-data directories, resolved through a consistent configuration service.

## 24.2 Suggested logical storage layout

```text
PQ-AI-Provenance-Data/
├── database/
│   └── provenance.sqlite
│
├── datasets/
│   ├── original/
│   └── experimental/
│
├── manifests/
│   ├── unsigned/
│   └── signed/
│
├── keys/
│   └── public/
│
├── models/
│   ├── baseline/
│   ├── watermarked/
│   └── transformed/
│
├── experiments/
│   ├── dataset-tampering/
│   └── watermark-robustness/
│
├── reports/
│   ├── csv/
│   ├── json/
│   └── figures/
│
└── logs/
```

This is a logical layout. The actual application-data location should be configurable and platform-appropriate.

Private keys, if stored locally, require a separate protected location and a documented security policy. They should not be stored in the public-key directory shown above.

## 24.3 Large artifacts

Datasets and checkpoints can be much larger than metadata records. Store their paths and hashes in SQLite rather than inserting all their bytes into database tables by default.

## 24.4 File references

Use stable identifiers and carefully managed paths. If an artifact is moved or deleted, the application should report that it is unavailable instead of silently substituting another file.

## 24.5 Export portability

Exports should include enough metadata to interpret the results independently.

A portable export may contain:

- Manifest JSON.
- Signature file.
- Public key or public-key reference.
- Verification instructions.
- Experiment configuration.
- Metrics CSV.
- Relevant artifact hashes.

A report that references local absolute paths may not remain usable on another computer. Where portability is required, use relative paths or package the explicitly selected artifacts.

---

# 25. Configuration and Reproducibility

## 25.1 Configuration principles

Experiment parameters should be configurable and recorded.

Examples include:

- Dataset location.
- Data directory.
- SQLite database location.
- Training batch size.
- Epoch count.
- Optimizer settings.
- Random seed.
- Tampering rate.
- Tampering strategy.
- Watermark method.
- Detection threshold.
- Output directory.
- Logging level.

## 25.2 Example configuration

The following JSON is illustrative. The application must define and validate its actual configuration schema before using such a file.

```json
{
  "application": {
    "name": "PQ-AI Provenance",
    "version": "0.1.0"
  },
  "ml": {
    "dataset": "CIFAR10",
    "model": "ResNet18",
    "batch_size": 128,
    "epochs": 20,
    "learning_rate": 0.001,
    "seed": 42
  },
  "tampering": {
    "supported_rates": [0.01, 0.05, 0.10],
    "preserve_original": true
  },
  "cryptography": {
    "hash_algorithm": "SHA-256",
    "signature_algorithm": "ML-DSA-65"
  },
  "storage": {
    "database_filename": "provenance.sqlite"
  }
}
```

The values are example settings, not a validated optimal training configuration.

## 25.3 Reproducibility record

Every experiment should capture:

- Application version.
- Python version.
- Dependency versions.
- Operating system.
- Hardware and execution device.
- Random seed.
- Dataset fingerprint.
- Training and evaluation splits.
- Configuration.
- Start and end timestamps.
- Result metrics.
- Artifact identifiers and hashes.

This makes it easier to interpret differences between experiments and diagnose unexpected results.

---

# 26. Installation

Installation instructions must be validated against the actual dependency versions and cryptographic backend used by the project.

The following steps provide a development setup template.

## 26.1 Prerequisites

Install:

- Python 3.11 or a compatible version supported by the selected dependencies.
- Git.
- A C/C++ build toolchain if required by native dependencies.
- The platform-specific dependencies required by the chosen cryptographic backend.
- A compatible PyTorch and Torchvision combination.

GPU acceleration is optional. The baseline workflow should have a CPU execution path.

## 26.2 Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd PQ-AI-Provenance
```

Replace the placeholder with the actual repository URL.

## 26.3 Create a virtual environment

Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, follow your system's Python and PowerShell environment guidance rather than changing security settings blindly. You can also invoke the environment's Python executable directly.

## 26.4 Upgrade packaging tools

```bash
python -m pip install --upgrade pip setuptools wheel
```

## 26.5 Install project dependencies

If the repository maintains a `requirements.txt` file:

```bash
python -m pip install -r requirements.txt
```

If the project uses `pyproject.toml` for package installation, the development installation may instead use:

```bash
python -m pip install -e .
```

Use the dependency-management method actually configured in the repository. Do not maintain conflicting dependency versions across multiple files.

## 26.6 Cryptographic backend installation

The selected backend may require native libraries, development headers, or platform-specific build steps.

Consult the official installation instructions for the exact backend and version chosen.

After installation, test ML-DSA-65 key generation, signing, and verification in isolation before integrating it with the GUI.

Do not assume that installing a Python package automatically installs every required native dependency.

## 26.7 Verify the environment

Useful checks include:

```bash
python --version
python -m pip --version
python -m pip check
```

Once implemented, the project should also provide a diagnostic command that reports whether PySide6, PyTorch, Torchvision, the cryptographic backend, and SQLite are available.

---

# 27. Running the Application

The current desktop launcher is the root-level `main.py` file.

```bash
python main.py
```

For packaging, build with PyInstaller after the dependencies are installed:

```bash
pyinstaller PQAI.spec
```

Use only the command that corresponds to the actual entry point on your machine.

## 27.1 Expected first-run workflow

A completed application should guide a user through the following sequence:

1. Open the application.
2. Configure a data directory.
3. Select or download CIFAR-10.
4. Inspect and fingerprint the dataset.
5. Create a provenance manifest.
6. Generate or select a signing key.
7. Sign and verify the manifest.
8. Configure a baseline ResNet-18 experiment.
9. Train and evaluate the model.
10. Save the checkpoint and experiment metadata.
11. Create controlled tampering experiments.
12. Configure and evaluate a model watermark.
13. Run robustness experiments.
14. Review results.
15. Export selected records.

Individual stages should be usable and testable without requiring all later stages to be completed.

---

# 28. Command-Line Interface

An optional CLI can improve automation, debugging, testing, and reproducibility.

The CLI is a planned extension unless these commands have already been implemented.

A possible command design is:

```text
pqai hash <dataset-path>
pqai manifest create <dataset-path>
pqai manifest sign <manifest-path>
pqai manifest verify <manifest-path> <signature-path>
pqai dataset verify <dataset-path> <manifest-path>
pqai train --config <config-path>
pqai tamper --config <config-path>
pqai watermark evaluate --config <config-path>
pqai experiment report <experiment-id>
```

The actual command names and options must match the implemented CLI.

## 28.1 CLI design requirements

- Use explicit subcommands and argument validation.
- Return non-zero exit codes for failures.
- Keep standard output suitable for machine-readable output when requested.
- Send diagnostic messages to standard error or structured logs.
- Never print private keys or secret watermark material.
- Support configuration files and explicit overrides.
- Record the effective configuration for experiments.
- Avoid executing shell commands built from untrusted input.

The GUI and CLI should share backend services instead of maintaining two independent implementations of cryptographic or ML operations.

---

# 29. Testing and Quality Assurance

## 29.1 Testing strategy

The project should use multiple levels of testing.

### Unit tests

Test individual functions in isolation.

Examples:

- SHA-256 digest calculation.
- Directory inventory ordering.
- Canonical manifest serialization.
- Manifest validation.
- Signature encoding and decoding.
- Signature verification.
- Tampering-rate calculations.
- Metric calculations.
- SQLite repository behavior.

### Integration tests

Test interactions between components.

Examples:

- Hash a dataset, create a manifest, sign it, and verify it.
- Modify a file and confirm that fingerprint verification detects the difference.
- Create a training record and associate a checkpoint with it.
- Save and reload experiment metadata.
- Export an experiment report and validate its contents.

### GUI tests

Test:

- Window creation.
- Navigation.
- Input validation.
- Progress updates.
- Error presentation.
- Worker completion.
- Safe application shutdown.

### ML tests

Use small synthetic datasets for fast tests.

Test:

- Dataset loading.
- Model initialization.
- A minimal training step.
- Evaluation metrics.
- Checkpoint save and load.
- Tampering selection and counts.

Full CIFAR-10 training should not be required for every unit-test run.

### Packaging tests

Test the packaged application on each target operating system.

A successful PyInstaller command alone is not sufficient evidence that the application works.

## 29.2 Cryptographic negative tests

Test failure conditions including:

- Altered manifest bytes.
- Corrupted signatures.
- Wrong public keys.
- Missing key files.
- Invalid key encodings.
- Unsupported algorithms.
- Malformed manifests.
- Dataset fingerprint mismatches.
- Missing dataset files.
- Backend initialization failures.

A test suite must never treat an exception or unavailable backend as successful verification.

## 29.3 Watermark tests

Test:

- Detection of the expected watermark.
- Detection on a model without the watermark.
- Threshold handling.
- Invalid watermark configuration.
- Checkpoint loading failures.
- Evaluation after each supported transformation.

Use a suitable negative evaluation set to measure false positives.

## 29.4 Running tests

When pytest is configured:

```bash
python -m pytest
```

For a specific test file:

```bash
python -m pytest tests/unit/test_hash_utils.py
```

For verbose output:

```bash
python -m pytest -v
```

These commands assume the corresponding tests and project structure exist.

## 29.5 Code quality

The project should aim for:

- Clear module boundaries.
- Type hints on important interfaces.
- Consistent formatting.
- Focused exception handling.
- No hardcoded machine-specific paths.
- No secrets in source control.
- Regression tests for bug fixes.
- Documentation updates for changed behavior.

Only report test results that were actually observed.

---

# 30. Security Considerations

Security is a central part of PQ-AI Provenance, but it extends beyond the choice of signature algorithm.

## 30.1 Private-key protection

A digital signature is only as trustworthy as the protection of its signing key.

If an attacker obtains the private key, they may be able to create signatures that verify under the corresponding public key.

The application should:

- Avoid logging private-key contents.
- Avoid including private keys in exported reports.
- Keep key storage separate from public provenance artifacts.
- Apply appropriate operating-system access controls.
- Consider encrypted storage or operating-system credential facilities.
- Explain the consequences of key loss.
- Provide a documented key replacement or revocation workflow where appropriate.

Encryption and access controls reduce risk but do not make key theft impossible.

## 30.2 Key trust

The application should record the public key used for verification and provide a way to inspect its fingerprint.

The user needs a trustworthy way to associate the public key with the expected signer. Merely loading a public key from the same untrusted folder as the manifest is not sufficient to establish that association.

## 30.3 Manifest immutability

Once signed, a manifest should be treated as immutable.

When metadata changes, create a new version or linked record and sign the new bytes.

## 30.4 Untrusted input

Datasets, manifests, checkpoints, configuration files, and exported records may be malformed or malicious.

The application should:

- Validate file formats.
- Handle path traversal carefully.
- Avoid following unexpected symbolic links without a defined policy.
- Limit resource consumption where practical.
- Handle decompression and allocation errors.
- Use safe model-loading practices.
- Avoid executing imported files as code.
- Avoid launching external commands with unsanitized input.

## 30.5 Database integrity

SQLite is convenient for local persistence, but ordinary database records can be modified by someone with sufficient filesystem access.

The project should not describe its database as tamper-proof without a separate, validated integrity mechanism.

## 30.6 Logging

Logs should support debugging without leaking:

- Private keys.
- Passwords.
- Secret watermark triggers.
- Sensitive user data.
- Unnecessary absolute paths or personal information.

## 30.7 Supply-chain security

The project should:

- Use trusted dependency sources.
- Track dependency versions.
- Review native-library requirements.
- Update vulnerable dependencies.
- Avoid downloading executable components from untrusted sources.
- Document build environments.
- Consider release checksums and artifact signing.

---

# 31. Threat Model

A useful project should define what it intends to detect and what it does not defend against.

| Threat or event | Intended response | Important limitation |
|---|---|---|
| Accidental file corruption | Detect changed hashes. | Only relative to a trustworthy recorded fingerprint. |
| Dataset modification after signing | Detect a fingerprint mismatch. | The application must compare against the correct signed manifest. |
| Manifest modification | Signature verification should fail. | Only if the verifier uses a trusted public key and the exact signed bytes. |
| Corrupted signature | Report verification failure. | Error handling must not turn failure into success. |
| Wrong public key | Report signature failure. | Key trust still requires a defined process. |
| Replacement of manifest, signature, and key together | May be detectable if a trusted key or record exists independently. | A verifier that trusts all files from the same untrusted source may accept the attacker's own record. |
| Private-key theft | Limit exposure and document key recovery. | Cryptography cannot protect a key that has already been compromised. |
| Dataset contamination before signing | Not automatically detected. | A cleanly signed contaminated dataset remains contaminated. |
| Dishonest training procedure | Record configuration and artifacts. | Metadata and signatures do not prove the procedure was followed honestly. |
| Model checkpoint modification | Compare checkpoint fingerprints. | A matching hash does not establish model quality. |
| Watermark removal | Measure detection after selected transformations. | No guarantee against all attacks. |
| Malicious imported checkpoint | Validate input and use safe loading. | Complete protection against all malformed artifacts is not guaranteed. |
| Database tampering | Optionally detect changes through additional controls. | Ordinary SQLite records are not inherently immutable. |
| Compromised operating system | Outside the initial protection scope. | Local attackers with sufficient privileges may alter files, keys, or execution. |

## 31.1 Security objective

The primary objective is to make selected changes detectable and to create more trustworthy, reproducible records of the experiments performed.

The application is not intended to provide a complete secure execution environment or a universal proof of AI trustworthiness.

---

# 32. Limitations

## 32.1 A valid signature does not prove a dataset is clean

A signer can sign a manifest describing a dataset that already contains errors, biased samples, corrupted labels, or malicious content.

The signature authenticates the signed record under the relevant key-trust assumptions. It does not certify the scientific quality of the dataset.

## 32.2 A hash does not prove authenticity

A hash identifies content relative to a reference digest. If both the file and its unsigned digest can be replaced, the digest alone cannot authenticate the file.

## 32.3 Provenance does not prove honest training

Recording a dataset, configuration, and checkpoint helps document a training run. It does not prove that every recorded step was performed as described.

## 32.4 Watermark robustness is method-dependent

A watermark may survive some transformations and fail under others. Results depend on the embedding and detection methods, thresholds, model, dataset, and transformation parameters.

## 32.5 Benchmark results depend on the environment

Training time and cryptographic performance vary with CPU, GPU, memory, operating system, library versions, and implementation choices.

## 32.6 Reproducibility is not absolute

Random seeds improve repeatability, but identical results are not guaranteed across every hardware and software configuration.

## 32.7 Post-quantum cryptography does not secure the entire application

ML-DSA-65 is one cryptographic component. It does not automatically protect private-key storage, database files, model checkpoints, application dependencies, or the user's operating system.

## 32.8 Local-first design has trade-offs

Local execution provides control over data and avoids mandatory server infrastructure. It also means that users must manage backups, key protection, disk capacity, and data migration themselves.

## 32.9 Initial dataset scope

CIFAR-10 and ResNet-18 provide a manageable experimental baseline. Results on this dataset should not be generalized automatically to large language models, medical datasets, production vision systems, or other model families.

---

# 33. Cross-Platform Packaging

## 33.1 Goal

The intended release targets are:

- Windows.
- Linux.
- macOS.

PyInstaller is the planned packaging tool.

## 33.2 Platform-specific builds

PyInstaller is not a universal cross-compilation solution. A release should normally be built and tested on the target operating system. The included `PQAI.spec` file is the starting point for those builds.

This means maintaining separate build workflows for Windows, Linux, and macOS.

## 33.3 Packaging concerns

The build must account for:

- PySide6 and Qt plugins.
- PyTorch and Torchvision dependencies.
- Native cryptographic libraries.
- Python package imports.
- Application icons and resources.
- Configuration defaults.
- Writable user-data directories.
- Dataset and checkpoint paths.
- Runtime errors and logging.

## 33.4 Keep user data outside the executable

Do not bundle personal datasets, generated checkpoints, signing private keys, or experiment databases into the application executable.

The packaged application should create or open a suitable user-data directory at runtime.

The desktop dashboard stores working files under the user profile by default, and the UI lets you override the dataset, model, results, key, and tampered-dataset paths.

## 33.5 Release validation

For each operating system:

1. Install dependencies in the build environment.
2. Run automated tests.
3. Build the application.
4. Launch the packaged build.
5. Test cryptographic operations.
6. Test dataset loading.
7. Test at least one minimal training workflow.
8. Test persistence and exports.
9. Inspect startup and shutdown behavior.
10. Test on a clean environment where practical.

The supported Python version, operating-system versions, architecture, and any GPU limitations should be documented for each release.

---

# 34. Troubleshooting

This section lists common development issues and recommended diagnostic steps.

## 34.1 PySide6 import errors

Possible causes:

- Incorrect virtual environment.
- Incomplete installation.
- Conflicting Python installations.
- Incompatible package versions.

Check:

```bash
python -c "import PySide6; print(PySide6.__version__)"
python -m pip check
```

## 34.2 PyTorch cannot access the GPU

Possible causes include a CPU-only PyTorch installation, missing compatible GPU drivers, or an unsupported hardware/software combination.

Check:

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

A result of `False` means CUDA is not available through that installation and environment. The application should still support CPU execution where practical.

## 34.3 Cryptographic algorithm unavailable

Possible causes:

- Missing native backend.
- Unsupported backend version.
- Incorrect algorithm identifier.
- Mismatched Python bindings and native library.
- Platform-specific build failure.

Check the selected library's official documentation and inspect its available algorithms. Do not substitute an unrelated signature algorithm without explicitly changing the configuration and recorded algorithm identifier.

## 34.4 Signature verification fails

Check:

- Whether the manifest bytes are identical to the bytes that were signed.
- Whether canonical serialization is consistent.
- Whether the correct signature file was loaded.
- Whether the public key corresponds to the signing key.
- Whether encoding and decoding preserved the original bytes.
- Whether the manifest was modified.
- Whether the selected algorithm and parameter set match.

A failed verification must remain a failure until the cause is understood.

## 34.5 Dataset fingerprint mismatch

Check:

- Whether any files changed.
- Whether the inventory includes the same paths.
- Whether excluded files differ.
- Whether relative-path normalization changed.
- Whether the dataset is incomplete.
- Whether the manifest describes the same dataset version.

Do not automatically overwrite the recorded fingerprint to make the mismatch disappear.

## 34.6 Training is slow

Possible improvements include:

- Reducing the number of epochs during development.
- Using smaller batches when memory is limited.
- Avoiding unnecessary dataset reprocessing.
- Using supported hardware acceleration.
- Profiling data loading and model execution separately.

Any change affecting the experiment configuration should be recorded.

## 34.7 GUI becomes unresponsive

Long-running operations may be executing on the main UI thread.

Move training, hashing, and large-file operations to appropriate worker threads or another supported execution mechanism. Update widgets through Qt signals and slots.

## 34.8 Packaged application fails to start

Build with diagnostic output and inspect missing imports, shared libraries, Qt plugins, resources, and writable paths.

Reproduce the issue in a clean environment and make the smallest verified fix.

---

# 35. Development Roadmap

The following roadmap organizes development into stages. It is a proposed plan, not a statement that the stages are complete.

## Phase 1: Project foundation

- Establish the repository structure.
- Create the virtual environment.
- Configure dependencies.
- Implement application configuration.
- Establish logging and error handling.
- Set up pytest.
- Build a minimal PySide6 window.
- Add repository-wide Copilot instructions and Agent Skills.

**Deliverable:** A launchable application skeleton with a working test environment.

## Phase 2: Cryptographic foundation

- Implement SHA-256 file hashing.
- Implement deterministic file inventories.
- Define the manifest schema.
- Implement canonical serialization.
- Integrate ML-DSA-65.
- Implement key generation.
- Implement signing and verification.
- Add negative tests.
- Document key storage and trust assumptions.

**Deliverable:** A tested command or service that can create and verify signed provenance records.

## Phase 3: Dataset provenance

- Implement dataset scanning.
- Generate aggregate fingerprints.
- Create dataset manifests.
- Store provenance metadata.
- Detect file changes.
- Add dataset comparison views.
- Export manifests and verification results.

**Deliverable:** A usable dataset integrity and provenance workflow.

## Phase 4: Baseline machine learning

- Implement CIFAR-10 loading.
- Implement ResNet-18 configuration.
- Implement training and evaluation.
- Add checkpoint management.
- Record experiment metadata.
- Persist results.
- Visualize baseline metrics.

**Deliverable:** A reproducible baseline image-classification experiment.

## Phase 5: Dataset tampering

- Implement configurable tampering operations.
- Support 1%, 5%, and 10% experiment rates.
- Preserve the original dataset.
- Record modified sample identities.
- Fingerprint experimental variants.
- Compare model metrics.
- Export experiment results.

**Deliverable:** Controlled and repeatable dataset-tampering experiments.

## Phase 6: Model watermarking

- Select and document a watermarking method.
- Implement embedding.
- Implement detection.
- Establish baseline detection tests.
- Measure clean-model utility.
- Record watermark configurations and outcomes.

**Deliverable:** A validated baseline watermarking experiment.

## Phase 7: Robustness evaluation

- Implement fine-tuning experiments.
- Implement a defined pruning procedure.
- Implement a defined quantization or compression procedure.
- Compare detection rates and model performance.
- Add visualizations and structured reports.

**Deliverable:** A controlled model-watermark robustness evaluation workflow.

## Phase 8: Desktop integration

- Connect the services to PySide6 screens.
- Implement background execution.
- Add progress reporting.
- Add verification-result views.
- Add experiment history and comparison screens.
- Add export workflows.
- Test error and shutdown behavior.

**Deliverable:** An integrated desktop application.

## Phase 9: Release preparation

- Complete regression tests.
- Audit security-sensitive operations.
- Finalize dependency versions.
- Build on each supported OS.
- Validate packaged workflows.
- Write installation and troubleshooting instructions.
- Publish release artifacts and documented limitations.

**Deliverable:** Tested platform-specific release packages.

---

# 36. Future Enhancements

After the initial system is stable, potential extensions include:

## 36.1 Additional datasets

Add support for datasets beyond CIFAR-10, with configurable loaders, metadata schemas, and preprocessing.

## 36.2 Additional model architectures

Support additional convolutional networks and other model families, with architecture-specific experiment configurations.

## 36.3 More watermarking methods

Compare different watermarking techniques under a common, clearly documented evaluation framework.

## 36.4 Provenance chains

Link dataset versions, preprocessing steps, training runs, checkpoints, and model transformations into an explicit provenance graph.

## 36.5 Signed experiment reports

Sign selected experiment records and exports so that their recorded contents can be authenticated independently.

## 36.6 Key-management improvements

Investigate operating-system key stores, encrypted private-key files, key rotation, revocation records, and trusted public-key distribution.

## 36.7 Extended cryptographic benchmarks

Measure behavior across different manifest sizes, hardware configurations, and supported implementations.

## 36.8 Additional tampering strategies

Explore more dataset modifications while preserving a clear distinction between the operation performed and the conclusions supported by the results.

## 36.9 Experiment comparison tools

Add multi-run comparisons, statistical summaries, confidence intervals, and better visualizations of variability.

## 36.10 Reproducible export bundles

Create self-contained experiment bundles containing manifests, signatures, public-key references, configurations, metrics, and artifact fingerprints.

Each extension should be added only after its security assumptions, implementation requirements, and testing strategy are defined.

---

# 37. Skills for GitHub Copilot

The repository uses Agent Skills under `.agents/skills/` to provide focused instructions for different development tasks.

These skills are intended to guide coding behavior. They do not install dependencies, validate the implementation automatically, or replace testing and code review.

## 37.1 Available project skills

| Skill | Responsibility |
|---|---|
| `pqc-cryptography` | SHA-256, ML-DSA-65, manifests, signatures, key handling, and verification. |
| `pytorch-ml-experiments` | CIFAR-10, ResNet-18, training, metrics, reproducibility, and checkpoints. |
| `ai-provenance-watermarking` | Provenance relationships, watermark embedding, detection, and robustness evaluation. |
| `pyside6-desktop-app` | Desktop screens, Qt workers, signals, progress reporting, and UI integration. |
| `cross-platform-packaging` | PyInstaller, native dependencies, OS-specific builds, and release validation. |
| `python-testing-quality` | pytest, error handling, type hints, regression tests, and code quality. |

## 37.2 Skill location

```text
.agents/
└── skills/
    ├── pqc-cryptography/
    │   └── SKILL.md
    ├── pytorch-ml-experiments/
    │   └── SKILL.md
    ├── ai-provenance-watermarking/
    │   └── SKILL.md
    ├── pyside6-desktop-app/
    │   └── SKILL.md
    ├── cross-platform-packaging/
    │   └── SKILL.md
    └── python-testing-quality/
        └── SKILL.md
```

Each skill should have valid YAML frontmatter with a name matching its directory and a useful description.

Repository-wide instructions can be maintained separately in `.github/copilot-instructions.md`.

## 37.3 Suggested development sequence

Begin with cryptography and testing. Establish a trustworthy manifest and signature workflow before connecting it to the ML pipeline.

Then implement dataset management, baseline training, tampering experiments, and watermarking. Integrate these services into the desktop interface after the underlying operations have reliable tests.

Packaging should come after the application can run and its core workflows can be tested.

---

# 38. Contribution Guidelines

Contributions should improve correctness, reproducibility, maintainability, or usability without weakening the project's security properties.

## 38.1 Before making a change

- Inspect existing modules.
- Identify the responsible subsystem.
- Check whether equivalent functionality already exists.
- Review related tests.
- Read the relevant project skill.
- Confirm the intended behavior and failure cases.

## 38.2 During development

- Keep changes focused.
- Avoid unnecessary architectural rewrites.
- Preserve existing interfaces where possible.
- Add type hints and documentation for important APIs.
- Avoid hardcoded machine-specific paths.
- Never add secrets or personal datasets to source control.
- Use synthetic data for ordinary automated tests.
- Keep the original dataset and baseline checkpoints unchanged during experiments.

## 38.3 Before submitting a change

- Run relevant tests.
- Run broader regression tests when practical.
- Update documentation if behavior changes.
- Report any tests that could not be run.
- Document new dependencies.
- State any security implications.
- Do not claim that an operation is secure or complete without appropriate evidence.

---

# 39. Academic and Research Applications

PQ-AI Provenance can serve as a foundation for research into the relationship between cryptographic records and machine-learning integrity.

Potential research questions include:

1. What is the performance overhead of ML-DSA-65 when signing and verifying dataset provenance records of different sizes?
2. How reliably can SHA-256 fingerprints detect changes to recorded dataset contents?
3. How do different types of dataset corruption affect ResNet-18 classification metrics?
4. How do different watermarking methods affect clean-model accuracy?
5. How does watermark detection change after fine-tuning, pruning, and quantization?
6. What metadata is necessary to reproduce a training run meaningfully?
7. What security assumptions are required to trust a signed dataset manifest?
8. How do local key storage and public-key distribution affect the trustworthiness of the provenance workflow?

## 39.1 Experimental reporting

A research report should clearly describe:

- The dataset and its version.
- The baseline model.
- The exact tampering and watermarking methods.
- The experiment configurations.
- The cryptographic backend and version.
- The hardware and software environment.
- The number of runs.
- The metrics and statistical methods.
- The observed results.
- The limitations and threats to validity.

The report should distinguish implementation validation from empirical evaluation and should not generalize results beyond the conditions actually tested.

---

# 40. Glossary

| Term | Definition |
|---|---|
| AI provenance | Records describing the origins, processing, and relationships of AI artifacts. |
| Artifact | A file or object produced or used by an experiment, such as a checkpoint or manifest. |
| Checkpoint | A saved representation of model state, optionally including training state. |
| Canonical serialization | A deterministic representation of structured data as bytes. |
| Dataset fingerprint | A digest representing defined dataset contents and inventory rules. |
| Digital signature | A cryptographic value used to verify a message against a public key. |
| F1 score | The harmonic mean of precision and recall under a specified averaging scheme. |
| Fingerprint mismatch | A difference between an observed digest and a recorded reference digest. |
| Manifest | A structured record describing an artifact or experiment. |
| ML-DSA-65 | A standardized post-quantum digital signature algorithm parameter set. |
| Model watermark | A deliberately embedded signal intended to be detectable using a defined method. |
| Post-quantum cryptography | Cryptographic techniques designed to resist known classical and quantum attacks under specified assumptions. |
| Provenance chain | A set of linked records describing relationships between artifacts and processing stages. |
| ResNet-18 | A residual convolutional neural network architecture. |
| Robustness experiment | A controlled test of how a system behaves after a specified modification. |
| SHA-256 | A cryptographic hash function producing a 256-bit digest. |
| Signature verification | Checking whether a signature is valid for the supplied message and public key. |
| Tampering rate | The proportion of eligible samples or files modified under a documented procedure. |
| Test set | Data reserved for final evaluation under a defined experimental protocol. |
| Watermark detection rate | The proportion of designated positive watermark cases correctly detected. |

---

# 41. References

The following resources provide background on the principal technologies. Consult the documentation corresponding to the exact versions used by the implementation.

## Cryptography

- [NIST FIPS 204 — Module-Lattice-Based Digital Signature Standard](https://csrc.nist.gov/pubs/fips/204/final)
- [Open Quantum Safe — liboqs](https://openquantumsafe.org/)
- [Open Quantum Safe — liboqs GitHub repository](https://github.com/open-quantum-safe/liboqs)
- [Python hashlib documentation](https://docs.python.org/3/library/hashlib.html)

## Machine learning

- [PyTorch documentation](https://pytorch.org/docs/stable/index.html)
- [Torchvision documentation](https://pytorch.org/vision/stable/index.html)
- [CIFAR-10 dataset](https://www.cs.toronto.edu/~kriz/cifar.html)
- [Deep Residual Learning for Image Recognition](https://arxiv.org/abs/1512.03385)

## Desktop development

- [Qt for Python — PySide6 documentation](https://doc.qt.io/qtforpython-6/)
- [Python documentation](https://docs.python.org/3/)
- [SQLite documentation](https://www.sqlite.org/docs.html)

## Testing and packaging

- [pytest documentation](https://docs.pytest.org/)
- [PyInstaller documentation](https://pyinstaller.org/en/stable/)

## GitHub Copilot and Agent Skills

- [VS Code Agent Skills documentation](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [GitHub Copilot documentation](https://docs.github.com/en/copilot)

These references are starting points for implementation and research. The project's documentation should identify the exact standards, versions, methods, and sources relevant to the experiments actually performed.

---

# 42. License

The project's license has not yet been specified.

Before public distribution, select an appropriate license and add the corresponding `LICENSE` file to the repository. Review the licensing conditions of included dependencies, datasets, model weights, and any third-party watermarking implementations.

Do not label the project as MIT, Apache-2.0, or another license until that choice has been made and the repository contains the corresponding license text.

---

## Final Project Summary

PQ-AI Provenance is intended to provide an integrated experimental environment for exploring how cryptographic fingerprints, post-quantum signatures, AI dataset provenance, model watermarking, and controlled tampering experiments can work together.

Its key contribution is the separation of several questions that are often incorrectly treated as equivalent:

- **Did the file contents change?** Compare cryptographic fingerprints.
- **Does the provenance signature verify?** Verify the signed bytes against the supplied public key.
- **Does the observed dataset match the signed record?** Recompute and compare dataset fingerprints.
- **How did a dataset modification affect the model?** Conduct controlled training and evaluation experiments.
- **Did the model watermark remain detectable?** Apply the defined detector before and after documented transformations.

The system is designed to make these questions testable, record their outcomes, and present the results through a local desktop application.

Its success should be measured by the correctness of its implementation, reproducibility of its experiments, quality of its tests, and precision of its security claims—not by the number of technologies it combines.
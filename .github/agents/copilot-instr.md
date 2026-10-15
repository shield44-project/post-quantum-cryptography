# PQ-AI Provenance — Copilot Instructions

## Project purpose

Build a local-first, cross-platform desktop application for post-quantum dataset provenance, AI model watermarking, and controlled tampering experiments.

## Technology stack

- Python
- PySide6
- PyTorch and Torchvision
- CIFAR-10 and ResNet-18 for baseline experiments
- SHA-256 for fingerprints
- ML-DSA-65 for post-quantum digital signatures
- SQLite for local structured data
- CSV and JSON for exports
- Matplotlib for visualizations
- pytest for automated tests
- PyInstaller for packaging

Verify actual dependency versions and supported APIs before implementing integrations.

## Architecture rules

- Keep GUI, business logic, cryptography, ML, watermarking, provenance, and persistence separate.
- Reuse existing modules instead of duplicating functionality.
- Use pathlib and configurable data directories.
- Keep datasets, model checkpoints, signing keys, and experiment results outside packaged executables.
- Do not introduce a mandatory web server or cloud dependency.
- Do not change public interfaces unnecessarily.

## Security rules

- Never implement cryptographic primitives from scratch.
- Never expose private keys or secrets in logs, exports, or screenshots.
- Use deterministic serialization for signed manifests.
- Validate imported files and manifests.
- Never silently bypass signature verification.
- A valid signature does not prove a dataset was clean before signing or that training was honest.
- A model watermark does not guarantee ownership or tamper resistance.
- Do not claim absolute quantum security.

## ML experiment rules

- Preserve original datasets and baseline checkpoints.
- Make tampering rates configurable and record the actual changes.
- Keep train, validation, and test data appropriately separated.
- Record seeds, configurations, dataset identifiers, metrics, and relevant software versions.
- Report experimental limitations honestly.

## Development workflow

Before making changes, inspect relevant source files, configuration, and tests. Make focused changes, add or update tests, run relevant checks, and summarize what changed and what remains unverified. Never claim a build or test succeeded unless it was actually run.

## Documentation

Update README instructions when installation, configuration, security assumptions, user workflows, or packaging changes. Provide platform-specific installation and build steps where required.
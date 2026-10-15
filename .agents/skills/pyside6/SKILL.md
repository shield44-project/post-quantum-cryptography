---
name: pyside6
description: Build and maintain the PQ-AI Provenance desktop GUI using PySide6. Use for windows, widgets, navigation, forms, progress indicators, background tasks, charts, dialogs, and connecting UI actions to backend services.
---

# PySide6 Desktop App Skill

## Project context

PQ-AI Provenance is a local-first desktop application for Windows, Linux, and macOS. It uses Python and PySide6 to provide a graphical interface for dataset verification, cryptographic signing, model training, watermark experiments, and result visualization.

There should be no mandatory web dashboard or remote server.

## Architecture

Keep the GUI separate from application logic.

Recommended layers:
- `ui/`: windows, pages, widgets, dialogs, and presentation.
- `services/`: workflow orchestration and application services.
- `crypto/`: hashes, signatures, and key operations.
- `ml/`: dataset loading, training, and evaluation.
- `watermark/`: watermark embedding and detection.
- `provenance/`: manifest creation and verification.
- `storage/`: SQLite persistence and file access.
- `experiments/`: experiment configurations and results.

Inspect the existing repository before introducing new modules. Extend existing abstractions instead of creating duplicate implementations.

## UI behavior

- Use a consistent layout, typography, spacing, and navigation pattern.
- Provide clear states for idle, running, succeeded, failed, and cancelled operations where cancellation is supported.
- Validate inputs and show actionable error messages.
- Display verification results with clear explanations of what was checked.
- Show training progress, current stage, and relevant metrics.
- Include confirmation dialogs before destructive operations.
- Do not block the GUI thread during long-running tasks.
- Use Qt signals and slots to communicate between workers and the UI.
- Disable or guard controls when a concurrent operation would be unsafe.
- Keep accessibility in mind through sensible tab order, labels, keyboard navigation, and readable contrast.

## Background operations

Use an appropriate Qt worker pattern, such as QThread with worker objects, for long-running operations.

- Perform training, dataset hashing, signing, verification, and large file processing outside the GUI thread.
- Emit progress and status signals.
- Handle exceptions inside the worker and report failures safely to the UI.
- Ensure workers finish cleanly when a window closes.
- Avoid unsafe cross-thread UI updates.
- Support cancellation only where the underlying operation can implement it safely.

## Data and security

- Use pathlib for filesystem operations.
- Store user data outside the application installation directory.
- Never display or log private keys, secrets, or sensitive information.
- Do not run shell commands by concatenating untrusted user input.
- Use prepared SQL statements for SQLite operations.
- Treat imported manifests and model files as untrusted input.
- Keep cryptographic and ML operations in backend services, not widget event handlers.

## Visualization and persistence

- Use Matplotlib or another existing project-approved charting library for experiment results.
- Use SQLite for structured local metadata and experiment history.
- Use CSV or JSON for explicitly requested exports.
- Keep paths configurable and handle missing or moved files gracefully.

## Testing

Test service behavior independently of the GUI where possible. Add GUI tests for navigation, validation, worker signals, error dialogs, and successful workflows. Ensure closing the application during a long operation does not leave unsafe background activity.
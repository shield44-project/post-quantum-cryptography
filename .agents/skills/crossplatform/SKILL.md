---
name: crossplatform
description: Package PQ-AI Provenance as a desktop application for Windows, Linux, and macOS using PyInstaller. Use for dependency management, build scripts, application resources, release artifacts, platform-specific issues, and distribution checks.
---

# Cross-Platform Packaging Skill

## Project context

PQ-AI Provenance is a Python desktop application built with PySide6, PyTorch, cryptographic dependencies, SQLite, and data-science libraries.

The application must be packaged and tested separately for each target operating system.

## Build principles

- Use a dedicated virtual environment for development and building.
- Maintain a documented dependency list and, where appropriate, a lockfile or constraints file.
- Pin or constrain dependencies when required for reproducible releases.
- Check compatibility among Python, PySide6, PyTorch, the cryptography binding, and PyInstaller.
- Use PyInstaller configuration files or maintained build scripts rather than undocumented manual steps.
- Inspect the project's existing packaging configuration before creating another.
- Prefer a one-folder build initially when native libraries and plugins make one-file builds difficult.
- Never promise that one PyInstaller binary will run natively on all operating systems.

## Platform-specific builds

Build on the target operating system:
- Windows build on Windows.
- Linux build on Linux.
- macOS build on macOS.

Use separate CI jobs or documented build environments for each platform. Test on clean systems or clean virtual machines when possible.

## Native dependencies

- Check whether cryptographic libraries require native shared libraries or runtime components.
- Confirm Qt platform plugins and required resources are included.
- Confirm PyTorch and Torchvision load successfully in the packaged application.
- Inspect dynamic-library errors instead of assuming hidden imports are the only issue.
- Add explicit hidden imports or data files only when verified to be necessary.
- Do not bundle native libraries from one operating system into another platform's package.

## Files and resources

- Bundle only resources needed at runtime, such as icons, UI assets, and default configuration.
- Keep downloaded datasets, model checkpoints, signing keys, and user experiment records outside the executable.
- Resolve bundled resources using a packaging-aware resource path strategy.
- Resolve writable user data using an appropriate per-user application-data directory.
- Never write user data into a read-only installation directory.
- Do not include private keys, personal datasets, or development secrets in releases.

## Release process

1. Run automated tests.
2. Verify dependency compatibility.
3. Build for the target OS.
4. Launch the packaged application on a clean environment.
5. Test dataset loading, hashing, signing, verification, training, watermark evaluation, and exporting.
6. Check logs and startup behavior.
7. Document supported operating systems and known limitations.
8. Publish checksums and version information for release artifacts when appropriate.

## Troubleshooting

When a packaged app fails:
- Capture the full error output.
- Test with console output enabled.
- Inspect missing imports, shared libraries, Qt plugins, and model files.
- Reproduce the failure in a clean environment.
- Make the smallest change that resolves the confirmed cause.

Never claim a release is cross-platform or production-ready merely because the build command completed successfully.
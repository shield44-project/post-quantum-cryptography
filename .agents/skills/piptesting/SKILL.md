---
name: piptesting
description: Maintain Python code quality, automated tests, type hints, error handling, logging, dependency management, and regression coverage for PQ-AI Provenance. Use when adding features, refactoring code, fixing bugs, or preparing a release.
---

# Python Testing and Quality Skill

## Project context

PQ-AI Provenance combines cryptography, dataset processing, machine learning, watermarking, SQLite persistence, and a PySide6 desktop interface. Changes in one subsystem must not silently break the others.

## Before editing code

- Inspect the relevant files and understand the existing architecture.
- Search for existing helpers, services, models, and tests before adding new ones.
- Preserve established interfaces unless a change is necessary.
- Avoid rewriting entire modules to make a small fix.
- Identify affected workflows and add regression tests.
- Do not invent dependency APIs; check project versions and actual signatures.

## Code quality

- Follow PEP 8 and use descriptive names.
- Add type hints to public functions and important interfaces.
- Keep functions focused and avoid unnecessary global state.
- Use pathlib for filesystem paths.
- Use context managers for files and database connections where appropriate.
- Use parameterized SQL queries.
- Catch specific exceptions and provide actionable error messages.
- Use Python logging rather than scattered debug prints in application code.
- Avoid hardcoded absolute paths and machine-specific settings.
- Do not suppress errors or use broad exception handlers without a clear reason.
- Keep secrets out of source code, logs, test fixtures, and exported reports.

## Testing strategy

Use pytest and organize tests by subsystem.

### Unit tests
Test:
- SHA-256 hashing and file-change detection
- Manifest serialization and validation
- Signature generation and verification
- Dataset tampering-rate calculations
- Model metric calculations
- Watermark detection logic
- SQLite persistence and export formatting
- Configuration and path handling

### Integration tests
Test workflows that connect:
- Dataset fingerprinting, manifest generation, signing, and verification
- Dataset loading, model training, checkpoint creation, and evaluation
- Watermark embedding, detection, and robustness experiments
- GUI actions, background workers, and persistence services

### Negative tests
Include:
- Missing or corrupted files
- Invalid manifests
- Wrong keys and invalid signatures
- Missing optional dependencies
- Invalid configurations
- Database errors
- Model checkpoint loading failures
- Interrupted or failed background operations

Use temporary directories, synthetic datasets, and test keys. Do not depend on personal files or production credentials.

## Running tests

- Run focused tests after each change.
- Run the broader test suite before declaring a task complete.
- Keep ordinary unit tests fast.
- Mark expensive model-training and hardware-dependent tests separately.
- Do not claim tests passed unless they were actually run.
- Report the command executed, the outcome, and any tests that could not run.

## Dependencies and documentation

- Update dependency files when introducing new packages.
- Avoid adding a large dependency for a small utility without justification.
- Document configuration variables and platform-specific requirements.
- Update README instructions when installation, behavior, or commands change.
- Add type checking or linting only in a way compatible with the project's existing tooling.

## Definition of done

A change is ready when:
1. The implementation matches the requested behavior.
2. Relevant tests pass.
3. Failure cases are handled clearly.
4. Security-sensitive behavior has appropriate tests.
5. Documentation is updated when needed.
6. No unrelated files or behavior were changed accidentally.
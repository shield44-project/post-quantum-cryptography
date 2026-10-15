---
name: cryptography
description: Implement and review post-quantum cryptography, ML-DSA-65 digital signatures, SHA-256 dataset fingerprints, provenance manifests, key management, and signature verification. Use when working on signing, verification, cryptographic records, or integrity checks.
---

# PQC Cryptography Skill

## Project context

This project, PQ-AI Provenance, is a local-first desktop application for dataset provenance, AI model watermarking, and tampering experiments. It uses SHA-256 for fingerprints and ML-DSA-65 for post-quantum digital signatures.

## Responsibilities

- Implement cryptographic functionality in dedicated modules, separate from the GUI.
- Use a maintained, compatible ML-DSA implementation, such as a supported liboqs binding, after checking the installed API and version.
- Use ML-DSA-65 consistently for key generation, signing, and verification.
- Use SHA-256 to fingerprint dataset files and canonical provenance records.
- Create deterministic manifest serialization before hashing or signing.
- Include relevant metadata in manifests, such as dataset identity, file hashes, creation time, algorithm identifiers, and schema version.
- Verify signatures against the exact signed bytes and the corresponding public key.
- Treat a changed manifest, dataset fingerprint, signature, or public key as a verification failure where applicable.
- Handle malformed files, missing keys, invalid signatures, unavailable algorithms, and cryptographic library errors safely.
- Keep private signing keys separate from exported public provenance records.
- Never log or export private keys, secret material, or sensitive data.
- Document key storage, backup, rotation, and loss limitations.

## Security rules

- Never implement cryptographic algorithms from scratch.
- Never substitute a hash comparison for digital signature verification.
- Never use an insecure fallback if the requested algorithm is unavailable.
- Never claim that a signature proves the original dataset was clean or that model training was honest.
- Never describe ML-DSA-65 as providing an absolute guarantee against every quantum or classical attack.
- Clearly distinguish integrity, authenticity, and provenance claims.
- Do not silently regenerate keys when verification fails.

## Architecture

Keep cryptographic operations in reusable service modules. The GUI should call those services instead of implementing cryptographic logic itself.

Suggested modules:
- `crypto/hash_utils.py`
- `crypto/signatures.py`
- `crypto/key_manager.py`
- `provenance/manifest.py`

Adapt these paths to the existing repository rather than duplicating existing modules.

## Testing

Test successful signing and verification, altered manifests, wrong public keys, corrupted signatures, missing files, invalid inputs, and unavailable cryptographic backends. Use temporary test keys and synthetic data. Never use production private keys in tests.

Before implementing a library integration, inspect its actual installed version, supported algorithm identifiers, and function signatures. Do not invent APIs.
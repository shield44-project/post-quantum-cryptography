---
name: provenance
description: Design dataset provenance records, model lineage tracking, AI model watermarking, ownership-signal evaluation, and robustness experiments. Use when implementing provenance workflows, watermark embedding or detection, or model tampering analysis.
---

# AI Provenance and Watermarking Skill

## Project context

PQ-AI Provenance connects dataset integrity, signed provenance records, model training, watermark experiments, and evaluation reports.

Keep the following concepts separate:

1. Dataset integrity: whether observed file contents match recorded hashes.
2. Provenance authenticity: whether a record has a valid signature from the corresponding signing key.
3. Model lineage: which dataset and configuration were associated with a training run.
4. Model watermarking: whether a chosen ownership signal can be detected in a model.
5. Model robustness: how performance or watermark detection changes after specified modifications.

None of these alone proves the entire training process was trustworthy.

## Provenance workflow

- Generate a manifest containing dataset identity, hashes, schema version, timestamps, and relevant training metadata.
- Sign the canonical manifest using the cryptography service.
- Verify the signature before relying on the manifest's authenticity.
- Recompute dataset fingerprints and compare them with recorded fingerprints.
- Link training runs to the manifest identifier, model architecture, configuration, and resulting checkpoint hash.
- Preserve previous records when a dataset or model changes; create a new version or event instead of rewriting history.
- Clearly distinguish verified facts, user-supplied claims, and locally recorded observations.

## Watermark design

- Keep watermark embedding, detection, and evaluation in separate modules.
- Define the watermark method, secret material, trigger or signal, thresholds, and expected detection procedure explicitly.
- Use a controlled, documented watermark method suitable for research.
- Keep watermark secrets separate from public experiment reports.
- Avoid embedding private keys or sensitive credentials in model checkpoints.
- Record the model checkpoint hash before and after watermark-related operations.
- Measure clean-model performance and watermark detection performance separately.
- Document false positives, false negatives, and detection thresholds.

## Robustness experiments

Evaluate watermark behavior under controlled operations such as:
- Fine-tuning
- Pruning
- Quantization or compression
- Checkpoint serialization and reload
- Other explicitly defined model modifications

For every experiment, record:
- Original checkpoint identifier and hash
- Transformation and parameters
- Dataset and evaluation configuration
- Accuracy before and after modification
- Watermark detection rate
- False-positive or false-negative measurements where applicable
- Random seed and software versions

Use reproducible copies of checkpoints. Never overwrite the baseline model.

## Reporting

Generate structured CSV or JSON experiment records and human-readable summaries. Graphs should have labelled axes, units, legends, and clear baselines.

Do not claim that a watermark guarantees ownership, cannot be removed, proves a model was not tampered with, or is universally robust. Present observed results with the exact experimental conditions and limitations.

## Integration

Use the cryptography service for signatures and hashing, the ML experiment service for model training and evaluation, and the persistence layer for experiment records. Do not duplicate those implementations inside the watermark module.

Test embedding, detection, threshold handling, missing metadata, corrupted checkpoints, and robustness evaluation with small controlled models.
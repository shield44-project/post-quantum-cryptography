# Threat model

## What we protect
A trained image-classification model and the claim that it was produced by a
specific developer from a specific, committed dataset.

## Who is involved
- Developer: trains the model, signs a manifest, embeds a watermark payload.
- Auditor: receives the model, public key, signed manifest and watermark key,
  then verifies authenticity.

## Attackers
1. Remover: has the model weights and wants to erase the watermark.
   Capabilities: fine-tuning, pruning, quantization, adding noise,
   overwriting with a second watermark.
2. Forger: wants to pass off a model as someone else's.
   Capabilities: copies the manifest, tries to forge signatures,
   embeds their own watermark.
3. Poisoner: alters training data.
   Capabilities: modifies samples before or after signing.

## What the system claims
- The model carries a payload bound to a manifest signed by the developer's
  ML-DSA key.
- Changing the manifest or dataset commitment breaks verification.
- The watermark survives the Remover's attacks listed above, within
  measured limits.

## What the system does NOT claim
- It does not prove the data was clean before signing.
- It does not prove the weights were trained on the committed dataset.
- It does not defend against distillation (out of scope).
- It requires white-box access to the weights.

## Assumptions
- The developer's private key is kept secret.
- The watermark key (seed) is shared only with trusted auditors.
- The post-quantum security of ML-DSA holds.
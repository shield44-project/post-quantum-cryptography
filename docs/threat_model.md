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

## Measured against the Remover (Phase 6 and 6b)
- Accidental lifecycle changes (fine-tuning, pruning, quantization, noise, output-channel
  rescaling) never removed the mark while the model stayed useful.
- Function-preserving obfuscation (Phase 6 found it; Phase 6b fixes it): reordering or
  positively rescaling the channels that feed the carrier layer leaves the model's answers
  identical but scrambles the carrier. The verifier now undoes both (Hungarian re-alignment,
  a linear program for the scales) and still demands an exact 256-bit match. The search only
  runs when a counting bound proves it cannot fit a codeword the model never carried
  (2^-239 for rs32); 724 null models in `experiments/phase6b_false_accept.py` gave 0 false
  accepts.
- Overwriting with a second watermark on the same layer still destroys the exact payload.
  The verifier then reports DAMAGED: the code values still agree with our signed codeword
  far beyond chance (below 2^-64 for an unmarked model, counted without any search). This
  is evidence of origin, not a proof of the exact payload.
- Not yet tested: adding dummy neurons (it changes the parameter count, so the signed
  manifest check rejects the model, which still counts as a removal), overwriting a
  different layer, much longer fine-tuning, and attacks on the rs16 models.

## Operational notes
- The verifier needs the secret watermark key. Any auditor who receives it learns where
  the mark lives and could target it, so it is shared only with trusted auditors.
- During development the team shared the keys (including the ML-DSA secret key) over a
  chat app and chose to keep them. A real release would need a fresh key pair.
- `created_utc` in the manifest is chosen by the signer. Nothing proves who signed first,
  so a priority dispute (two developers each with a valid signature) needs a trusted
  timestamp (RFC 3161) or a transparency log. Not implemented.

## Assumptions
- The developer's private key is kept secret.
- The watermark key (seed) is shared only with trusted auditors.
- The post-quantum security of ML-DSA holds.
# Results log

## Phase 1: Baseline (no watermark)
- Model: SmallCNN, width 32, ~160k parameters
- Hardware: Colab GPU (TESLA T4 GPU name)
- Training: 30 epochs, SGD (lr 0.05, momentum 0.9, nesterov), cosine schedule,
  weight decay 5e-4, batch 128, crop+flip augmentation
- Seeds: 0, 1, 2
- Test accuracy (final epoch): 0.8507 +/- 0.0119
- Seconds per run: 589

## Phase 2: Crypto and provenance (recorded 2026-10-26 from commit d8bc8b9)
- CIFAR-10 train Merkle root: 76c4deeb4da9723777c84f81fb7bf905d99b9633af7dab930cb913817be074ca (50,000 leaves)
- Developer id: Post-Quantum-Testing   key id: bae58d20d2964be6ef068a9ff17772af   ML-DSA-65 signature: 3309 bytes
- Payload (256 bit): a81a2b6f42d6921ced51312865ca35492b2b763b186e6f1ae88323bd57e4ddcb
- pytest phase2: 5 passed; verify_release --check-dataset: VERIFIED; tamper demo: all 6 tampered cases REJECTED, PASSED
- Re-checked 2026-10-26 on a second machine (Windows, Python 3.14.7, liboqs 0.16.0 built natively):
  same Merkle root, signature valid, VERIFIED

## Phase 3: Embedding v0, 32-bit prefix, no ECC (recorded 2026-10-26)
- Source: commit messages ffec212 and a49df67 (Colab T4 training, Fedora local checks)
- Layer features.6.0.weight, mode mean (average over the 128 output filters), carrier dim 576,
  n_bits 32 (first 32 bits of the payload), projection matrix from keys/watermark_key.bin
- Training: same recipe as the baseline, Total_Loss = CE + lam * BCE(sigmoid(X·w), bits), 30 epochs
- Final test accuracy and paired difference (watermarked seed N minus baseline seed N):

| lam | seed 0 | seed 1 | seed 2 | paired diffs (points) | mean ± std (points) | bit errors |
|---|---|---|---|---|---|---|
| 0.1 | 0.8600 | 0.8487 | 0.8630 | -0.12 / -0.45 / +2.52 | +0.65 ± 1.63 | 0 / 0 / 0 |
| 1 | 0.8555 | 0.8359 | 0.8579 | -0.57 / -1.73 / +2.01 | -0.10 ± 1.91 | 0 / 0 / 0 |
| 5 | 0.8489 | 0.8385 | 0.8549 | -1.23 / -1.47 / +1.71 | -0.33 ± 1.77 | 0 / 0 / 0 |

- Extraction check, lam 1 (experiments.phase3_check_extraction, real key):
  - right key: 0/32 bit errors on all 3 seeds; min|logit| 3.60 / 3.63 / 3.64; mean|logit| 4.04 / 4.04 / 3.98
  - 50 random wrong keys: mean BER 0.499 / 0.514 / 0.479 (range 0.188 to 0.812), i.e. random
  - unmarked baseline, right key: 13/32, 15/32, 17/32 bit errors (BER 0.41 / 0.47 / 0.53), i.e. random
  - chance that random bits match all 32: 2.33e-10
- Done-when (0 bit errors, accuracy cost within about 1 to 2 points): MET for every lam
- Seed 2 gains about 2 points under every lam. The seed 2 baseline (0.8378) is the lowest of the three,
  so this is most likely baseline seed noise, not a benefit of the watermark.
- Independent re-check 2026-10-26 (Windows, CPU): all 9 watermarked and 3 baseline checkpoints re-evaluated
  on the CIFAR-10 test set; every accuracy matches the table to 4 decimals. phase3_check_extraction with the
  real key on lam1 seed 0: 0/32 errors, min|logit| 3.60, baseline 13/32.
- Repo fix found during the audit: GitHub commit 6387c5f had runs/baseline/seed0/model.pt replaced by the
  1-epoch smoke model (test accuracy 0.2830). The local merge 0f77055 restores the real seed 0 baseline
  (0.8612). Not pushed yet.

## Phase 4: ECC and the full 256-bit payload (recorded 2026-10-26)
- Code: `embedding/ecc.py` (none / rep<r> / rs<p>, soft decoding; Reed-Solomon erasures capped at
  parity/2 after pure noise "decoded" 1000/1000 times without the cap, 0/1000 with it).
- Training: Colab T4, same recipe as the baseline, Total_Loss = CE + lam * BCE(X·w, codeword), 30 epochs,
  carrier = mean over output filters (576 numbers). About 17 s per epoch, 8.5 min per run.
- Stage A (seed 0, rs32 = 512 embedded bits):

| layer | lam | acc | paired diff (points) | raw errors | decoded errors | min margin |
|---|---|---|---|---|---|---|
| features.6.0 | 1 | 0.8467 | −1.45 | 1/512 | 0 | 0.02 |
| features.6.0 | 5 | 0.8319 | −2.93 | 0 | 0 | 1.21 |
| features.6.0 | 20 | 0.8308 | −3.04 | 0 | 0 | 2.25 |
| features.4.0 | 1 | 0.8392 | −2.20 | 1/512 | 0 | 0.00 |
| features.4.0 | 5 | 0.8199 | −4.13 | 0 | 0 | 1.15 |
| features.4.0 | 20 | 0.7947 | −6.65 | 0 | 0 | 2.31 |

- Chosen: features.6.0, lam 20 (0 raw errors; same accuracy as lam 5 within one-seed noise, almost twice
  the margin). Rule: gaps under 0.5 points count as a tie, then the larger margin wins.
- Stage B and code comparison (features.6.0, lam 20; paired by seed against the baseline):

| code | embedded bits | seed 0 | seed 1 | seed 2 | mean ± std (points) | mean acc | raw/decoded errors | min margin |
|---|---|---|---|---|---|---|---|---|
| rs32 | 512 | −3.04 | −4.99 | −1.26 | −3.10 ± 1.87 | 0.8198 | 0 / 0 all seeds | 2.24 |
| rs16 | 384 | −4.03 | −4.57 | +0.17 | −2.81 ± 2.59 | 0.8226 | 0 / 0 all seeds | 2.70 |
| rep2 | 512 | −3.61 | −4.80 | — | −4.21 ± 0.84 (2 seeds) | 0.8152 | 0 / 0 all seeds | 1.84 |

- Noise test (P4.3; noise std = level × each weight tensor's std; 20 trials per level; local CPU):

| code | ≤ 5% | 100% (model ≈ chance) | 200% | 300% | 400% | 500% |
|---|---|---|---|---|---|---|
| rs32 (3 seeds) | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 3-4/20 |
| rs16 (3 seeds) | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 13-14/20 |
| rep2 (2 seeds) | 20/20 | 20/20 | 20/20 | 14-15/20 | 4/20 | 0/20 |
| unmarked baseline | 0/5 decoded, 256/512 raw bits wrong | | | | | |

- Accuracy under noise: ≤ 0.8 points lost at 5%; 10 to 20% accuracy (chance 10%) at 100%.
- Done-when (full payload survives light noise with 0 errors after decoding): **MET** for every model.
- Known limitation: accuracy cost about −3 points (target 1 to 2). Not explained by carrier capacity
  (rs16 with 384 bits costs the same as rs32 with 512); most likely the BCE loss keeps pushing until weight
  decay balances it. Proposed fix: margin-capped (hinge) loss; waits for the team/faculty decision.
- Caveat: baseline seed 2 (0.8378) looks like a weak run (watermarked seed-2 models are usually the best of
  their group), so the means probably understate the cost slightly. More baseline seeds (Phase 7) would settle it.
- Caveat: the Phase 1 baselines and the Phase 4 models were both trained on a Colab T4, but in different
  sessions and with different data-loader shuffling, so the pairing shares the initial weights, not the data order.
- Margin depends on the key/payload: same recipe, Mallory's key gave 2.02, our key with Mallory's payload 1.59,
  our key and payload 2.24.

## Phase 5: Verifier tool (recorded 2026-10-26)
- `verify/verify_model.py`: signature → model (architecture, signed width, parameter count) → watermark read
  (ECC) → decoded payload == SHA-256(signed manifest). Exit 0 = VERIFIED, 1 = REJECTED.
- Mallory (second developer): own ML-DSA-65 key (key id 89add2f8…), own watermark key (fingerprint
  59022180cd831ada), own signed manifest; Phase 4 model trained on Colab: acc 0.8274, margin 2.02.
- Negative-case suite (`experiments/phase5_negative_cases.py`), 8 cases per seed:

| models | cases | result |
|---|---|---|
| Phase 3, lam 1 (ecc none, 32 bits), seeds 0-2, stand-in Mallory | 24 | all correct, right reason, PASSED |
| Phase 4 rs32, seeds 0-2, real Mallory | 24 | all correct, right reason, PASSED |
| Phase 4 rs16, seeds 0-2, real Mallory | 24 | all correct, right reason, PASSED |
| insider: our watermark key + Mallory's payload | 1 | REJECTED (116/256 bits differ) |

Accuracy cost of watermark
0 {'final_test_acc': 0.8308, 'bit_errors': 0, 'ber': 0.0, 'decoded_errors': 0}
1 {'final_test_acc': 0.8033, 'bit_errors': 0, 'ber': 0.0, 'decoded_errors': 0}
2 {'final_test_acc': 0.8252, 'bit_errors': 0, 'ber': 0.0, 'decoded_errors': 0}

- Done-when (wrong key, tampered manifest, unmarked model and someone else's model rejected; own model
  passes): **MET**.
- tests: phases 2-5, 26 passed (Windows, liboqs 0.16.0 built natively).

## Fix H1: verifier must check the whole signed payload (recorded 2026-10-27)
- Flaw (found in review after Phase 6): `n_bits` came from the unsigned `final.json` / command line and
  only `1 <= n_bits <= 256` was enforced. ecc, layer, mode and the watermark key are unsigned too, so a forger
  could retry with few bits until an unmarked or someone else's model passed (50% per try at 1 bit, 1/256 at
  8 bits; at the old default of 32 bits, a search over about 4 billion watermark keys).
- Fix (branch `fix-short-payload`, from `phase6`): `n_bits` must equal the signed `payload_bits`; default
  taken from the manifest instead of 32; `--allow-short` accepts fewer bits for legacy models only and prints
  a WARNING line before the verdict. Commands and code: `docs/phase_commands.md`, "Phase 4-5 fix".
- Not affected: all Phase 4 results and all 234 Phase 6 verifications (every one used `n_bits 256`).
- Changed: the Phase 3 rows above now need `--n-bits 32 --allow-short` to reproduce.

| check | result |
|---|---|
| Phase 4 rs32 / rs16 model, no flags | VERIFIED (256 bits) |
| Phase 3 model, no flags / `--n-bits 32` without `--allow-short` | REJECTED (as intended) |
| Phase 3 model, `--n-bits 32 --allow-short` | VERIFIED + WARNING (32 of 256 bits) |
| unmarked model, forger asks `--n-bits 1` | REJECTED at the new check |
| negative cases, Phase 4 rs32 and rs16, seeds 0-2 (now the default models) | PASSED, all rows right reason |
| negative cases, Phase 3 with `--n-bits 32 --allow-short` | PASSED |
| negative cases, Phase 3 without the flag | FAILED (as intended) |

- tests: `test_phase5.py` 11 passed (3 new: short payload, forger with 1/8/32 bits, default n_bits from
  manifest); phases 2-5, 29 passed (Windows, liboqs 0.16.0).

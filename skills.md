# skills.md: Project handoff file

**Project:** Post-Quantum AI Provenance Watermarking
**File version:** v1 (covers Phase 0 and Phase 1)
**Last updated:** 2026-10-25
**Current status:** Phase 0 DONE, Phase 1 DONE, Phase 2 NOT STARTED

---

## 0. How to use this file

If you (the user) lose track of the project, or start a new AI chat, paste this whole file at the start and say:

> "Read this project handoff file. Continue from the current status. Do not redo finished phases."

If you are the AI reading this: treat this file as the source of truth for what has been built, decided and measured. Section 12 says how to respond to this user. Section 11 lists what is not yet confirmed. Do not assume anything marked UNCONFIRMED.

**Maintenance rule:** from Phase 2 onward, the AI must give an updated version of this file (and requirements.txt) with every phase walkthrough. Bump the version number and add a line to the changelog (Section 14).

---

## 1. The user

- Student developer (engineering college level). Experienced in general programming; **new to cryptography and to ML watermarking**, so explain concepts simply before using them.
- Works locally in **WSL2 Ubuntu** (project at `~/pq-watermark`, Python virtual environment `.venv`) and trains models on **Google Colab (Tesla T4 GPU)**.
- Project is an ideation-to-build project that will be pitched to mentors, so claims must be honest and defensible.

---

## 2. The project in one paragraph

Give an AI model a tamper-proof "birth certificate" hidden inside its weights that stays unforgeable even against quantum computers. A developer signs a manifest (describing the training dataset and model) with **ML-DSA** (NIST FIPS 204, post-quantum digital signature). A short payload derived from that manifest is embedded into the model weights during training via an extra loss term. A buyer/auditor later extracts the payload from the weights and verifies it against the signed manifest and the developer's public key.

**Why:** ordinary signatures (RSA/ECC) could be forged once quantum computers run Shor's algorithm, and a signature file shipped next to a model can simply be stripped. Embedding in the weights plus a post-quantum signature fixes both.

**Actors:** Developer (trains, signs, embeds) / Model (carries watermark) / Auditor (extracts and verifies, white-box access to weights).

**Three pillars:** (1) provenance (signed dataset commitment), (2) deep model watermarking (payload in weights), (3) post-quantum cryptography (ML-DSA).

---

## 3. Original ideation reports and their flaws

The user was given five reports (Study, ML-DSA & NIST, Loss function manipulation, Decryption, overall concept). They proposed: sign the dataset with ML-DSA, then embed the **entire signature** bit by bit by pushing carrier weights positive (bit 1) or negative (bit 0) via `Total_Loss = Classification_Loss + λ * Watermark_Loss`, with the carrier weights chosen by a secret seed. Verification = read signs of carrier weights back into bits, then run ML-DSA verify.

**Flaws identified and fixed in the revised design:**

| # | Flaw in original | Fix adopted in the plan |
|---|---|---|
| 1 | Real ML-DSA signature is thousands of bytes (ML-DSA-65: ~3.3 KB, ~26,000 bits) and one wrong bit fails verification. The reports used a 7-bit toy example. | Do NOT embed the signature. Sign a **manifest**; embed only a short **payload** (hash of the manifest). The signature ships beside the model. |
| 2 | Sign-based single-bit encoding (positive = 1, negative = 0) is fragile under fine-tuning, pruning (weights become 0) and quantization. | Use **projection-based embedding** (Uchida et al.) and **error-correcting codes**, with soft decoding. |
| 3 | Circularity: cannot sign final weights if the weights contain the signature. | Sign the manifest (dataset root, model info, key ID, timestamp), not the weights. |
| 4 | Claim "True means training data wasn't poisoned" is too strong. | Claim only: **the model is bound to a signed dataset commitment by the legitimate developer** (tamper-evident provenance). It does not prove data was clean before signing, nor that this model was trained on that data. |
| 5 | Secret seed makes verification private (conflicts with "anyone can audit with the public key"). | Document the trade-off. Seed shared only with trusted auditors for the prototype. Treat the seed as a separate watermark key. |
| 6 | No threat model. | Written in `docs/threat_model.md` (remover, forger, poisoner). |
| 7 | Quantum framing was weak ("quantum-enabled poisoning"). | Reframe: signatures made today could be forged later, so long-lived models need post-quantum signatures. |
| 8 | Only white-box verification. | Keep white-box for the prototype. Black-box trigger-set watermark is an optional stretch goal. |

The user proceeded with the roadmap built on these fixes without asking for changes. They have not explicitly confirmed each of the eight individually.

**Novelty positioning:** weight watermarking itself already exists (Uchida 2017, DeepSigns, Adi et al. backdoor watermarks). This project's contribution is the **end-to-end post-quantum provenance pipeline**: Merkle-committed dataset, ML-DSA-signed manifest, robust ECC-protected payload in the weights, verifier tool, and a benchmark against lifecycle attacks.

---

## 4. Revised architecture (target design)

```
Dataset -> Merkle root --+
Model info, developer ID +--> Manifest --> ML-DSA sign --> signed_manifest.json (shipped / registry)
                                 |
                          SHA-256(canonical manifest) -> payload bits (up to 256)
                                 |
                          ECC encode (Phase 4)
                                 |
     Train: CE loss + lambda * BCE(sigmoid(X . w), codeword)  --> watermarked model (Colab)

Audit: model + watermark key + public key + signed manifest
       -> X . w -> soft decode + ECC -> payload
       -> payload == SHA-256(manifest)?  and  ML-DSA verify(manifest, signature, public key)
       -> VERIFIED / REJECTED
```

Key rules:
- Payload = first `payload_bits` (default 256) bits of SHA-256 over the **canonical JSON** of the manifest (sorted keys, separators `(",", ":")`). The manifest does not contain the payload (avoids circularity).
- Projection embedding: secret random matrix `X` (derived from a secret watermark seed) projects a chosen layer's flattened weights; a BCE regularizer pushes `sigmoid(X . w)` toward the payload/codeword bits. Start with a small payload (32 bits), then scale to 128 to 256 bits with ECC.
- The secret ML-DSA key never goes to Colab. Colab only needs `release/payload.hex` (and later, the watermark seed for training).

---

## 5. Environment and tooling

**Local machine (crypto, tests, verifier):**
- WSL2 Ubuntu, project folder `~/pq-watermark`, virtual environment `.venv` (activate: `source .venv/bin/activate`).
- Python 3.10+ (exact version not recorded).
- PyTorch **CPU** build installed locally via `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`.
- Other packages: numpy, scipy, matplotlib, pandas, tqdm (see requirements.txt).
- **liboqs-python** (Open Quantum Safe) installed by cloning the official repo and running `pip install .` inside the venv (it needs git, cmake, ninja, build-essential, libssl-dev, installed with apt). ML-DSA-65 confirmed working by the user (sign then verify returned True, tampered message returned False).
- Git repo initialized. `.gitignore` contains: `.venv/`, `__pycache__/`, `data/`, `keys/`, `*.pt`, `*.pth`, `.ipynb_checkpoints/`.

**Training (Colab):**
- Google Colab with a **Tesla T4 GPU** runtime. Project lives in Google Drive at `My Drive/pq-watermark` (Drive is mounted in the notebook; `/content` is wiped when sessions end).
- CIFAR-10 is stored on Colab local disk via env var `CIFAR_ROOT=/content/data` for speed; code defaults to `data` locally.
- Torch, torchvision, numpy, pandas, matplotlib and tqdm come preinstalled on Colab. Do not reinstall torch there.
- Results are brought back to the local repo with a zip export (Section 9, step list).

---

## 6. Repository structure and file status

```
pq-watermark/
  crypto/            __init__.py                       (Phase 2 will fill: merkle.py, dataset.py, signing.py, manifest.py)
  embedding/         __init__.py                       (Phases 3 and 4)
  training/          __init__.py
                     seed.py            DONE  reproducibility helper set_seed()
                     model.py           DONE  SmallCNN (Colab Drive; confirm copied locally)
                     data.py            DONE  CIFAR-10 loaders (reads CIFAR_ROOT)
                     train_baseline.py  DONE  baseline training script
  attacks/           __init__.py                       (Phase 6)
  verify/            __init__.py                       (Phase 2 and 5)
  experiments/       run_baseline_seeds.py  DONE  multi-seed runner
  tests/             test_mldsa.py  DONE (Phase 0)   test_torch.py  DONE (Phase 0)
  docs/              threat_model.md  DONE   results_log.md  (Phase 1 entry; confirm filled)
  keys/              (git-ignored; will hold ML-DSA public_key.bin and secret_key.bin in Phase 2)
  data/              (git-ignored; CIFAR-10)
  runs/baseline/     seed0/ seed1/ seed2/ summary.json  (created on Colab Drive)
  skills.md          this file
  requirements.txt
```

Always run code from the project root using `python -m package.module` (for example `python -m training.train_baseline`), not `python path/to/file.py`.

---

## 7. Roadmap and status

| Phase | Goal | Status |
|---|---|---|
| 0 | Scope and setup: environment, ML-DSA test, skeleton, threat model | **DONE** |
| 1 | Baseline CNN on CIFAR-10, 3 seeds, saved weights | **DONE** |
| 2 | Crypto and provenance: Merkle tree, ML-DSA keys, signed manifest, payload, verifier, tamper tests | **NOT STARTED** (design below) |
| 3 | Embedding v0: projection-based, no ECC, 32-bit payload, custom loss, train on Colab | not started |
| 4 | Add ECC, scale payload to 128 to 256 bits, retune lambda and layer | not started |
| 5 | Verifier tool (CLI): extract, decode, check payload against manifest, ML-DSA verify; negative cases | not started |
| 6 | Attack suite: fine-tuning, pruning, quantization (8 and 4 bit), noise, overwriting with second watermark | not started |
| 7 | Evaluation and ablations: lambda sweep, payload size vs accuracy, ECC on/off, false-positive rate on unmarked models, second model (ResNet-18), 5 seeds, paired by seed | not started |
| 8 | Write-up, 3-minute demo (tamper live, show REJECTED), mentor Q and A prep | not started |

Cut order if short of time: black-box trigger watermark, second model, hybrid signatures, Merkle per-sample proofs. Never cut the attack suite.

---

## 8. Phase 0: what was done

- Installed WSL2 Ubuntu, base tools (python3, venv, pip, git, cmake, ninja, build-essential, libssl-dev), created `~/pq-watermark` and `.venv`.
- Installed PyTorch CPU and the scientific packages; installed liboqs-python from the official repo.
- `tests/test_mldsa.py`: sign and verify "hello" with ML-DSA-65. Expected and reported: enabled True; public key about 1,952 bytes; signature about 3,309 bytes; correct message True; tampered message False.
- `tests/test_torch.py`: tensor math works; CIFAR-10 downloads (50,000 train images, shape (3, 32, 32)); GPU False locally (fine).
- Created folder skeleton, `training/seed.py`, `.gitignore`, first git commit.
- Wrote `docs/threat_model.md` (what is protected; attackers: Remover, Forger, Poisoner; claims; non-claims; assumptions).
- User reported everything matched expected output.

**Two meanings of "seed" (do not confuse):**
1. Reproducibility seed (`set_seed`): not secret.
2. Secret watermark seed (picks carrier or projection): secret; lives in `keys/`, never committed.

---

## 9. Phase 1: what was done

**Goal:** a control-group model with no watermark, measured over 3 seeds.

**Model** (`training/model.py`, class `SmallCNN(width=32, num_classes=10)`):
- Conv block = Conv2d(3x3, padding 1, bias False) + BatchNorm2d + ReLU.
- `features` = [block(3,w), block(w,w), MaxPool, block(w,2w), block(2w,2w), MaxPool, block(2w,4w), MaxPool]; `classifier` = Flatten, Dropout(0.3), Linear(4w*4*4, 10).
- width 32 gives **160,234 parameters** (computed by hand; the training log prints the same count at the start of each run).
- Likely carrier layers for the watermark: `features.6.0.weight` (shape 128x64x3x3 = 73,728 weights) and `features.4.0.weight` (64x64x3x3 = 36,864 weights).

**Data** (`training/data.py`): CIFAR-10, train 50,000 / test 10,000. Train augmentation: RandomCrop(32, padding 4) and horizontal flip. Normalize mean (0.4914, 0.4822, 0.4465), std (0.2470, 0.2435, 0.2616). Batch 128 (test batch 256), 2 workers.

**Training** (`training/train_baseline.py`): CrossEntropyLoss; SGD lr 0.05, momentum 0.9, Nesterov, weight decay 5e-4; cosine annealing over 30 epochs. Reported metric is **final-epoch** test accuracy (never best-epoch). Outputs per seed: `runs/baseline/seed{N}/model.pt`, `metrics.csv`, `final.json`.

**Runner** (`experiments/run_baseline_seeds.py`): runs seeds 0, 1, 2 via `python -m training.train_baseline`, skips finished seeds, writes `runs/baseline/summary.json`.

**Colab workflow used:** notebook with cells to check GPU; mount Drive; `%cd /content/drive/MyDrive/pq-watermark`; `%%writefile` cells for each code file; smoke test; then
`!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_baseline_seeds --seeds 0 1 2 --epochs 30`.

**RESULTS (measured):**

| Seed | Final test accuracy |
|---|---|
| 0 | 0.8612 |
| 1 | 0.8532 |
| 2 | 0.8378 |
| **Mean +/- std** | **0.8507 +/- 0.0119** |

- Hardware: Colab Tesla T4. Reported time: 589 (interpreted as seconds per run, about 10 minutes).
- Interpretation: valid baseline, on the low side of the expected 85 to 89% for a 160K-parameter model. The seed spread (about 2.3 points between best and worst) is real seed variance, not one broken run. Consequence: comparisons in later phases must be **paired by seed** (watermarked seed N vs baseline seed N) and the final evaluation should use **5 seeds**. A watermark costing under about 1 point cannot be distinguished from seed noise on 3 unpaired seeds.

**Bringing Colab results back to the local repo (documented method):** in Colab, `shutil.make_archive(...)` the Drive folder to a zip and `files.download(...)`; then in WSL `unzip -o <zip> -d ~/pq-watermark` and commit `training experiments docs runs`. `.pt` files stay git-ignored (originals stay in Drive).

---

## 10. Phase 2 plan (designed, NOT built yet)

All Phase 2 work runs locally (CPU). Planned files:

- `crypto/merkle.py`: leaf hash = SHA-256(`0x00` | index u64 | label u16 | image bytes); node hash = SHA-256(`0x01` | left | right); odd node promoted unchanged; `build_levels`, `merkle_root`, `merkle_proof`, `verify_proof`.
- `crypto/dataset.py`: Merkle root over the 50,000 CIFAR-10 **train** samples.
- `crypto/signing.py`: ML-DSA-65 wrappers via `oqs` (generate_keys, sign, verify returning False on any exception, key_id = first 32 hex chars of SHA-256(public key)).
- `crypto/manifest.py`: manifest fields (format_version, developer_id, key_id, signature_algorithm, created_utc, dataset{name, split, num_samples, merkle_root_sha256, leaf_format, node_format}, model{architecture, width, num_params}, watermark{scheme "projection-v1", payload_bits}); canonical JSON bytes; payload bits from SHA-256(canonical manifest); `bits_to_hex`.
- `experiments/phase2_make_release.py`: generates (or loads) keys in `keys/`, builds and signs manifest, writes `release/signed_manifest.json`, `release/payload.hex`, `release/public_key.bin`; refuses to overwrite without `--force`.
- `verify/verify_release.py`: checks key ID, signature, optionally dataset root (`--check-dataset`); prints PASS/FAIL lines and VERIFIED/REJECTED.
- `tests/test_phase2.py`: Merkle proofs (including odd sizes), one changed leaf changes root, signature tamper/wrong-key/tampered-manifest rejected, payload depends on manifest, one CIFAR pixel change changes the root. Run with `python -m pytest tests/test_phase2.py -v` (expect 5 passed).
- Done when: changing one dataset sample or one manifest field makes verification fail.

Notes: ML-DSA signing is typically randomized, so two signatures of the same message differ but both verify. Each re-run of the release script produces a new timestamp and therefore a new payload, so finalize the manifest before Phase 3 training. Back up `keys/secret_key.bin` privately; never commit it.

---
## Phase 2 (date)
- Merkle root: <64 hex>   key id: <32 hex>   developer id: <name>   width: <32|64>
- payload (256 bit): <64 hex>
- pytest phase2: 5 passed | tamper demo: PASSED

## Phase 3 (date)
- layer features.6.0.weight, mode mean, carrier dim 576, n_bits 32 (prefix of payload), lambda <L>
- seeds 0/1/2 final test acc: <a0>/<a1>/<a2>  paired diff vs baseline: <d0>/<d1>/<d2>  mean <m> +/- <s>
- bit errors at final epoch: <0/0/0>   min|logit|: <x/y/z>
- wrong-key BER (50 keys): <min/mean/max>   unmarked-baseline BER: <b>
- notes / problems:

## 11. Open items and UNCONFIRMED facts

- UNCONFIRMED: whether the Phase 1 files (`training/`, `experiments/`, `runs/` metrics) were exported from Colab Drive and committed in the local repo.
- UNCONFIRMED: whether `docs/results_log.md` has the Phase 1 numbers filled in.
- UNCONFIRMED: exact Python and package versions (record with `pip freeze > requirements-lock.txt` locally).
- DECISION PENDING: retrain baseline with `--width 64` (about 30 minutes on T4) into `runs/baseline_w64` for a higher and steadier baseline. Must be decided **before Phase 3** because the architecture must stay fixed once the watermark is embedded. Default if no decision: keep width 32.
- Phase 2 has not been started.

---

## 12. How the AI should respond to this user

- Give **complete, step-by-step walkthroughs** per phase: concepts first (simply), then exact file contents, exact commands, expected output, a checklist, and troubleshooting.
- For **new files**, give full contents. For **changes to existing files**, give exact find/replace blocks (the user prefers manual edits over the AI applying changes directly).
- State where each command runs (local WSL vs Colab). Colab code goes in notebook cells; local code runs from `~/pq-watermark` with the venv active.
- Give an updated `skills.md` and `requirements.txt` with every phase from Phase 2 onward.
- Be honest about limits: report negative results, never claim the system proves training data was clean, and flag anything unconfirmed.
- Do not ask many questions at once; at most one clarifying question per response.

---

## 13. Quick reference

**Local (WSL):**
```bash
cd ~/pq-watermark
source .venv/bin/activate
python -m pytest tests/test_phase2.py -v      # after Phase 2 is built
```

**Colab (notebook cells):**
```python
from google.colab import drive
drive.mount('/content/drive')
%cd /content/drive/MyDrive/pq-watermark
```
```bash
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_baseline_seeds --seeds 0 1 2 --epochs 30
```

**Glossary:** hash = fixed-size fingerprint; Merkle root = single hash committing to a whole dataset; manifest = signed JSON record of dataset, model, key and timestamp; payload = bits derived from the manifest and hidden in the weights; carrier weights = the weights holding the watermark; lambda = weight of the watermark loss versus accuracy; BER = bit error rate after extraction; ECC = error-correcting code; white-box = auditor has the weights.

---

## 14. Changelog

- v1 (2026-10-25): Initial handoff file. Covers ideation review and fixes, revised architecture, Phase 0 and Phase 1 results (baseline 0.8507 +/- 0.0119 over 3 seeds on Colab T4), Phase 2 design.

# skills.md: Project handoff file

**Project:** Post-Quantum AI Provenance Watermarking
**File version:** v2 (covers Phases 0 to 5)
**Last updated:** 2026-10-26
**Current status:** Phases 0, 1, 2, 3, 4, 5 DONE (Phase 4 with a known accuracy limitation, see Section 10c). Phase 6 NOT STARTED.

---

## 0. How to use this file

If you (the user) lose track of the project, or start a new AI chat, paste this whole file at the start and say:

> "Read this project handoff file. Continue from the current status. Do not redo finished phases."

If you are the AI reading this: treat this file as the source of truth for what has been built, decided and measured. Section 12 says how to respond to this user. Section 11 lists open items and what is not yet confirmed. Do not assume anything marked UNCONFIRMED. Every command and every piece of code used from Phase 4 on is in `docs/phase_commands.md`; all measured numbers are in `docs/results_log.md`.

**Maintenance rule:** with every phase, the AI must give an updated version of this file (and requirements.txt). Bump the version number and add a line to the changelog (Section 14).

---

## 1. The team and machines

- Student developers (engineering college level). Experienced in general programming; **new to cryptography and to ML watermarking**, so explain concepts simply before using them.
- Several people and machines have worked on the repo (git authors): Phases 0 and 1 by PKgamerzop (WSL2 Ubuntu); Phases 2 and 3 by shield44 (Fedora, `~/Documents/projects/post-quantum-ai`, venv `venv/`); Phase 4 and 5 work on 2026-10-26 by Krishnadasa Raja on **Windows 11** (`C:\Users\JEEVAN SHETTY\post-quantum-cryptography`, venv `venv/`, native liboqs build).
- Training runs on **Google Colab (Tesla T4 GPU)**. Note: the Colab Drive folder of one account does not automatically have code pushed from another; see Section 5.
- The project will be pitched to mentors and faculty, so claims must be honest and defensible.

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
| 5 | Secret seed makes verification private (conflicts with "anyone can audit with the public key"). | Document the trade-off. Watermark key shared only with trusted auditors for the prototype. |
| 6 | No threat model. | Written in `docs/threat_model.md` (remover, forger, poisoner). |
| 7 | Quantum framing was weak ("quantum-enabled poisoning"). | Reframe: signatures made today could be forged later, so long-lived models need post-quantum signatures. |
| 8 | Only white-box verification. | Keep white-box for the prototype. Black-box trigger-set watermark is an optional stretch goal. |

**Novelty positioning:** weight watermarking itself already exists (Uchida 2017, DeepSigns, Adi et al. backdoor watermarks). This project's contribution is the **end-to-end post-quantum provenance pipeline**: Merkle-committed dataset, ML-DSA-signed manifest, robust ECC-protected payload in the weights, verifier tool, and a benchmark against lifecycle attacks.

---

## 4. Architecture (as built)

```
Dataset -> Merkle root --+
Model info, developer ID +--> Manifest --> ML-DSA-65 sign --> release/signed_manifest.json
                                 |
                          SHA-256(canonical manifest) -> payload (256 bits, release/payload.hex)
                                 |
                          ECC encode (rs32 -> 512 bits, rs16 -> 384, rep2 -> 512; embedding/ecc.py)
                                 |
     Train: CE + lambda * BCE(X . v, codeword)   v = mean over output filters of features.6.0.weight (576 numbers)
                                                  X = secret +/-1 matrix from keys/watermark_key.bin (SHAKE-256)

Audit (verify/verify_model.py): signature -> model (architecture, signed width, parameter count)
       -> X . v -> soft ECC decode -> decoded payload == SHA-256(signed manifest)?  -> VERIFIED / REJECTED
```

Key rules:
- Payload = first 256 bits of SHA-256 over the **canonical JSON** of the manifest (sorted keys, separators `(",", ":")`). The manifest does not contain the payload (avoids circularity).
- Watermark settings (ecc, n_bits, layer, mode) are NOT in the manifest (adding them would change the payload of every trained model); they come from the `final.json` next to the model. Signing them is a manifest-v2 idea.
- The ML-DSA secret key never goes to Colab. Colab needs `release/payload.hex` and `keys/watermark_key.bin` (uploaded with `files.upload()`, never inside a zip).
- Two different "seeds": the reproducibility seed (`set_seed`, not secret) and the secret watermark key (`keys/watermark_key.bin`, 32 random bytes; fingerprint 81b57c4b28884f01 is safe to share, the key is not).

---

## 5. Environment and tooling

**Fedora / WSL (Linux):** venv, PyTorch CPU (`pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`), `pip install -r requirements.txt`, liboqs-python built from the official repo (`pip install .`; needs git, cmake, ninja, build tools, libssl-dev).

**Windows 11 (since 2026-10-26):** liboqs 0.16.0 built natively with Visual Studio 2026 Build Tools (MSVC 14.51, bundled CMake/Ninja) into `%USERPROFILE%\_oqs`; project venv `venv\` with torch 2.14.1+cpu, reedsolo 1.7.0, liboqs-python 0.16.0.1, Python 3.14.7. Full steps: `docs/phase_commands.md`, "Setup: liboqs on native Windows". Clone liboqs into a SHORT path (Windows path-length limit). CIFAR-10 for local checks is in `data/` (git-ignored).

**Colab (training):** T4 GPU runtime; project in Drive `My Drive/pq-watermark`; `CIFAR_ROOT=/content/data` (local disk, wiped on reset; a copy is kept in `My Drive/pq-watermark/cifar_cache/`). Install `reedsolo` after every runtime reset. About 17 s per epoch, 8.5 min per 30-epoch run; the first CIFAR download can take about 30 min. Free Colab: idle timeout about 90 min, daily GPU quota unknown.

**Moving code to Colab:** uncommitted code is zipped without keys (`pq_watermark_colab_code.zip`) and unzipped in the Drive folder. Results come back as a zip (`phase4_export.zip`) that is checked (paths, key fingerprints, payloads) before extracting.

`.gitignore` contains: `venv/`, `__pycache__/`, `data/`, `keys/`, `mallory/keys/`, `.ipynb_checkpoints/`, `.env*`. Note `.venv/` is NOT listed and `.pt` files are no longer ignored (model files are committed).

---

## 6. Repository structure and file status

```
crypto/        merkle.py dataset.py signing.py manifest.py                    Phase 2
embedding/     keys.py projection.py extract.py                               Phase 3
               ecc.py                                                         Phase 4
training/      seed.py model.py data.py train_baseline.py                     Phase 1
               train_watermarked.py  (--ecc added in Phase 4)                 Phase 3/4
attacks/       noise.py  (Gaussian weight noise, reused in Phase 6)           Phase 4
verify/        verify_release.py                                              Phase 2
               verify_model.py                                                Phase 5
experiments/   run_baseline_seeds.py                                          Phase 1
               phase2_make_release.py phase2_tamper_demo.py                   Phase 2
               phase3_make_wm_key.py phase3_check_extraction.py run_phase3.py Phase 3
               run_phase4.py phase4_noise_test.py                             Phase 4
               phase5_make_mallory.py phase5_mallory_standin.py phase5_negative_cases.py   Phase 5
tests/         test_mldsa.py test_torch.py (scripts) test_phase2..5.py (pytest; 26 pass with liboqs)
docs/          threat_model.md results_log.md phase_commands.md
release/       signed_manifest.json payload.hex public_key.bin               Phase 2
runs/          baseline/ (3 seeds)  smoke/  wm_smoke/  wm_v0/ (Phase 3, 9 models)
               wm_v1/ (Phase 4: Stage A 6 models, rs32 x3, rs16 x3, rep2 x2, summary.json, noise_test.json)
mallory/       release/ (public)  runs/ (Phase 4 Mallory model, insider model, stand-in)  keys/ (git-ignored)
keys/          public_key.bin secret_key.bin watermark_key.bin (git-ignored)
```

Always run code from the project root using `python -m package.module`.

---

## 7. Roadmap and status

| Phase | Goal | Status |
|---|---|---|
| 0 | Scope and setup: environment, ML-DSA test, skeleton, threat model | **DONE** |
| 1 | Baseline CNN on CIFAR-10, 3 seeds, saved weights | **DONE** |
| 2 | Crypto and provenance: Merkle tree, ML-DSA keys, signed manifest, payload, verifier, tamper tests | **DONE** |
| 3 | Embedding v0: projection-based, no ECC, 32-bit payload | **DONE** |
| 4 | ECC, full 256-bit payload, retune lambda and layer, light-noise test | **DONE** (accuracy cost about 3 points, above the 1-2 target; decision pending) |
| 5 | Verifier tool (CLI) and negative cases | **DONE** |
| 6 | Attack suite: fine-tuning, pruning, quantization (8 and 4 bit), noise, overwriting with second watermark | not started |
| 7 | Evaluation and ablations: lambda sweep, payload size vs accuracy, ECC on/off, false-positive rate on unmarked models, second model (ResNet-18), 5 seeds, paired by seed | not started |
| 8 | Write-up, 3-minute demo (tamper live, show REJECTED), mentor Q and A prep | not started |

Cut order if short of time: black-box trigger watermark, second model, hybrid signatures, Merkle per-sample proofs. Never cut the attack suite.

---

## 8. Phase 0: what was done

- Environment (WSL2 Ubuntu at the time), PyTorch CPU, liboqs-python; `tests/test_mldsa.py` signs and verifies "hello" with ML-DSA-65 (public key 1,952 bytes, signature 3,309 bytes, correct True, tampered False; re-confirmed on Windows 2026-10-26).
- Folder skeleton, `training/seed.py`, `.gitignore`, `docs/threat_model.md` (attackers: Remover, Forger, Poisoner; non-claims include distillation).

---

## 9. Phase 1: what was done

- `SmallCNN(width=32)`: 160,234 parameters. Conv blocks Conv(3x3, no bias) + BN + ReLU; features = [b(3,w), b(w,w), pool, b(w,2w), b(2w,2w), pool, b(2w,4w), pool]; classifier Dropout(0.3) + Linear.
- CIFAR-10, crop + flip augmentation, SGD lr 0.05 momentum 0.9 Nesterov, wd 5e-4, cosine over 30 epochs, batch 128; final-epoch accuracy only.
- **Results (Colab T4):** seed 0 0.8612, seed 1 0.8532, seed 2 0.8378; **mean 0.8507 ± 0.0119**. Independently re-measured on Windows CPU: identical.
- Seed 2 looks like a weak run (watermarked seed-2 models in Phases 3 and 4 are usually the best of their group), so paired differences on seed 2 look too favourable.
- Repo fix: GitHub commit 6387c5f had the 1-epoch smoke model (accuracy 0.2830) as `runs/baseline/seed0/model.pt`; local merge 0f77055 restores the real seed 0 (0.8612). **Not pushed yet.**

---

## 10. Phases 2 to 5: what was done

### 10a. Phase 2 (crypto and provenance)
- Merkle root over the 50,000 CIFAR-10 train images: `76c4deeb4da9723777c84f81fb7bf905d99b9633af7dab930cb913817be074ca` (reproduced on Windows).
- Developer id `Post-Quantum-Testing`, key id `bae58d20d2964be6ef068a9ff17772af`, ML-DSA-65; payload `a81a2b6f42d6921ced51312865ca35492b2b763b186e6f1ae88323bd57e4ddcb`.
- `verify_release --check-dataset`: VERIFIED. Tamper demo: all 6 tampered cases REJECTED. Done-when met.
- Gap: the manifest has no training config (epochs, lr, lambda) although the roadmap lists it.

### 10b. Phase 3 (32-bit prefix, no ECC)
- features.6.0.weight, mean mode (576 numbers), lambda 0.1 / 1 / 5, 3 seeds each: **0/32 bit errors on all 9 models**; min margin 1.7 to 5.0; wrong-key and unmarked BER about 0.5.
- Paired accuracy difference (points): +0.65 (lambda 0.1), −0.10 (lambda 1), −0.33 (lambda 5). Done-when met.
- The committed Phase 3 code differs from the Notion Phase 3 walkthrough (file names, key as a `.bin` file instead of a seed number, lambda values); the repo is the source of truth.

### 10c. Phase 4 (ECC and full payload)
- `embedding/ecc.py`: `none`, `rep<r>`, `rs<p>` with soft decoding; RS erasures capped at parity/2 (without the cap, pure noise "decoded" 1000/1000 times).
- Stage A (seed 0, rs32): features.6.0 beats features.4.0 at every lambda; lambda 1 leaves 1 raw error; chosen **features.6.0, lambda 20** (margin 2.25).
- Stage B (paired accuracy difference, points): **rs32 −3.10 ± 1.87** (3 seeds, margin 2.24), **rs16 −2.81 ± 2.59** (3 seeds, margin 2.71), rep2 −4.21 (2 seeds, margin 1.84). 0 raw and 0 decoded errors everywhere.
- Noise test: every model decodes 20/20 at ≤ 5% noise (**done-when met**) and up to 400% (rs32, rs16) or 200% (rep2); models are at chance accuracy at 100% noise.
- **Known limitation:** about −3 accuracy points (target 1 to 2). Not caused by carrier capacity (rs16 with fewer bits costs the same); most likely the BCE loss keeps pushing until weight decay balances it. Proposed fix: margin-capped (hinge) loss. **Waiting for a team/faculty decision.**
- Both rs32 and rs16 go to Phase 6.

### 10d. Phase 5 (verifier)
- `verify/verify_model.py`: one command, VERIFIED/REJECTED with reasons, exit 0/1.
- Mallory: second developer with own ML-DSA key (key id 89add2f8…), own watermark key (fingerprint 59022180cd831ada), own signed manifest, own Phase 4 model (accuracy 0.8274, margin 2.02, trained on Colab).
- Negative-case suite: 8 cases per seed on Phase 3, Phase 4 rs32 and Phase 4 rs16 models, all correct for the right reason (**done-when met**). Extra insider case (our watermark key, Mallory's payload): REJECTED.
- Incident: the first Colab Mallory model was trained with OUR watermark key (wrong file picked; both are named `watermark_key.bin`). Caught from `final.json`; kept as the insider case; the training cell now asserts the key fingerprint before starting.

---

## 11. Open items and UNCONFIRMED facts

- **Decision pending (team/faculty):** accept about −3 accuracy points, or test the margin-capped loss (about 25 to 40 min of work and GPU time).
- **Not committed / not pushed:** all Phase 4 and 5 code, docs, `runs/wm_v1/`, `mallory/` (minus keys), and the merge 0f77055 that fixes the seed 0 baseline file on GitHub.
- Keys (including `secret_key.bin`) were shared over a chat app; the team decided to keep them. Record this in the threat model.
- The Notion roadmap does not match the repo (file names, key format, lambda values; its "skills v4" was never committed).
- Small issues: `.gitignore` lacks `.venv/`; `test_mldsa.py` is a script, not a pytest test; `phase2_tamper_demo.py` hard-codes `keys/public_key.bin`; the manifest lacks the training config; the carrier layer is the last conv layer, not a middle one as the roadmap says.
- More baseline seeds (3 and 4) would show whether baseline seed 2 is an outlier (planned for Phase 7's 5 seeds).
- UNCONFIRMED: exact package versions on the Fedora and Colab machines (record with `pip freeze`).

---

## 12. How the AI should respond to this user

- Do exactly **one task ID per turn** (for example P4.2) unless the user explicitly asks for more, then stop and wait.
- **Explain all generated code line by line** (what and why), plus improvement ideas, so the team understands it fully.
- Log **every command and all code** of a phase in `docs/phase_commands.md` under its phase heading, with real outputs and an "Ideas for improving" list per step.
- Concepts first (simply), then exact commands, expected output and troubleshooting. Say where each command runs (local Windows / Fedora / Colab).
- Be honest about limits: report negative results and wrong predictions, never claim the system proves training data was clean, flag anything unconfirmed.
- Never put keys in zips, logs or notebooks; upload the watermark key to Colab with `files.upload()` and check its fingerprint.
- At most one clarifying question per response.

---

## 13. Quick reference

**Local (Windows):**
```bash
venv\Scripts\python -m pytest tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py tests/test_phase5.py -q
venv\Scripts\python -m verify.verify_model --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt
venv\Scripts\python -m experiments.phase4_noise_test --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt --data-root data
```

**Colab (notebook cells):**
```python
from google.colab import drive
drive.mount('/content/drive')
%cd /content/drive/MyDrive/pq-watermark
!pip install -q "reedsolo>=1.7"
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_phase4 --eccs rs32 --layers features.6.0.weight --lams 20 --seeds 0 1 2
```

**Glossary:** hash = fixed-size fingerprint; Merkle root = single hash committing to a whole dataset; manifest = signed JSON record of dataset, model, key and timestamp; payload = bits derived from the manifest and hidden in the weights; carrier = the weights holding the watermark; codeword = payload plus ECC check bits; lambda = weight of the watermark loss versus accuracy; margin (min|logit|) = how far the weakest bit is from flipping; BER = bit error rate; ECC = error-correcting code; white-box = auditor has the weights.

---

## 14. Changelog

- v1 (2026-10-25): Initial handoff file. Ideation review and fixes, revised architecture, Phase 0 and Phase 1 results (baseline 0.8507 ± 0.0119), Phase 2 design.
- v2 (2026-10-26): Phases 2 to 5 recorded (Phase 2 and 3 results from commit messages, re-verified on Windows; Phase 4 ECC, Colab training, rs32/rs16/rep2 comparison, noise test, accuracy limitation; Phase 5 verifier, Mallory, negative cases). Windows setup with native liboqs. Team and machine history, open items, working rules (one task per turn, line-by-line explanations, docs/phase_commands.md logging). Removed the unfilled Phase 2/3 result templates.

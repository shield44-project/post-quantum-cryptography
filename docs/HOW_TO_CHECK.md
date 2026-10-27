# How to check the Phase 4 and 5 work (Linux and Windows)

For a team member who wants to reproduce the checks on their own machine. You do not need a GPU and
you do not retrain anything: the trained models are already in the repo (`runs/wm_v1/`, `mallory/runs/`).

Every check prints a clear verdict (`passed`, `VERIFIED`, `DONE-WHEN ... PASSED`); the expected output is
under each command. Full details: `docs/phase_commands.md` (every command used, with code and outputs)
and `docs/results_log.md` (all measured numbers).

| Step | What it checks | Keys needed | Time |
|---|---|---|---|
| 1 | Get the code | none | 1 min |
| 2 | Python environment and ML-DSA library | none | 10 to 40 min, once per machine |
| 3 | Unit tests and the signed release | none | 1 min |
| 4 | Our watermark is in our models | `keys/watermark_key.bin`, `keys/public_key.bin` | 1 min |
| 5 | Payload survives weight noise | same as step 4 (+ CIFAR-10 for accuracy) | 3 min (+ download) |
| 6 | Verifier rejects every negative case | step 4 keys + Mallory's keys | 2 min |

**Rules for every command**
- Run from the **project root** (the folder that contains `crypto/`, `embedding/`, `docs/`).
- Use `python -m package.module`, never `python path/to/file.py`.
- **Linux / WSL** blocks are for bash (Fedora, Ubuntu, WSL). Activate the venv in every new terminal:
  `source venv/bin/activate`, then use `python`.
- **Windows** blocks are for **PowerShell** (the default terminal in VS Code and Windows Terminal). They call
  the venv's Python directly as `venv\Scripts\python`, so no activation is needed.

---

## Step 1: Get the code

**Linux / WSL**
```bash
git clone https://github.com/shield44-project/post-quantum-cryptography.git   # skip if you already have it
cd post-quantum-cryptography
git fetch origin
git checkout phase4-5
git pull
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/shield44-project/post-quantum-cryptography.git   # skip if you already have it
cd post-quantum-cryptography
git fetch origin
git checkout phase4-5
git pull
```

Check: `git log --oneline -1` shows a commit starting with `Phase 4-5`.

---

## Step 2: Python environment and ML-DSA library (once per machine)

Python 3.10 or newer.

### Linux / WSL

System packages, then the venv:

```bash
# Fedora:
sudo dnf install -y git cmake ninja-build gcc gcc-c++ make openssl-devel python3-devel
# Ubuntu / WSL (use this line instead of the Fedora one):
#   sudo apt update && sudo apt install -y git cmake ninja-build build-essential libssl-dev python3-venv python3-dev

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

liboqs-python (ML-DSA), with the venv active:

```bash
cd ~
git clone --depth=1 https://github.com/open-quantum-safe/liboqs-python
cd liboqs-python
pip install .
cd -                       # back to the project folder
python tests/test_mldsa.py
```

The first import may spend a few minutes building the C library.

### Windows (PowerShell)

1. Install **Build Tools for Visual Studio** (free, from visualstudio.microsoft.com, "Tools for Visual
   Studio") with the workload **"Desktop development with C++"**. It brings the C compiler, the Windows SDK,
   CMake and Ninja. Also install **Git for Windows** and **Python 3.10+** (python.org, tick "Add to PATH").

2. Find your Build Tools folder (needed in the next step):

```powershell
& "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" -products * -property installationPath
```

   It prints something like `C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools`
   (`18` = 2026, `17` = 2022).

3. Download liboqs 0.16.0 into a **short** path (a deep folder breaks the checkout because of the Windows
   path-length limit):

```powershell
git -c core.longpaths=true clone --depth 1 --branch 0.16.0 https://github.com/open-quantum-safe/liboqs.git "$env:USERPROFILE\_oqs_build\liboqs"
```

4. Save the following as `build_oqs.bat` in `%USERPROFILE%\_oqs_build\`. If step 2 printed a different
   folder, change the `...\18\BuildTools\...` part of the `call` line to match.

```bat
@echo off
set "PATH=C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "SRC=%USERPROFILE%\_oqs_build\liboqs"
set "BLD=%USERPROFILE%\_oqs_build\build"
where cl >nul || (echo cl.exe not found after vcvars64 & exit /b 1)
cmake -S "%SRC%" -B "%BLD%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DOQS_BUILD_ONLY_LIB=ON -DOQS_USE_OPENSSL=OFF -DCMAKE_INSTALL_PREFIX="%USERPROFILE%\_oqs" || exit /b 1
cmake --build "%BLD%" --parallel || exit /b 1
cmake --install "%BLD%" || exit /b 1
echo BUILD-AND-INSTALL-OK
```

5. Build and install (about 5 minutes; must end with `BUILD-AND-INSTALL-OK`):

```powershell
cmd /c "$env:USERPROFILE\_oqs_build\build_oqs.bat"
```

   This installs `oqs.dll` into `%USERPROFILE%\_oqs`, where liboqs-python looks by default. Afterwards
   `%USERPROFILE%\_oqs_build` can be deleted.

6. The venv and packages, from the project root:

```powershell
python -m venv venv
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
venv\Scripts\python -m pip install -r requirements.txt "liboqs-python==0.16.0.1"
venv\Scripts\python tests\test_mldsa.py
```

### Expected from `test_mldsa.py` (both systems)

```
ML-DSA-65 enabled: True
public key bytes: 1952
signature bytes: 3309
correct message: True
tampered message: False
```

`liboqs-python faulthandler is disabled` may be printed first; it is informational, not an error.

---

## Step 3: Checks that need no keys

**Linux / WSL**
```bash
python -m pytest tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py tests/test_phase5.py -q
python -m verify.verify_release --release-dir release --public-key release/public_key.bin
```

**Windows (PowerShell)**
```powershell
venv\Scripts\python -m pytest tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py tests/test_phase5.py -q
venv\Scripts\python -m verify.verify_release --release-dir release --public-key release/public_key.bin
```

Expected: `29 passed` (if you see `skipped`, liboqs or torch is missing in this venv, see step 2), then

```
PASS  load release files
PASS  key id matches manifest
PASS  algorithm is ML-DSA-65
PASS  signature valid
PASS  payload.hex matches manifest
VERIFIED
```

This proves the signed manifest in `release/` is intact and signed by key id `bae58d20…`.

---

## Step 4: Checks that need the watermark key

### 4a. Put the keys in place

Get these two files **privately** from the developer (USB stick, direct file transfer; not a group chat,
not email, never git):

| File | Goes to | Secret? |
|---|---|---|
| `watermark_key.bin` (32 bytes) | `keys/watermark_key.bin` | yes, share only with trusted auditors |
| `public_key.bin` (1952 bytes) | `keys/public_key.bin` | no (same file as `release/public_key.bin`) |

`secret_key.bin` (the signing key) is **not** needed for any check. Replace `<download folder>` with
where you saved the files.

**Linux / WSL**
```bash
mkdir -p keys
cp "<download folder>/watermark_key.bin" "<download folder>/public_key.bin" keys/
python -c "from embedding.keys import key_fingerprint, load_key; print(key_fingerprint(load_key('keys/watermark_key.bin')))"
```

**Windows (PowerShell)**
```powershell
New-Item -ItemType Directory -Force keys | Out-Null
Copy-Item "<download folder>\watermark_key.bin", "<download folder>\public_key.bin" keys\
venv\Scripts\python -c "from embedding.keys import key_fingerprint, load_key; print(key_fingerprint(load_key('keys/watermark_key.bin')))"
```

Expected: `81b57c4b28884f01`. Any other value means a wrong key file. `keys/` is git-ignored, so the
keys cannot be committed by accident; still run `git status` before any commit and make sure nothing
from `keys/` is listed.

### 4b. Phase 4 model (256-bit payload with error correction)

**Linux / WSL**
```bash
python -m verify.verify_model --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt
```

**Windows (PowerShell)**
```powershell
venv\Scripts\python -m verify.verify_model --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt
```

Expected: 10 `PASS` lines, the last two being

```
PASS  watermark read (ecc rs32, 512 values)  (min margin 2.25, corrected 0, erasures 0)
PASS  extracted payload == SHA-256(signed manifest)  (256 bits match)
VERIFIED
```

Try the other models by changing the path: `lam20_n256_rs32/seed1`, `seed2`, `lam20_n256_rs16/seed0..2`,
`lam20_n256_rep2/seed0..1`. All should print `VERIFIED`.

The verifier always checks all 256 signed payload bits. Asking for fewer (for example `--n-bits 8`) is
rejected with `FAIL  embedded payload covers the whole signed payload`, because the watermark settings
are not signed and a short check could let an unrelated model pass by chance. Only legacy Phase 3 models
may use fewer bits, with `--allow-short` (see 4c).

An unmarked model must be rejected:

**Linux / WSL**
```bash
python -m verify.verify_model --model runs/baseline/seed0/model.pt --ecc rs32 --n-bits 256
```

**Windows (PowerShell)**
```powershell
venv\Scripts\python -m verify.verify_model --model runs/baseline/seed0/model.pt --ecc rs32 --n-bits 256
```

Expected (the decoder finds no valid watermark; exit code 1 is correct here):

```
FAIL  watermark read (ecc rs32, 512 values)  (decoder failed; min margin 0.00)
REJECTED
```

### 4c. Phase 3 model (32-bit payload, no error correction)

**Linux / WSL**
```bash
python -m experiments.phase3_check_extraction --model runs/wm_v0/lam1_n32/seed0/model.pt --baseline-model runs/baseline/seed0/model.pt
```

**Windows (PowerShell)**
```powershell
venv\Scripts\python -m experiments.phase3_check_extraction --model runs/wm_v0/lam1_n32/seed0/model.pt --baseline-model runs/baseline/seed0/model.pt
```

Expected: `1) watermarked model, right key : 0/32 bit errors`, wrong keys and the unmarked baseline near
BER 0.5, and `DONE-WHEN (0 bit errors on the clean model): PASSED`.

The Phase 3 models carry only 32 of the 256 signed bits, so the verifier rejects them unless told this is a
legacy model:

**Linux / WSL**
```bash
python -m verify.verify_model --model runs/wm_v0/lam1_n32/seed0/model.pt --n-bits 32 --allow-short
```

**Windows (PowerShell)**
```powershell
venv\Scripts\python -m verify.verify_model --model runs/wm_v0/lam1_n32/seed0/model.pt --n-bits 32 --allow-short
```

Expected (the WARNING line is correct: 32 bits is a weaker proof than 256):

```
PASS  watermark read (ecc none, 32 values)  (min margin 3.60, corrected 0, erasures 0)
PASS  extracted payload == SHA-256(signed manifest)  (32 bits match)
WARNING  only 32 of 256 signed payload bits checked (--allow-short), weaker proof
VERIFIED
```

Without `--n-bits 32 --allow-short` the same model is `REJECTED`; that is the intended behaviour.

---

## Step 5: Noise test (Phase 4 "done when")

Optional download for the accuracy column (about 170 MB, once; it can be slow):

**Linux / WSL**
```bash
python -c "import torchvision; torchvision.datasets.CIFAR10('data', train=False, download=True)"
```

**Windows (PowerShell)**
```powershell
venv\Scripts\python -c "import torchvision; torchvision.datasets.CIFAR10('data', train=False, download=True)"
```

Run the test. `--out` writes the result to a scratch file so the committed `noise_test.json` is not
overwritten. Leave out `--data-root data` if you skipped the download (the accuracy column then shows `-`).

**Linux / WSL**
```bash
python -m experiments.phase4_noise_test --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt --data-root data --out /tmp/noise_check.json
```

**Windows (PowerShell)**
```powershell
venv\Scripts\python -m experiments.phase4_noise_test --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt --data-root data --out "$env:TEMP\noise_check.json"
```

Expected: `20/20` in the "decoded OK" column for every level up to 400%, about `4/20` at 500%, and

```
first level with a failed trial: 500%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
```

---

## Step 6: Negative-case suite (Phase 5 "done when")

Also needs the keys of Mallory (the second, fake developer used for testing), from the developer, placed
privately in `mallory/keys/`: `public_key.bin` and `watermark_key.bin` (fingerprint `59022180cd831ada`).
`mallory/keys/` is git-ignored too.

**Linux / WSL**
```bash
mkdir -p mallory/keys
cp "<download folder>/mallory/public_key.bin" "<download folder>/mallory/watermark_key.bin" mallory/keys/
python -m experiments.phase5_negative_cases --seeds 0 1 2 --model-pattern "runs/wm_v1/lam20_n256_rs32/seed{seed}/model.pt" --mallory-model mallory/runs/lam20_n256_rs32/seed3/model.pt
```

**Windows (PowerShell)**
```powershell
New-Item -ItemType Directory -Force mallory\keys | Out-Null
Copy-Item "<download folder>\mallory\public_key.bin", "<download folder>\mallory\watermark_key.bin" mallory\keys\
venv\Scripts\python -m experiments.phase5_negative_cases --seeds 0 1 2 --model-pattern "runs/wm_v1/lam20_n256_rs32/seed{seed}/model.pt" --mallory-model mallory/runs/lam20_n256_rs32/seed3/model.pt
```

Expected: for each of the 3 seeds a table of 8 cases where `expected` equals `got` and `right reason` is
`yes` on every row (own model VERIFIED; wrong public key, wrong watermark key, tampered manifest,
unmarked model, Mallory's model with our files, our model with Mallory's files all REJECTED; Mallory's
model with Mallory's files VERIFIED), then

```
DONE-WHEN (4 negative cases rejected, own model passes): PASSED
```

For the rs16 models, change `lam20_n256_rs32` to `lam20_n256_rs16` in `--model-pattern`. The rs32 models
and Mallory's `lam20_n256_rs32/seed3` are also the defaults, so `--seeds 0 1 2` alone runs the same check.

For the legacy Phase 3 models (32 bits) add `--n-bits 32 --allow-short` and use the 32-bit Mallory stand-in:

```bash
python -m experiments.phase5_negative_cases --seeds 0 1 2 --n-bits 32 --allow-short --model-pattern "runs/wm_v0/lam1_n32/seed{seed}/model.pt" --mallory-model mallory/runs/standin_lam5_n32/seed1/model.pt
```

Expected: a `NOTE: --allow-short is on ...` line first, then the same all-`yes` tables and `PASSED`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'oqs'` | Linux: venv not active or liboqs-python not installed in it. Windows: use `venv\Scripts\python`, and check step 2 ended with `BUILD-AND-INSTALL-OK` |
| `ModuleNotFoundError: No module named 'embedding'` (or `crypto`, `training`) | run from the project root with `python -m ...` |
| `ModuleNotFoundError: No module named 'reedsolo'` | install the requirements again (step 2) |
| `No such file or directory: 'keys/watermark_key.bin'` | step 4a |
| `FAIL  embedded payload covers the whole signed payload` | the model or `--n-bits` asks for fewer than 256 bits. Legacy Phase 3 model: add `--n-bits 32 --allow-short` (4c). Phase 4 model: its `final.json` is missing or edited |
| Fingerprint is not `81b57c4b28884f01` | wrong key file; ask the developer again |
| Tests show `skipped` | liboqs or torch missing in this venv |
| `Dataset not found or corrupted` in step 5 | run the CIFAR-10 download command, or leave out `--data-root` |
| Windows: `vswhere.exe is not recognized` or `cl.exe not found` | Build Tools or its C++ workload missing; or the `...\18\BuildTools\...` path in `build_oqs.bat` does not match step 2 |
| Windows: liboqs clone shows thousands of deleted files | path too long; clone into `%USERPROFILE%\_oqs_build` exactly as in step 2 |
| Windows PowerShell: `running scripts is disabled` | not needed: the commands call `venv\Scripts\python` directly, no `Activate.ps1` |
| `git push` fails with `HTTP 408` or `curl 55` (Windows) | `git -c http.version=HTTP/1.1 push` |

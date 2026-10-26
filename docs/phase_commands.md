# Phase commands and code

Every command and every piece of code used in a phase, in the order it was run.
"Local" means the project root on the developer machine with the venv active;
"Colab" means a notebook cell with the project folder in Drive as working directory.

To re-check the finished work on another machine (Linux or Windows), follow `docs/HOW_TO_CHECK.md`.

---

## Setup: liboqs on native Windows (done 2026-10-26)

For team members on Windows without WSL. Needs Visual Studio Build Tools with the
"Desktop development with C++" workload (MSVC, Windows SDK; it bundles CMake and Ninja) and git.
liboqs-python 0.16.0.1 needs liboqs 0.16.0. It looks for the library in `%USERPROFILE%\_oqs` by default.

1. Clone into a SHORT path (a deep folder breaks the checkout: Windows path-length limit):

```bash
git -c core.longpaths=true clone --depth 1 --branch 0.16.0 https://github.com/open-quantum-safe/liboqs.git "%USERPROFILE%\_oqs_build\liboqs"
```

2. Build and install with this `build_oqs.bat` (run it with `cmd /c build_oqs.bat`, about 5 minutes):

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

`18\BuildTools` is Visual Studio 2026 Build Tools; change the path for another version
(`vswhere -products * -property installationPath` prints it). Afterwards `%USERPROFILE%\_oqs_build`
can be deleted; `%USERPROFILE%\_oqs\bin\oqs.dll` is what Python loads.

3. Project venv (`venv/` is git-ignored), from the project root:

```bash
python -m venv venv
venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
venv\Scripts\python -m pip install -r requirements.txt "liboqs-python==0.16.0.1"
```

4. Check:

```bash
venv\Scripts\python tests\test_mldsa.py
venv\Scripts\python -m pytest tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py -q
venv\Scripts\python -m verify.verify_release --release-dir release --public-key release/public_key.bin --check-dataset
```

Output on this machine (Windows 11, Python 3.14.7, MSVC 14.51, torch 2.14.1+cpu):

```
ML-DSA-65 enabled: True
public key bytes: 1952
signature bytes: 3309
correct message: True
tampered message: False

17 passed

PASS  load release files
PASS  key id matches manifest
PASS  algorithm is ML-DSA-65
PASS  signature valid
PASS  payload.hex matches manifest
PASS  dataset Merkle root matches manifest
VERIFIED
```

`liboqs-python faulthandler is disabled` is printed on import; it is informational, not an error.

---

## Phase 4: Error correction and scaling to the full payload

Goal: protect the 256-bit payload with an error-correcting code (ECC), decode from
soft values (the raw scores X·w), scale the embedded payload from 32 to 256 bits.
Done when: the full payload survives light noise on the weights with zero errors after decoding.

### P4.1: ECC module and tests (local)

**What it adds**

| File | Purpose |
|---|---|
| `embedding/ecc.py` | `get_code(name)` returns an encoder/decoder: `none`, `rep<r>` (repetition), `rs<p>` (Reed-Solomon with p parity bytes) |
| `tests/test_phase4.py` | 6 tests: round trip, soft beats hard (repetition and RS), RS limit, noise never "decodes", bad parameters |
| `requirements.txt` | adds `reedsolo>=1.7` |

**Codes and sizes for the 256-bit payload**

| Code | Codeword bits | Repairs | Fits the 576-dim mean-mode carrier? |
|---|---|---|---|
| `none` | 256 | nothing | yes |
| `rep2` | 512 | soft vote of 2 copies | yes |
| `rep3` | 768 | majority of 3 copies | no (needs `--mode full`) |
| `rs32` | 512 (64 bytes) | e wrong + f erased bytes while 2e + f ≤ 32, erasing at most 16 | yes |

**Commands (local)**

```bash
pip install "reedsolo>=1.7"                      # or: pip install -r requirements.txt
python -m pytest tests/test_phase4.py -v         # expect 6 passed
python -m pytest tests/test_phase2.py tests/test_phase3.py -q   # earlier phases still pass
```

Extra check (local): how the RS decoder behaves on pure noise, i.e. what an unmarked
model or a wrong watermark key produces.

```bash
python - <<'PY'
import time, numpy as np
from embedding.ecc import get_code
from embedding.keys import load_payload_bits
p = load_payload_bits("release/payload.hex", 256)
code = get_code("rs32"); rng = np.random.default_rng(9)
t = time.time(); oks = hits = 0
for _ in range(1000):
    r = code.decode(rng.normal(size=512)); oks += r["ok"]; hits += r["bits"] == p
print("random logits, 1000 trials: decoder said ok %d times, matched real payload %d times, %.1f ms/decode" % (oks, hits, (time.time()-t)))
PY
```

**Output (2026-10-26, Windows, Python 3.14.7, reedsolo 1.7.0)**

```
tests/test_phase4.py::test_roundtrip_all_codes PASSED
tests/test_phase4.py::test_repetition_soft_beats_hard PASSED
tests/test_phase4.py::test_rs_corrects_up_to_limit PASSED
tests/test_phase4.py::test_rs_soft_erasures_beat_hard PASSED
tests/test_phase4.py::test_noise_and_garbage_never_crash PASSED
tests/test_phase4.py::test_bad_parameters_and_capacity PASSED
6 passed
(phase 2 + 3: 9 passed, 1 skipped; the skip is the liboqs test, liboqs not installed on that machine)

random logits, 1000 trials: decoder said ok 0 times, matched real payload 0 times, 5.4 ms/decode
```

**Problem found and fixed during P4.1:** the first version let soft decoding erase up to
all 32 parity bytes. With every parity byte erased there is no redundancy left, so the
decoder "succeeded" on 1000 of 1000 pure-noise inputs (it never produced the real payload,
so verification would still reject, but `ok` meant nothing). Erasures are now capped at
parity/2 = 16, which leaves 16 parity bytes to check the result: 0 of 1000 noise inputs
decode. Rule for Phase 5: the verifier must compare the decoded payload with the manifest,
never trust `ok` alone.

**Code: `embedding/ecc.py`**

```python
"""Error-correcting codes for the watermark payload (Phase 4).

The payload (256 bits) is ENCODED into a longer codeword before embedding. At
extraction time the raw scores (logits = X @ v) are DECODED back to the payload.

    "none"     codeword = payload                         (Phase 3 behaviour)
    "rep{r}"   every payload bit written r times          rep2: 256 -> 512 bits
    "rs{p}"    Reed-Solomon over bytes, p parity bytes     rs32: 32 -> 64 bytes = 512 bits
               repairs e wrong bytes + f erased bytes as long as 2e + f <= p
               (the decoder erases at most p/2 bytes, see ReedSolomon.decode)

Soft decoding: decoders take the LOGITS, not 0/1 bits. A logit's sign is the bit,
its size is how sure we are. Repetition adds up the logits of the copies;
Reed-Solomon marks the least sure bytes as erasures, which cost half as much to
repair as errors. Bit order is MSB first, same as crypto.manifest.payload_bits.
"""
import numpy as np


def hard_bits(logits):
    """Phase 3 extraction rule: bit 1 if logit > 0, else 0."""
    return (np.asarray(logits, dtype=np.float64) > 0).astype(np.uint8)


def _check_bits(bits, n):
    b = np.asarray(bits, dtype=np.uint8).ravel()
    if b.size != n or b.max(initial=0) > 1:
        raise ValueError("expected %d bits of 0/1, got %d values" % (n, b.size))
    return b


def _check_logits(logits, n):
    z = np.asarray(logits, dtype=np.float64).ravel()
    if z.size != n:
        raise ValueError("expected %d logits, got %d" % (n, z.size))
    return z


def _result(ok, bits=None, corrected=0, erasures=0):
    return {"ok": ok, "bits": bits, "corrected": corrected, "erasures": erasures}


class NoCode:
    def __init__(self, k_bits):
        self.name, self.k_bits, self.n_bits = "none", k_bits, k_bits

    def encode(self, bits):
        return _check_bits(bits, self.k_bits).tolist()

    def decode(self, logits, soft=True):
        return _result(True, hard_bits(_check_logits(logits, self.n_bits)).tolist())


class Repetition:
    """Layout: [payload, payload, ...], r full copies one after another."""

    def __init__(self, k_bits, r):
        if r < 2:
            raise ValueError("repetition factor must be at least 2")
        self.name, self.k_bits, self.r, self.n_bits = "rep%d" % r, k_bits, r, k_bits * r

    def encode(self, bits):
        return np.tile(_check_bits(bits, self.k_bits), self.r).tolist()

    def decode(self, logits, soft=True):
        z = _check_logits(logits, self.n_bits).reshape(self.r, self.k_bits)
        if soft:
            bits = hard_bits(z.sum(axis=0))                        # confident copies outvote shaky ones
        else:
            bits = (2 * hard_bits(z).sum(axis=0) > self.r).astype(np.uint8)   # majority vote, tie -> 0
        corrected = int((hard_bits(z) != bits).sum())              # copies that lost the vote
        return _result(True, bits.tolist(), corrected)


class ReedSolomon:
    """RS over GF(256) via `reedsolo`. Codeword = data bytes followed by parity bytes."""

    def __init__(self, k_bits, parity_bytes):
        if k_bits % 8:
            raise ValueError("Reed-Solomon needs a payload that is a whole number of bytes")
        if k_bits // 8 + parity_bytes > 255:
            raise ValueError("Reed-Solomon over GF(256): data + parity must be at most 255 bytes")
        from reedsolo import RSCodec  # imported here so "none" / "rep" work without reedsolo

        self.rsc = RSCodec(parity_bytes)
        self.name, self.k_bits, self.parity = "rs%d" % parity_bytes, k_bits, parity_bytes
        self.n_bits = (k_bits // 8 + parity_bytes) * 8

    def encode(self, bits):
        data = np.packbits(_check_bits(bits, self.k_bits)).tobytes()
        return np.unpackbits(np.frombuffer(bytes(self.rsc.encode(data)), dtype=np.uint8)).tolist()

    def decode(self, logits, soft=True):
        """Try plain decoding first, then erase the 2, 4, ... least sure bytes until it works.

        At most parity/2 bytes are erased. Erasing all parity bytes would leave no
        redundancy, so ANY input (even pure noise) would "decode" and ok would mean nothing.
        """
        from reedsolo import ReedSolomonError

        z = _check_logits(logits, self.n_bits)
        received = np.packbits(hard_bits(z))
        sureness = np.abs(z).reshape(-1, 8).min(axis=1)            # a byte is as sure as its least sure bit
        order = np.argsort(sureness, kind="stable").tolist()       # least sure first
        for n_erase in range(0, self.parity // 2 + 1, 2) if soft else [0]:
            try:
                _, codeword, _ = self.rsc.decode(bytearray(received.tobytes()),
                                                 erase_pos=order[:n_erase] or None)
            except ReedSolomonError:
                continue
            fixed = np.frombuffer(bytes(codeword), dtype=np.uint8)
            return _result(True, np.unpackbits(fixed[: self.k_bits // 8]).tolist(),
                           int((fixed != received).sum()), n_erase)
        return _result(False)


def get_code(name, k_bits=256):
    if name == "none":
        return NoCode(k_bits)
    if name.startswith("rep"):
        return Repetition(k_bits, int(name[3:]))
    if name.startswith("rs"):
        return ReedSolomon(k_bits, int(name[2:]))
    raise ValueError("unknown code %r (use none, rep<r> or rs<parity bytes>)" % name)
```

**Code: `tests/test_phase4.py`**

```python
"""Run from the project root:  python -m pytest tests/test_phase4.py -v   (expect 6 passed)"""
import numpy as np
import pytest

from embedding.ecc import get_code

pytest.importorskip("reedsolo")

PAYLOAD = [int(b) for b in np.random.default_rng(0).integers(0, 2, 256)]


def _logits(codeword, size=3.0):
    """Perfect extraction: +size for bit 1, -size for bit 0."""
    return np.where(np.asarray(codeword) == 1, size, -size)


def test_roundtrip_all_codes():
    for name, n_bits in [("none", 256), ("rep2", 512), ("rep3", 768), ("rs32", 512)]:
        code = get_code(name)
        cw = code.encode(PAYLOAD)
        assert code.n_bits == len(cw) == n_bits
        r = code.decode(_logits(cw))
        assert r["ok"] and r["bits"] == PAYLOAD and r["corrected"] == 0, name
    assert get_code("rs32").encode(PAYLOAD)[:256] == PAYLOAD                  # data bytes come first


def test_repetition_soft_beats_hard():
    code = get_code("rep3")
    z = _logits(code.encode(PAYLOAD)).reshape(3, 256)
    z[1:, :10] = -0.1 * np.sign(z[1:, :10])            # copies 2 and 3 of bits 0..9: wrong, but barely
    z = z.ravel()
    assert code.decode(z, soft=False)["bits"][:10] != PAYLOAD[:10]           # majority vote is fooled
    r = code.decode(z, soft=True)
    assert r["bits"] == PAYLOAD and r["corrected"] == 20                     # confident copy 1 wins


def test_rs_corrects_up_to_limit():
    code = get_code("rs32")
    rng = np.random.default_rng(1)
    for _ in range(20):
        z = _logits(code.encode(PAYLOAD)).reshape(64, 8)
        bad = rng.choice(64, 17, replace=False)
        z[bad[:16], 0] *= -1                                                  # 16 confidently wrong bytes
        r = code.decode(z.ravel(), soft=False)
        assert r["ok"] and r["bits"] == PAYLOAD and r["corrected"] == 16
        z[bad[16], 0] *= -1                                                   # one more: 17 > 32 / 2
        assert code.decode(z.ravel(), soft=False)["bits"] != PAYLOAD


def test_rs_soft_erasures_beat_hard():
    code = get_code("rs32")
    z = _logits(code.encode(PAYLOAD)).reshape(64, 8)
    bad = np.random.default_rng(2).choice(64, 24, replace=False)
    z[bad, 3] = -0.2 * np.sign(z[bad, 3])              # 24 wrong bytes, each with one barely-wrong bit
    z = z.ravel()
    assert code.decode(z, soft=False)["bits"] != PAYLOAD                      # 24 > 16: hard decoding fails
    r = code.decode(z, soft=True)
    assert r["ok"] and r["bits"] == PAYLOAD and r["erasures"] > 0            # erasing unsure bytes fixes it


def test_noise_and_garbage_never_crash():
    code = get_code("rs32")
    rng = np.random.default_rng(3)
    for _ in range(50):
        r = code.decode(rng.normal(size=512))          # what an unmarked model or wrong key looks like
        assert not r["ok"] and r["bits"] != PAYLOAD    # noise must not "decode" at all
    with pytest.raises(ValueError):
        code.decode(np.zeros(500))                     # wrong length


def test_bad_parameters_and_capacity():
    assert get_code("rs32").n_bits <= 576 and get_code("rep2").n_bits <= 576  # fit the mean-mode carrier
    assert get_code("rep3").n_bits > 576                                      # needs --mode full
    for bad in [lambda: get_code("rs240"), lambda: get_code("bch"), lambda: get_code("rep1"),
                lambda: get_code("rs32", k_bits=250)]:
        with pytest.raises(ValueError):
            bad()
```

**Change: `requirements.txt`**

```diff
-# Planned, not needed yet (Phase 4, error-correcting codes). Uncomment when we get there:
-# reedsolo
-# galois
+# Error-correcting codes (Phase 4): Reed-Solomon, pure Python
+reedsolo>=1.7
```

**Ideas for improving P4.1 (not done yet)**

1. Faster failure on noise: the soft RS decoder makes up to 9 attempts (about 5 ms) before giving
   up on noise. Erasing in steps of 4 instead of 2 roughly halves that, at a small cost in edge cases.
2. Stronger code if needed: if P4.3 shows `rs32` breaking at low noise, try `rs40`
   (72 bytes = 576 bits, exactly fills the mean-mode carrier).
3. Interleaving: a fixed shuffle of codeword bit positions would protect against clustered errors.
   Not needed while X is random (each bit has its own independent row), so left out.
4. Confidence in the result: `decode` could also return the margin of the least sure byte, so the
   Phase 5 verifier can say how close to the edge a model is, not only VERIFIED / REJECTED.

### P4.2: Training with the full encoded payload (code: local, training: Colab)

**What it adds**

| File | Change |
|---|---|
| `training/train_watermarked.py` | new `--ecc` option; trains on the ECC codeword (512 bits for `rs32`); logs raw AND decoded errors per epoch; `final.json` gets `ecc`, `codeword_bits`, `decoded_ok`, `decoded_errors`; `run_dir()` names output folders (Phase 3 names unchanged) |
| `experiments/run_phase4.py` | new runner: sweeps ecc × layer × λ × seed, paired accuracy vs baseline, merges into `runs/wm_v1/summary.json` |
| `tests/test_phase4.py` | 7th test: a full 512-bit `rs32` codeword learned into a 576-dim carrier, 0 raw errors, decodes to the payload |

**Step 1: local checks (done 2026-10-26)**

```bash
python -m pytest tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py -v   # 16 passed, 1 skipped (liboqs)
```

CPU smoke run, 1 epoch, real CIFAR-10, THROWAWAY watermark key (not `keys/watermark_key.bin`),
then the runner building its table from that finished run:

```bash
python -c "import secrets; open('throwaway_wm_key.bin','wb').write(secrets.token_bytes(32))"
python -m training.train_watermarked --seed 0 --epochs 1 --lam 1 --n-bits 256 --ecc rs32 \
    --key throwaway_wm_key.bin --data-root <cifar dir> --out-root runs_smoke_p4
python -m experiments.run_phase4 --eccs rs32 --lams 1 --seeds 0 --epochs 1 --out-root runs_smoke_p4
```

```
params 160234 | layer features.6.0.weight (128, 64, 3, 3) | carrier dim 576 | payload 256 bits | ecc rs32 -> 512 embedded bits | lam 1 | device cpu
ep  1  cls 2.360  wm 0.5569  acc 0.3289  bit_errors 54/512  decoded 256/256  min|logit| 0.00
...
 ecc  | layer        | lam  | seed | wm acc | base acc | diff    | raw errors | decoded | min|logit|
 rs32 | features.6.0 | 1    | 0    | 0.3289 | 0.8612 | -0.5323 |   54/512   | 256/256 | 0.00
TOTAL DECODED ERRORS (this invocation): 256
```

The pipeline works end to end. One epoch is far too short (accuracy 0.33, 54 raw errors, decode fails);
it only proves the code runs. `decoded 256/256` means "decode failed", which is counted as all bits wrong.

**Step 2: λ simulation (local CPU, done 2026-10-26).** Watermark loss + weight decay only (no
cross-entropy), on the real `features.6.0.weight` with the real optimizer and 30-epoch cosine schedule.
It checks whether λ can beat weight decay before spending GPU time. Sanity check: for 32 bits, λ=1 it
predicts min|logit| 3.78; the real Phase 3 Colab runs measured 3.60.

```bash
python - <<'PY'
import numpy as np, torch
from embedding.ecc import get_code
from embedding.projection import ProjectionWatermark, get_weight
from training.model import SmallCNN
payload = [int(b) for b in np.random.default_rng(0).integers(0, 2, 256)]
steps = 30 * 391
for ecc, nb in [("none", 32), ("rs32", 256)]:
    code = get_code(ecc, nb); cw = code.encode(payload[:nb]); t = torch.tensor(cw, dtype=torch.float32)
    for lam in [0.1, 1, 5, 20]:
        torch.manual_seed(0); m = SmallCNN(width=32); w = get_weight(m, "features.6.0.weight")
        wm = ProjectionWatermark(b"\x07" * 32, "features.6.0.weight", code.n_bits, "mean", w.shape)
        opt = torch.optim.SGD([w], lr=0.05, momentum=0.9, nesterov=True, weight_decay=5e-4)
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=steps)
        first0 = None
        for s in range(steps):
            opt.zero_grad(); (lam * wm.loss(m, t)).backward(); opt.step(); sch.step()
            if first0 is None and s % 391 == 390:
                got, _ = wm.extract(m)
                if got == cw: first0 = (s + 1) // 391
        got, z = wm.extract(m); raw = sum(a != b for a, b in zip(got, cw)); d = code.decode(z)
        print("%-4s %3d bits  lam %-4g raw errors %3d/%d  decoded ok %-5s  min|logit| %.2f  first epoch with 0 raw errors: %s"
              % (ecc, nb, lam, raw, code.n_bits, d["ok"] and d["bits"] == payload[:nb], min(abs(x) for x in z), first0))
PY
```

```
none  32 bits  lam 0.1  raw errors   0/32  decoded ok True   min|logit| 1.98  first epoch with 0 raw errors: 1
none  32 bits  lam 1    raw errors   0/32  decoded ok True   min|logit| 3.78  first epoch with 0 raw errors: 1
none  32 bits  lam 5    raw errors   0/32  decoded ok True   min|logit| 5.11  first epoch with 0 raw errors: 1
none  32 bits  lam 20   raw errors   0/32  decoded ok True   min|logit| 6.30  first epoch with 0 raw errors: 1
rs32 256 bits  lam 0.1  raw errors  45/512  decoded ok False  min|logit| 0.00  first epoch with 0 raw errors: None
rs32 256 bits  lam 1    raw errors   4/512  decoded ok True   min|logit| 0.00  first epoch with 0 raw errors: None
rs32 256 bits  lam 5    raw errors   0/512  decoded ok True   min|logit| 0.97  first epoch with 0 raw errors: 3
rs32 256 bits  lam 20   raw errors   0/512  decoded ok True   min|logit| 2.04  first epoch with 0 raw errors: 1
```

Conclusion: 16× more bits need a much stronger push. λ=0.1 cannot work, λ=1 is at the edge, λ ≥ 5 is
needed. So the Stage A sweep is λ = 1, 5, 20 (not Phase 3's 0.1, 1, 5), and the runner default is 5.
Real training adds cross-entropy, so Colab numbers will differ; the simulation only sets the sweep range.

**Step 3: Colab (T4 GPU runtime), one block per cell**

```python
from google.colab import drive
drive.mount('/content/drive')
%cd /content/drive/MyDrive/pq-watermark
```

Get the new code into the Drive folder. The Phase 4 code is not committed yet, so `git pull` will not
bring it. Upload `phase4_colab_code.zip` (made 2026-10-26, in the Downloads folder of the Windows
machine; it holds `embedding/ecc.py`, `training/train_watermarked.py`, `experiments/run_phase4.py`,
`attacks/__init__.py`, `attacks/noise.py`, `tests/test_phase4.py`) into the Drive project folder, then:

```python
!unzip -o phase4_colab_code.zip && rm phase4_colab_code.zip
```

```python
!pip install -q "reedsolo>=1.7"
!python -m pytest tests/test_phase4.py -q          # expect 8 passed
!ls -l keys/watermark_key.bin release/payload.hex  # same key + payload as Phase 3
!cat release/payload.hex                           # must be a81a2b6f...57e4ddcb
```

Smoke test (2 epochs, about 1 minute after the CIFAR download):

```python
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m training.train_watermarked --seed 0 --epochs 2 --lam 5 --n-bits 256 --ecc rs32 --out-root runs/wm_v1_smoke
```

Expect `bit_errors` well below 256 and falling. If it stays near 256/512 the watermark is not training.

Stage A, tuning on seed 0 (6 runs, about 1 hour):

```python
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_phase4 --eccs rs32 --layers features.6.0.weight features.4.0.weight --lams 1 5 20 --seeds 0
```

Pick the config: among rows with **0 decoded errors and 0 raw errors**, take the smallest accuracy drop;
accuracy differences under 0.5 points count as a tie (one seed, seed spread about 1.2 points), and on a
tie take the larger min|logit| (more noise headroom for P4.3). The tie band was added after Stage A:
the first version ranked purely by accuracy and would have picked λ=5 over λ=20 on a 0.11-point gap,
although λ=20 has almost twice the margin (2.25 vs 1.21). If no row has 0 raw errors, take the
largest min|logit| among rows with 0 decoded errors and note it.
This cell applies the rule to `runs/wm_v1/summary.json` (one seed only, so a difference under about
1 point between configs is seed noise, not a real ranking):

```python
import json
s = json.load(open("runs/wm_v1/summary.json"))
cands = []
for k, v in s.items():
    ecc, layer, lam = k.split("/")
    r = [x for x in v["rows"] if x["seed"] == 0]
    if ecc == "rs32" and r:
        r = r[0]
        cands.append({"layer": layer + ".weight", "lam": float(lam[3:]), "diff": r["diff"],
                      "margin": r["min_abs_logit"], "raw": r["raw_bit_errors"], "dec": r["decoded_errors"]})
clean = [c for c in cands if c["raw"] == 0 and c["dec"] == 0]
if clean:
    top = max(c["diff"] for c in clean)
    tied = [c for c in clean if top - c["diff"] < 0.005]      # < 0.5 points apart on one seed = a tie
    best = max(tied, key=lambda c: c["margin"])               # tie -> larger margin (more robust)
else:
    best = max([c for c in cands if c["dec"] == 0], key=lambda c: c["margin"])
    print("NOTE: no config reached 0 raw errors; picked the largest margin among 0 decoded errors")
for c in sorted(cands, key=lambda c: (c["layer"], c["lam"])):
    print(c)
BEST_LAYER, BEST_LAM = best["layer"], best["lam"]
print("\nCHOSEN:", BEST_LAYER, "lam", BEST_LAM)
```

Stage B, chosen layer + λ on all seeds, plus `rep2` at the same setting for the ECC comparison in P4.3
(5 new runs, about 50 minutes; seed 0 of rs32 is skipped because Stage A already did it). The `{...}`
inserts the Python variables from the cell above:

```python
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_phase4 --eccs rs32 rep2 --layers {BEST_LAYER} --lams {BEST_LAM} --seeds 0 1 2
```

P4.2 is done when Stage B prints `TOTAL DECODED ERRORS (this invocation): 0` and the mean paired
accuracy difference for `rs32` is within about 1 to 2 points.

Export (this time the JSON and CSV files come back too, not only `model.pt`):

```python
!zip -qr /content/phase4_export.zip embedding training experiments tests runs/wm_v1 -x "*/__pycache__/*"
from google.colab import files; files.download('/content/phase4_export.zip')
```

Local: unzip into the project root, check `git status` shows nothing from `keys/`, then commit including
`runs/wm_v1/**/final.json`, `metrics.csv` and `runs/wm_v1/summary.json`. Paste the Stage A and Stage B
tables into this section.

**Real run on Colab (2026-10-26, T4 GPU)**

What actually happened, in order. Training first started on the local Windows CPU (6 Stage A runs in
parallel took about 6 minutes per epoch each, about 3.5 hours for Stage A), so it was stopped after
2 epochs and moved to Colab. The 2-epoch partial runs were deleted; their early signal already
matched the simulation: λ=1 still had 28 to 37 raw errors after epoch 2, λ=5 and λ=20 had 0.

1. The Drive folder `pq-watermark` on this Colab account did not have the Phase 1 to 3 code
   (`ModuleNotFoundError: embedding.projection`, no `keys/`, no `release/`); Phases 2 and 3 had been
   run from another account. Fix: a key-free zip of all project code + `release/` + the baseline
   `final.json` files (`pq_watermark_colab_code.zip`, 47 files) was uploaded and unzipped, and the
   watermark key was uploaded separately with `files.upload()` (never inside a zip).

```python
!unzip -o pq_watermark_colab_code.zip && rm pq_watermark_colab_code.zip
!mkdir -p keys
from google.colab import files
import shutil
up = files.upload()                                   # keys/watermark_key.bin from the laptop
shutil.move("watermark_key.bin", "keys/watermark_key.bin")
!pip install -q "reedsolo>=1.7"
!python -m pytest tests/test_phase4.py -q
!python -c "from embedding.keys import key_fingerprint, load_key; print('key fingerprint', key_fingerprint(load_key('keys/watermark_key.bin')))"
```

```
8 passed in 9.77s
-rw------- 1 root root 32 Oct 26 08:57 keys/watermark_key.bin
a81a2b6f42d6921ced51312865ca35492b2b763b186e6f1ae88323bd57e4ddcb
key fingerprint 81b57c4b28884f01        <- same as the laptop key that reproduces Phase 3 exactly
```

2. Stage A. The CIFAR-10 download took 32 minutes (88 kB/s from the dataset server); training ran at
   about 17 s per epoch, about 8.5 minutes per run.

```python
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_phase4 --eccs rs32 --layers features.6.0.weight features.4.0.weight --lams 1 5 20 --seeds 0
```

```
 ecc  | layer        | lam  | seed | wm acc | base acc | diff    | raw errors | decoded | min|logit|
 rs32 | features.6.0 | 1    | 0    | 0.8467 | 0.8612 | -0.0145 |    1/512   |   0/256 | 0.02
 rs32 | features.6.0 | 5    | 0    | 0.8319 | 0.8612 | -0.0293 |    0/512   |   0/256 | 1.21
 rs32 | features.6.0 | 20   | 0    | 0.8308 | 0.8612 | -0.0304 |    0/512   |   0/256 | 2.25
 rs32 | features.4.0 | 1    | 0    | 0.8392 | 0.8612 | -0.0220 |    1/512   |   0/256 | 0.00
 rs32 | features.4.0 | 5    | 0    | 0.8199 | 0.8612 | -0.0413 |    0/512   |   0/256 | 1.15
 rs32 | features.4.0 | 20   | 0    | 0.7947 | 0.8612 | -0.0665 |    0/512   |   0/256 | 2.31

TOTAL DECODED ERRORS (this invocation): 0
```

   - features.6.0 is better than features.4.0 at every λ (less accuracy lost for the same margin).
   - λ=1 is out (1 raw error, margin about 0), although ECC still decoded it perfectly: from epoch 3 on,
     the decoded payload was exact while up to 20 raw bits were still wrong.
   - λ=5 and λ=20 cost the same accuracy within noise (0.11 points apart on one seed), but λ=20 has
     almost twice the margin (2.25 vs 1.21). The selection rule was changed to treat gaps under
     0.5 points as a tie (see above); it picks **features.6.0, λ=20**.

```python
!mkdir -p /content/drive/MyDrive/pq-watermark/cifar_cache && cp -r /content/data/* /content/drive/MyDrive/pq-watermark/cifar_cache/
BEST_LAYER, BEST_LAM = "features.6.0.weight", 20.0
```

3. Stage B and the code comparison. After rs32 seeds 1 and 2 the accuracy cost was clearly above
   the 1 to 2 point target. Hypothesis: 512 bits nearly fill the 576-number carrier, so the projection
   is ill-conditioned. A local calculation (throwaway key) supported the idea on paper:

```
code  | bits | bits/576 | smallest singular value | norm of carrier needed for margin 2 (min-norm solution)
none  |  256 | 0.44     |   8.44                  |   1.68
rs8   |  320 | 0.56     |   6.34                  |   2.09
rs16  |  384 | 0.67     |   4.73                  |   2.69
rs24  |  448 | 0.78     |   3.03                  |   3.67
rs32  |  512 | 0.89     |   1.58                  |   6.76
```

   So `rs16` (384 bits) was added, and `rep2` was cut to 2 seeds (its role is the noise comparison).
   Commands actually run:

```python
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_phase4 --eccs rs32 rep2 --layers {BEST_LAYER} --lams {BEST_LAM} --seeds 0 1 2
#   (stopped during rep2 seed 2; rs32 seeds 1-2 and rep2 seeds 0-1 were finished)
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_phase4 --eccs rs32 rs16 --layers features.6.0.weight --lams 20 --seeds 0 1 2
!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m experiments.run_phase4 --eccs rep2 --layers features.6.0.weight --lams 20 --seeds 0 1
```

```
 ecc  | layer        | lam  | seed | wm acc | base acc | diff    | raw errors | decoded | min|logit|
 rs32 | features.6.0 | 20   | 0    | 0.8308 | 0.8612 | -0.0304 |    0/512   |   0/256 | 2.25
 rs32 | features.6.0 | 20   | 1    | 0.8033 | 0.8532 | -0.0499 |    0/512   |   0/256 | 2.24
 rs32 | features.6.0 | 20   | 2    | 0.8252 | 0.8378 | -0.0126 |    0/512   |   0/256 | 2.24
 rs16 | features.6.0 | 20   | 0    | 0.8209 | 0.8612 | -0.0403 |    0/384   |   0/256 | 2.70
 rs16 | features.6.0 | 20   | 1    | 0.8075 | 0.8532 | -0.0457 |    0/384   |   0/256 | 2.71
 rs16 | features.6.0 | 20   | 2    | 0.8395 | 0.8378 | +0.0017 |    0/384   |   0/256 | 2.71

TOTAL DECODED ERRORS (this invocation): 0

 ecc  | layer        | lam  | seed | wm acc | base acc | diff    | raw errors | decoded | min|logit|
 rep2 | features.6.0 | 20   | 0    | 0.8251 | 0.8612 | -0.0361 |    0/512   |   0/256 | 1.85
 rep2 | features.6.0 | 20   | 1    | 0.8052 | 0.8532 | -0.0480 |    0/512   |   0/256 | 1.84

TOTAL DECODED ERRORS (this invocation): 0
```

| Code | Bits | Paired diff per seed (points) | Mean ± std (points) | Mean acc | Min margin |
|---|---|---|---|---|---|
| rs32 | 512 | −3.04 / −4.99 / −1.26 | −3.10 ± 1.87 | 0.8198 | 2.24 |
| rs16 | 384 | −4.03 / −4.57 / +0.17 | −2.81 ± 2.59 | 0.8226 | 2.70 |
| rep2 | 512 | −3.61 / −4.80 | −4.21 ± 0.84 (2 seeds) | 0.8152 | 1.84 |

   - The capacity hypothesis was **not** supported: rs16 costs the same accuracy as rs32 (paired by
     seed, rs16 minus rs32 = −0.99 / +0.42 / +1.43 points). Fewer bits only bought a larger margin.
   - Likely reason: the BCE watermark loss never reaches zero, so it keeps pushing until weight decay
     balances it, whatever the number of bits. The cost comes from that push, not from capacity
     (Stage A agrees: λ=5 and λ=20 cost the same; only λ=1, too weak to hold every bit, cost less).
   - Seed 2 looks flattering again (rs16 seed 2 is above its baseline). Baseline seed 2 (0.8378) is
     1.5 to 2.3 points below the other baselines while watermarked seed-2 models are usually the best
     of their group, so the reported means probably understate the cost slightly.

4. Decision (team/faculty discussion pending): accept the measured accuracy cost as a known Phase 4
   limitation; judge Phase 4 on its done-when (noise survival, P4.3). Proposed fix for later: a
   margin-capped (hinge) watermark loss that stops pushing once each bit is past a target margin.

5. Mallory model for Phase 5 (rs32, λ=20, features.6.0, seed 3, Mallory's key and payload):

```python
!mkdir -p mallory/keys mallory/release
!echo 7d01074602daa866d17efe2f3c1022a75eea2e5b7c4f5c57de83ac94074d9877 > mallory/release/payload.hex
from google.colab import files
import shutil
up = files.upload()                                   # mallory/keys/watermark_key.bin
shutil.move("watermark_key.bin", "mallory/keys/watermark_key.bin")
!python -c "from embedding.keys import key_fingerprint, load_key; fp = key_fingerprint(load_key('mallory/keys/watermark_key.bin')); assert fp == '59022180cd831ada', 'WRONG KEY: ' + fp; print('Mallory key OK', fp)" && CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 python -m training.train_watermarked --seed 3 --epochs 30 --lam 20 --n-bits 256 --ecc rs32 --layer features.6.0.weight --key mallory/keys/watermark_key.bin --payload mallory/release/payload.hex --out-root mallory/runs
```

   The first attempt (without the fingerprint assert) uploaded OUR key by mistake (both files are
   called `watermark_key.bin`): the model had Mallory's payload but key fingerprint 81b57c4b28884f01.
   It was caught locally from `final.json`, kept as an extra "insider" negative case in
   `mallory/runs/ourkey_lam20_n256_rs32/seed3/` (annotated), and the model was retrained with the
   assert above: accuracy 0.8274, 0/512 raw errors, 0 decoded errors, margin 2.02, fingerprint 59022180cd831ada.

6. Export and local import:

```python
!zip -qr /content/phase4_export.zip runs/wm_v1 mallory/runs -x "*/__pycache__/*"
from google.colab import files; files.download('/content/phase4_export.zip')
```

   Locally the zip was checked (all paths under `runs/wm_v1/` or `mallory/runs/`, nothing unsafe),
   extracted without the unfinished `rep2/seed2` folder, and every `final.json` was checked for the
   right key fingerprint and payload.

**P4.2 result:** 0 decoded errors on all 8 Stage B models and all 6 Stage A models (TOTAL DECODED
ERRORS 0). The accuracy part of the target (mean paired difference within about 1 to 2 points) is
**not met**: about −3 points for every code.

**Code: `experiments/run_phase4.py` (new)**

```python
"""Phase 4 runner (COLAB): trains every (ecc, layer, lambda, seed) combination, then compares to the baseline.

    # Stage A, tuning on seed 0 (6 runs, about 1 hour on a T4). lambda 0.1 is left out on purpose:
    # 512 bits need a stronger push than 32 bits (see docs/phase_commands.md, P4.2 simulation)
    python -m experiments.run_phase4 --eccs rs32 --layers features.6.0.weight features.4.0.weight --lams 1 5 20 --seeds 0
    # Stage B, the chosen layer + lambda on all seeds, with rep2 for comparison
    python -m experiments.run_phase4 --eccs rs32 rep2 --layers <best layer> --lams <best lam> --seeds 0 1 2

Skips runs that are already finished. Merges into runs/wm_v1/summary.json (earlier stages are kept)
and prints a table. Accuracy differences are PAIRED: watermarked seed N minus baseline seed N.
"""
import argparse
import json
import os
import statistics as st
import subprocess
import sys
from pathlib import Path

from experiments.run_phase3 import baseline_acc
from training.train_watermarked import run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eccs", nargs="+", default=["rs32"])
    ap.add_argument("--layers", nargs="+", default=["features.6.0.weight"])
    ap.add_argument("--lams", type=float, nargs="+", default=[5.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--n-bits", type=int, default=256)
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--mode", default="mean")
    ap.add_argument("--out-root", default="runs/wm_v1")
    ap.add_argument("--baseline-dir", default="runs/baseline")
    args = ap.parse_args()

    configs = [(e, l, lam) for e in args.eccs for l in args.layers for lam in args.lams]
    for ecc, layer, lam in configs:
        for seed in args.seeds:
            cmd = [sys.executable, "-m", "training.train_watermarked", "--seed", str(seed),
                   "--epochs", str(args.epochs), "--lam", str(lam), "--n-bits", str(args.n_bits),
                   "--ecc", ecc, "--width", str(args.width), "--layer", layer, "--mode", args.mode,
                   "--out-root", args.out_root]
            print(">>>", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True, env=dict(os.environ, PYTHONUNBUFFERED="1"))

    summary_path = Path(args.out_root) / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    print("\n ecc  | layer        | lam  | seed | wm acc | base acc | diff    | raw errors | decoded | min|logit|")
    for ecc, layer, lam in configs:
        rows = []
        for seed in args.seeds:
            f = json.loads((run_dir(args.out_root, lam, args.n_bits, ecc, layer, seed) / "final.json").read_text())
            b = baseline_acc(args.baseline_dir, seed, args.width)
            diff = None if b is None else f["final_test_acc"] - b
            rows.append({"seed": seed, "wm_acc": f["final_test_acc"], "base_acc": b, "diff": diff,
                         "raw_bit_errors": f["bit_errors"], "decoded_errors": f["decoded_errors"],
                         "min_abs_logit": f["min_abs_logit"]})
            print(" %-5s| %-13s| %-5g| %-5d| %.4f | %s | %s | %4d/%-5d | %3d/%-3d | %.2f" % (
                ecc, layer.replace(".weight", ""), lam, seed, f["final_test_acc"],
                "%.4f" % b if b is not None else "  n/a ", "%+.4f" % diff if diff is not None else "  n/a  ",
                f["bit_errors"], f["codeword_bits"], f["decoded_errors"], args.n_bits, f["min_abs_logit"]))
        diffs = [r["diff"] for r in rows if r["diff"] is not None]
        summary["%s/%s/lam%g" % (ecc, layer.replace(".weight", ""), lam)] = {
            "n_bits": args.n_bits,
            "rows": rows,
            "mean_wm_acc": st.mean(r["wm_acc"] for r in rows),
            "mean_paired_diff": st.mean(diffs) if diffs else None,
            "std_paired_diff": st.stdev(diffs) if len(diffs) > 1 else None,
            "total_raw_bit_errors": sum(r["raw_bit_errors"] for r in rows),
            "total_decoded_errors": sum(r["decoded_errors"] for r in rows),
            "min_abs_logit": min(r["min_abs_logit"] for r in rows),
        }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    total = sum(summary["%s/%s/lam%g" % (e, l.replace(".weight", ""), lam)]["total_decoded_errors"]
                for e, l, lam in configs)
    print("\nTOTAL DECODED ERRORS (this invocation): %d" % total)
    print("wrote", summary_path)


if __name__ == "__main__":
    main()
```

**Change: `training/train_watermarked.py`**

```diff
diff --git a/training/train_watermarked.py b/training/train_watermarked.py
index b7a52b7..46f4b56 100644
--- a/training/train_watermarked.py
+++ b/training/train_watermarked.py
@@ -1,8 +1,10 @@
-"""Phase 3: train SmallCNN with the projection watermark  (runs on COLAB, GPU).
+"""Phase 3/4: train SmallCNN with the projection watermark  (runs on COLAB, GPU).
 
-    python -m training.train_watermarked --seed 0 --epochs 30 --lam 1.0 --n-bits 32
+    python -m training.train_watermarked --seed 0 --epochs 30 --lam 1.0 --n-bits 32                  # Phase 3
+    python -m training.train_watermarked --seed 0 --epochs 30 --lam 1.0 --n-bits 256 --ecc rs32      # Phase 4
 
-Total_Loss = CrossEntropy + lam * BCE(sigmoid(X @ v), payload_bits)
+Total_Loss = CrossEntropy + lam * BCE(sigmoid(X @ v), codeword_bits)
+codeword = ECC-encoded first n_bits of the payload (with --ecc none it is the payload itself).
 
 Same recipe as the baseline: SGD lr 0.05, momentum 0.9, Nesterov, wd 5e-4,
 cosine annealing over the epochs, batch 128, final-epoch metrics only.
@@ -21,12 +23,24 @@ import torchvision
 import torchvision.transforms as T
 from torch.utils.data import DataLoader
 
+from embedding.ecc import get_code
 from embedding.keys import key_fingerprint, load_key, load_payload_bits
 from embedding.projection import ProjectionWatermark, get_weight
 from training.model import SmallCNN
 from training.seed import set_seed
 
 MEAN, STD = (0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)
+DEFAULT_LAYER = "features.6.0.weight"
+
+
+def run_dir(out_root, lam, n_bits, ecc, layer, seed):
+    """Phase 3 runs keep their old names (lam1_n32); ECC and a non-default layer extend the name."""
+    name = "lam%g_n%d" % (lam, n_bits)
+    if ecc != "none":
+        name += "_" + ecc
+    if layer != DEFAULT_LAYER:
+        name += "_" + layer.replace(".weight", "")
+    return Path(out_root) / name / ("seed%d" % seed)
 
 
 def make_loaders(root, batch_size, workers=2):
@@ -55,8 +69,9 @@ def main():
     ap.add_argument("--seed", type=int, default=0)
     ap.add_argument("--epochs", type=int, default=30)
     ap.add_argument("--lam", type=float, default=1.0)
-    ap.add_argument("--n-bits", type=int, default=32)
-    ap.add_argument("--layer", default="features.6.0.weight")
+    ap.add_argument("--n-bits", type=int, default=32, help="payload bits to embed (prefix of payload.hex)")
+    ap.add_argument("--ecc", default="none", help="none, rep<r> or rs<parity bytes>, see embedding/ecc.py")
+    ap.add_argument("--layer", default=DEFAULT_LAYER)
     ap.add_argument("--mode", choices=["mean", "full"], default="mean")
     ap.add_argument("--width", type=int, default=32)
     ap.add_argument("--lr", type=float, default=0.05)
@@ -68,7 +83,7 @@ def main():
     ap.add_argument("--force", action="store_true")
     args = ap.parse_args()
 
-    out = Path(args.out_root) / ("lam%g_n%d" % (args.lam, args.n_bits)) / ("seed%d" % args.seed)
+    out = run_dir(args.out_root, args.lam, args.n_bits, args.ecc, args.layer, args.seed)
     if (out / "final.json").exists() and not args.force:
         print("already finished, skipping:", out)
         return
@@ -78,13 +93,16 @@ def main():
     device = "cuda" if torch.cuda.is_available() else "cpu"
     key = load_key(args.key)
     payload = load_payload_bits(args.payload, args.n_bits)
-    bits = torch.tensor(payload, dtype=torch.float32, device=device)
+    code = get_code(args.ecc, args.n_bits)
+    codeword = code.encode(payload)
+    bits = torch.tensor(codeword, dtype=torch.float32, device=device)
 
     model = SmallCNN(width=args.width).to(device)
     num_params = sum(p.numel() for p in model.parameters())
-    wm = ProjectionWatermark(key, args.layer, args.n_bits, args.mode, get_weight(model, args.layer).shape)
-    print("params %d | layer %s %s | carrier dim %d | bits %d | lam %g | device %s"
-          % (num_params, args.layer, tuple(get_weight(model, args.layer).shape), wm.dim, args.n_bits, args.lam, device))
+    wm = ProjectionWatermark(key, args.layer, code.n_bits, args.mode, get_weight(model, args.layer).shape)
+    print("params %d | layer %s %s | carrier dim %d | payload %d bits | ecc %s -> %d embedded bits | lam %g | device %s"
+          % (num_params, args.layer, tuple(get_weight(model, args.layer).shape), wm.dim, args.n_bits,
+             args.ecc, code.n_bits, args.lam, device))
 
     train_loader, test_loader = make_loaders(args.data_root, args.batch_size)
     opt = torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, nesterov=True, weight_decay=5e-4)
@@ -92,7 +110,8 @@ def main():
 
     with open(out / "metrics.csv", "w", newline="") as f:
         w = csv.writer(f)
-        w.writerow(["epoch", "loss_cls", "loss_wm", "test_acc", "bit_errors", "ber", "min_abs_logit", "seconds"])
+        w.writerow(["epoch", "loss_cls", "loss_wm", "test_acc", "bit_errors", "ber", "min_abs_logit", "seconds",
+                    "decoded_errors"])
         t0 = time.time()
         for epoch in range(1, args.epochs + 1):
             model.train()
@@ -113,18 +132,23 @@ def main():
 
             acc = evaluate(model, test_loader, device)
             got, logits = wm.extract(model)
-            errors = sum(int(a != b) for a, b in zip(got, payload))
-            row = [epoch, s_cls / n, s_wm / n, acc, errors, errors / args.n_bits,
-                   min(abs(z) for z in logits), time.time() - t0]
+            errors = sum(int(a != b) for a, b in zip(got, codeword))          # raw, before ECC
+            dec = code.decode(logits)
+            dec_errors = (sum(int(a != b) for a, b in zip(dec["bits"], payload))
+                          if dec["ok"] else args.n_bits)                     # failed decode counts as all wrong
+            row = [epoch, s_cls / n, s_wm / n, acc, errors, errors / code.n_bits,
+                   min(abs(z) for z in logits), time.time() - t0, dec_errors]
             w.writerow(row)
             f.flush()
-            print("ep %2d  cls %.3f  wm %.4f  acc %.4f  bit_errors %d/%d  min|logit| %.2f"
-                  % (epoch, row[1], row[2], acc, errors, args.n_bits, row[6]))
+            print("ep %2d  cls %.3f  wm %.4f  acc %.4f  bit_errors %d/%d  decoded %d/%d  min|logit| %.2f"
+                  % (epoch, row[1], row[2], acc, errors, code.n_bits, dec_errors, args.n_bits, row[6]))
 
     torch.save(model.state_dict(), out / "model.pt")
     final = {"seed": args.seed, "epochs": args.epochs, "lam": args.lam, "n_bits": args.n_bits,
+             "ecc": args.ecc, "codeword_bits": code.n_bits,
              "layer": args.layer, "mode": args.mode, "width": args.width, "num_params": num_params,
-             "final_test_acc": acc, "bit_errors": errors, "ber": errors / args.n_bits,
+             "final_test_acc": acc, "bit_errors": errors, "ber": errors / code.n_bits,
+             "decoded_ok": dec["ok"], "decoded_errors": dec_errors,
              "min_abs_logit": row[6], "payload_bits": "".join(map(str, payload)),
              "key_fingerprint": key_fingerprint(key), "seconds": time.time() - t0}
     (out / "final.json").write_text(json.dumps(final, indent=2))
```

**Change: `tests/test_phase4.py` (7th test added)**

```python
def test_full_rs32_codeword_embeds_in_576_dim_carrier():
    """P4.2 in miniature: 512 codeword bits into a carrier the size of features.6.0 in mean mode."""
    torch = pytest.importorskip("torch")
    from embedding.projection import ProjectionWatermark

    class Mid(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = torch.nn.Conv2d(64, 8, 3, bias=False)     # mean-mode dim 64*3*3 = 576

    torch.manual_seed(0)
    m = Mid()
    code = get_code("rs32")
    cw = code.encode(PAYLOAD)
    wm = ProjectionWatermark(b"\x01" * 32, "conv.weight", code.n_bits, "mean", m.conv.weight.shape)
    target = torch.tensor(cw, dtype=torch.float32)
    opt = torch.optim.SGD(m.parameters(), lr=5.0)
    for _ in range(300):
        opt.zero_grad()
        wm.loss(m, target).backward()
        opt.step()
    got, logits = wm.extract(m)
    assert got == cw                                               # 0 raw errors on all 512 bits
    r = code.decode(logits)
    assert r["ok"] and r["bits"] == PAYLOAD
    with pytest.raises(ValueError):                                 # rep3 (768 bits) does not fit
        ProjectionWatermark(b"\x01" * 32, "conv.weight", get_code("rep3").n_bits, "mean", m.conv.weight.shape)
```

**Ideas for improving P4.2 (not done yet)**

1. A `--key` option on `run_phase4.py`: today it always uses `keys/watermark_key.bin`; passing the key
   path through would allow smoke runs with a throwaway key without calling the trainer directly.
2. λ warm-up: start λ high (e.g. 20) for the first epochs to lock the bits in, then lower it so
   cross-entropy has more freedom; could reduce the accuracy cost while keeping the margin.
3. Margin-aware loss: BCE keeps pushing bits that are already safe. A hinge loss
   `max(0, m - s*z)` (s = ±1 from the bit) stops at margin m and spends the effort on weak bits only.
4. Early warning: stop and report a run if raw errors are still above, say, 25% after 5 epochs,
   instead of finishing 30 epochs of a run that cannot succeed.
5. Record wall-clock seconds per run in `summary.json` to plan Phase 6 and 7 GPU budgets.

### P4.3: Light-noise robustness test (local)

**What it adds**

| File | Purpose |
|---|---|
| `attacks/noise.py` | `add_gaussian_noise(model, level, layers=None, generator=None)`: noisy COPY of a model, noise std = level × each tensor's own std. Reused by the Phase 6 attack suite |
| `experiments/phase4_noise_test.py` | for each noise level, 20 noisy copies → extract → ECC decode; prints raw errors, no-ECC errors, decoded OK, margin, optional test accuracy; writes `noise_test.json` next to the model; prints the DONE-WHEN verdict |
| `tests/test_phase4.py` | 8th test: the noise helper returns a copy, touches only chosen layers, and its noise is 10% of the std at level 0.1 |

"Light" = noise ≤ 5% of each weight tensor's std (`--light 0.05`). Justification measured below:
at 5% the real baselines lose at most 0.6 accuracy points.

**Command for the real P4.3 run (after P4.2 Stage B, needs `keys/watermark_key.bin`)**

```bash
for s in 0 1 2; do
  python -m experiments.phase4_noise_test --model runs/wm_v1/<run name>/seed$s/model.pt --data-root data
done
# same for the rep2 runs, to compare the two codes
python -m experiments.phase4_noise_test --model runs/baseline/seed0/model.pt --ecc rs32 --n-bits 256 --levels 0 0.05 --trials 5   # negative control
```

`<run name>` is the Stage B folder, e.g. `lam5_n256_rs32` (layer features.6.0) or `lam5_n256_rs32_features.4.0`.
P4.3 (and Phase 4) is done when all three rs32 seeds print `DONE-WHEN ... PASSED`.

**Local verification of the script (done 2026-10-26).** No Phase 4 model exists yet, so the script was
exercised on a STAND-IN: the real baseline seed 0 with the full 512-bit rs32 codeword pushed into its
carrier by watermark-only optimisation (Adam, 2000 steps) with a THROWAWAY key. Without cross-entropy
this wrecked the model's accuracy (0.1753), so only the watermark columns of the stand-in mean anything.
Real joint training (P4.2) is what gives real numbers.

```bash
python -m experiments.phase4_noise_test --model <stand-in>/model.pt --key throwaway_wm_key.bin
```

```
settings from .../final.json: ecc rs32 | payload 256 bits -> 512 embedded | layer features.6.0.weight | mode mean | 20 trials per level

noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     3.53        | -
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     3.53        | -
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     3.53        | -
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     3.53        | -
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     3.54        | -
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     3.51        | -
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     3.18        | -
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.30        | -
 200% |     0 /    0.4 / 3              |    0.2                  |  20/20     |     0.48        | -
 300% |     2 /    6.8 / 14             |    3.4                  |  20/20     |     0.07        | -
 400% |    15 /   21.5 / 29             |   10.3                  |  10/20     |     0.03        | -
 500% |    31 /   39.5 / 48             |   19.6                  |   0/20     |     0.02        | -

first level with a failed trial: 400%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
```

Reading it: at 300% noise, Phase 3 style reading (no ECC) would have about 3.4 wrong payload bits on
average and fail, while the RS decoder recovers the payload in 20/20 trials. ECC extends survival from
about 200% to about 300 to 350%. Errors are rare at low noise because the mean-mode carrier averages
128 filters, which shrinks independent noise about √128 ≈ 11×.

Negative control, unmarked baseline seed 0, same key and settings:

```bash
python -m experiments.phase4_noise_test --model runs/baseline/seed0/model.pt --key throwaway_wm_key.bin --ecc rs32 --n-bits 256 --levels 0 0.05 --trials 5
```

```
noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |   246 /  246.0 / 246            |  117.0                  |   0/5      |     0.00        | -
   5% |   245 /  246.0 / 247            |  115.6                  |   0/5      |     0.00        | -
```

About half the bits wrong (random) and no decode: correct.

What "light" means for real models: accuracy of the three real baselines under the same noise.

```bash
python - <<'PY'
import torch
from attacks.noise import add_gaussian_noise
from embedding.extract import load_smallcnn
from experiments.phase4_noise_test import test_accuracy
for s in (0, 1, 2):
    m = load_smallcnn("runs/baseline/seed%d/model.pt" % s)
    accs = [test_accuracy(add_gaussian_noise(m, lv, generator=torch.Generator().manual_seed(0)), "data")
            for lv in (0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0)]
    print("baseline seed%d  " % s + "  ".join("%g%%:%.4f" % (100 * lv, a) for lv, a in zip((0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0), accs)))
PY
```

```
baseline seed0  0%:0.8612  1%:0.8609  2%:0.8610  5%:0.8579  10%:0.8479  20%:0.8136  50%:0.5506  100%:0.1427
baseline seed1  0%:0.8532  1%:0.8525  2%:0.8516  5%:0.8472  10%:0.8363  20%:0.7876  50%:0.4305  100%:0.1022
baseline seed2  0%:0.8378  1%:0.8371  2%:0.8377  5%:0.8366  10%:0.8293  20%:0.8126  50%:0.6245  100%:0.1701
```

At ≤ 5% the models lose ≤ 0.6 points (light); at 50% they are ruined; at 100% they are near chance.
If the real Stage B models behave like the stand-in, random weight noise cannot remove the watermark
without first destroying the model. That is a claim to confirm on the real models, not yet a result.

**Problem found and fixed during P4.3:** when no tested level was ≤ `--light`, the verdict printed
`NOT YET` although nothing light had been tested. It now prints `NOT TESTED (no level <= --light)`.
The default levels were extended to 500% so the breaking point always shows.

**Code: `attacks/noise.py` (new)**

```python
"""Gaussian weight noise (Phase 4 light-noise check; reused by the Phase 6 attack suite).

Each chosen weight tensor W becomes  W + N(0, (level * std(W))^2): the noise is scaled to the
tensor's own spread, so level 0.05 means "5% of a typical weight" in every layer.
"""
import copy

import torch


def add_gaussian_noise(model, level, layers=None, generator=None):
    """Return a NOISY COPY of `model` (the original is untouched).

    layers: parameter names to perturb; None = every conv / linear weight (tensors with dim > 1).
    generator: a torch.Generator, so the same seed gives the same noise.
    """
    noisy = copy.deepcopy(model)
    params = dict(noisy.named_parameters())
    if layers is not None:
        missing = [n for n in layers if n not in params]
        if missing:
            raise KeyError("parameters not found: %s" % missing)
    with torch.no_grad():
        for name, p in params.items():
            if (layers is None and p.dim() > 1) or (layers is not None and name in layers):
                noise = torch.randn(p.shape, generator=generator, dtype=p.dtype)
                p.add_(noise.to(p.device) * level * p.std())
    return noisy
```

**Code: `experiments/phase4_noise_test.py` (new)**

```python
"""Phase 4 'done when' check (runs LOCALLY on CPU): does the full payload survive light weight noise?

    python -m experiments.phase4_noise_test --model runs/wm_v1/lam5_n256_rs32/seed0/model.pt
    python -m experiments.phase4_noise_test --model ... --data-root data      # also measure test accuracy

Settings (ecc, n_bits, layer, mode, width) come from the final.json next to the model unless given.
For every noise level, `--trials` noisy copies are made (noise on every conv / linear weight,
scaled to each tensor's own std), the watermark is extracted and ECC-decoded.
"no-ECC errors" = errors in the first n_bits raw bits, where every code keeps the payload,
i.e. what Phase 3 style reading would give on the same noisy model.
Writes noise_test.json next to the model.
"""
import argparse
import json
import statistics as st
from pathlib import Path

import torch

from attacks.noise import add_gaussian_noise
from embedding.ecc import get_code
from embedding.extract import load_smallcnn
from embedding.keys import load_key, load_payload_bits
from embedding.projection import ProjectionWatermark, get_weight

DEFAULTS = {"ecc": "none", "n_bits": 32, "layer": "features.6.0.weight", "mode": "mean", "width": 32}


def fill_settings(args):
    """Missing CLI settings are taken from final.json, then from DEFAULTS. Returns where they came from."""
    f = Path(args.model).parent / "final.json"
    run = json.loads(f.read_text()) if f.exists() else {}
    for k, default in DEFAULTS.items():
        if getattr(args, k) is None:
            setattr(args, k, run.get(k, default))
    return str(f) if f.exists() else "defaults"


@torch.no_grad()
def test_accuracy(model, data_root):
    import torchvision
    import torchvision.transforms as T
    from torch.utils.data import DataLoader

    from training.data import CIFAR_MEAN, CIFAR_STD

    tf = T.Compose([T.ToTensor(), T.Normalize(CIFAR_MEAN, CIFAR_STD)])
    test = torchvision.datasets.CIFAR10(data_root, train=False, download=False, transform=tf)
    model.eval()
    correct = sum((model(x).argmax(1) == y).sum().item() for x, y in DataLoader(test, batch_size=1000))
    return correct / len(test)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--key", default="keys/watermark_key.bin")
    ap.add_argument("--payload", default="release/payload.hex")
    ap.add_argument("--ecc", default=None)
    ap.add_argument("--n-bits", dest="n_bits", type=int, default=None)
    ap.add_argument("--layer", default=None)
    ap.add_argument("--mode", default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--levels", type=float, nargs="+", default=[0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 3, 4, 5])
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--light", type=float, default=0.05, help="largest noise level that counts as 'light'")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--data-root", default=None, help="CIFAR-10 folder; if given, test accuracy is measured too")
    ap.add_argument("--out", default=None, help="default: noise_test.json next to the model")
    args = ap.parse_args()
    source = fill_settings(args)

    key = load_key(args.key)
    payload = load_payload_bits(args.payload, args.n_bits)
    code = get_code(args.ecc, args.n_bits)
    codeword = code.encode(payload)
    model = load_smallcnn(args.model, args.width)
    wm = ProjectionWatermark(key, args.layer, code.n_bits, args.mode, get_weight(model, args.layer).shape)
    print("settings from %s: ecc %s | payload %d bits -> %d embedded | layer %s | mode %s | %d trials per level"
          % (source, args.ecc, args.n_bits, code.n_bits, args.layer, args.mode, args.trials))

    def errors(a, b):
        return sum(int(x != y) for x, y in zip(a, b))

    rows = []
    print("\nnoise | raw errors /%-4d min/mean/max | no-ECC errors /%-3d mean | decoded OK | mean min|logit| | test acc"
          % (code.n_bits, args.n_bits))
    for level in args.levels:
        g = torch.Generator().manual_seed(args.seed)
        raw, plain, margins, recovered = [], [], [], 0
        for _ in range(args.trials):
            got, logits = wm.extract(add_gaussian_noise(model, level, generator=g))
            raw.append(errors(got, codeword))
            plain.append(errors(got[: args.n_bits], payload))
            margins.append(min(abs(z) for z in logits))
            d = code.decode(logits)
            recovered += int(d["ok"] and d["bits"] == payload)
        acc = None
        if args.data_root:
            acc = test_accuracy(add_gaussian_noise(model, level, generator=torch.Generator().manual_seed(args.seed)),
                                args.data_root)
        rows.append({"level": level, "raw_errors": raw, "no_ecc_errors": plain, "recovered": recovered,
                     "trials": args.trials, "mean_min_abs_logit": st.mean(margins), "test_acc": acc})
        print("%4g%% | %5d / %6.1f / %-5d          | %6.1f                  | %3d/%-3d    | %8.2f        | %s"
              % (100 * level, min(raw), st.mean(raw), max(raw), st.mean(plain), recovered, args.trials,
                 st.mean(margins), "%.4f" % acc if acc is not None else "-"))

    light = [r for r in rows if r["level"] <= args.light]
    broken = [r["level"] for r in rows if r["recovered"] < r["trials"]]
    passed = bool(light) and all(r["recovered"] == r["trials"] for r in light)
    verdict = "PASSED" if passed else "NOT YET" if light else "NOT TESTED (no level <= --light)"
    print("\nfirst level with a failed trial: %s" % ("%g%%" % (100 * broken[0]) if broken else "none"))
    print("DONE-WHEN (noise <= %g%% -> 0 errors after decoding, every trial): %s" % (100 * args.light, verdict))

    out = Path(args.out) if args.out else Path(args.model).parent / "noise_test.json"
    out.write_text(json.dumps({"model": str(args.model), "ecc": args.ecc, "n_bits": args.n_bits,
                               "codeword_bits": code.n_bits, "layer": args.layer, "mode": args.mode,
                               "seed": args.seed, "light": args.light, "passed": passed, "rows": rows}, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
```

**Change: `tests/test_phase4.py` (8th test added)**

```python
def test_gaussian_noise_copy_scope_and_scale():
    """P4.3 helper: returns a copy, touches only the chosen layers, noise std = level * weight std."""
    torch = pytest.importorskip("torch")
    from attacks.noise import add_gaussian_noise
    from training.model import SmallCNN

    m = SmallCNN(width=32)
    before = {k: v.clone() for k, v in m.state_dict().items()}
    g = torch.Generator().manual_seed(0)
    assert all(torch.equal(a, b) for a, b in zip(add_gaussian_noise(m, 0.0, generator=g).parameters(),
                                                 m.parameters()))           # level 0 changes nothing
    n = add_gaussian_noise(m, 0.1, layers=["features.6.0.weight"], generator=g)
    changed = {k for k, v in n.state_dict().items() if not torch.equal(v, before[k])}
    assert changed == {"features.6.0.weight"}                              # only the chosen layer
    assert all(torch.equal(v, before[k]) for k, v in m.state_dict().items())   # original untouched
    w, wn = m.features[6][0].weight, n.features[6][0].weight
    assert 0.09 < ((wn - w).std() / w.std()).item() < 0.11                 # 10% of the layer's std
    with pytest.raises(KeyError):
        add_gaussian_noise(m, 0.1, layers=["no.such.weight"])
```

**Real run (2026-10-26, local Windows CPU, real key, `--data-root data`)**

```bash
for r in lam20_n256_rs32/seed0 lam20_n256_rs32/seed1 lam20_n256_rs32/seed2 \
         lam20_n256_rs16/seed0 lam20_n256_rs16/seed1 lam20_n256_rs16/seed2 \
         lam20_n256_rep2/seed0 lam20_n256_rep2/seed1; do
  python -m experiments.phase4_noise_test --model runs/wm_v1/$r/model.pt --data-root data
done
python -m experiments.phase4_noise_test --model runs/baseline/seed0/model.pt --ecc rs32 --n-bits 256 \
    --levels 0 0.05 --trials 5 --out <scratch>/p43_baseline_control.json       # negative control
```

About 3 minutes per model. Each run wrote `noise_test.json` next to its model.

Summary, decoded OK out of 20 trials per noise level (noise std = level × each weight tensor's std):

| Model | ≤ 5% (light) | 100% | 200% | 300% | 400% | 500% | Accuracy at 0% → 5% → 100% |
|---|---|---|---|---|---|---|---|
| rs32 seed 0 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 4/20 | 0.8308 → 0.8256 → 0.1103 |
| rs32 seed 1 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 4/20 | 0.8033 → 0.8006 → 0.1462 |
| rs32 seed 2 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 3/20 | 0.8252 → 0.8202 → 0.1139 |
| rs16 seed 0 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 14/20 | 0.8209 → 0.8164 → 0.1782 |
| rs16 seed 1 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 14/20 | 0.8075 → 0.8034 → 0.2008 |
| rs16 seed 2 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 13/20 | 0.8395 → 0.8314 → 0.1103 |
| rep2 seed 0 | 20/20 | 20/20 | 20/20 | **14/20** | 4/20 | 0/20 | 0.8251 → 0.8220 → 0.1015 |
| rep2 seed 1 | 20/20 | 20/20 | 20/20 | **15/20** | 4/20 | 0/20 | 0.8052 → 0.7994 → 0.1766 |
| unmarked baseline seed 0 (control) | 0/5 | | | | | | 256/512 raw bits wrong |

**Done-when: MET.** Every Phase 4 model prints `DONE-WHEN (noise <= 5% -> 0 errors after decoding,
every trial): PASSED`, with 0 raw errors at every level up to 100%.

Reading it:
- At light noise (≤ 5%) the models lose at most 0.8 accuracy points and the watermark is untouched.
- The models are useless (≈ 10 to 20% accuracy, chance is 10%) at 100% noise; the payload survives
  up to 400% (rs32, rs16) and 200% (rep2). Random weight noise cannot remove the watermark without
  first destroying the model.
- ECC matters: at 400% rs32 has 12.4 to 12.6 raw errors and would have 6.2 to 6.4 wrong payload bits
  without ECC (Phase 3 style reading would fail every trial), yet decodes 20/20.
- Robustness ranks rs16 > rs32 > rep2, the same order as the margins (2.71 > 2.24 > 1.84): the larger
  margin of rs16 outweighs its weaker code (8 vs 16 repairable bytes) for random noise. rep2 (same
  512 bits as rs32) breaks first: repetition is a weaker code than Reed-Solomon at equal length.
- Which code is better against Phase 6 attacks (fine-tuning, pruning, quantization), where errors are
  not random, is open; both rs32 and rs16 go forward to Phase 6.

Full output:

```
== lam20_n256_rs32/seed0

noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.25        | 0.8308
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.25        | 0.8300
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.25        | 0.8295
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.25        | 0.8256
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8166
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.21        | 0.7778
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.01        | 0.4018
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.51        | 0.1103
 200% |     0 /    0.1 / 1              |    0.1                  |  20/20     |     0.37        | 0.1003
 300% |     0 /    2.9 / 6              |    1.8                  |  20/20     |     0.13        | 0.1120
 400% |     5 /   12.6 / 24             |    6.4                  |  20/20     |     0.03        | 0.1147
 500% |    14 /   25.6 / 35             |   12.2                  |   4/20     |     0.02        | 0.1099

first level with a failed trial: 500%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== lam20_n256_rs32/seed1

noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8033
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8038
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8023
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8006
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.7947
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.20        | 0.7607
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.01        | 0.5478
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.52        | 0.1462
 200% |     0 /    0.1 / 1              |    0.1                  |  20/20     |     0.37        | 0.1002
 300% |     0 /    2.9 / 6              |    1.8                  |  20/20     |     0.13        | 0.0904
 400% |     5 /   12.4 / 23             |    6.2                  |  20/20     |     0.03        | 0.0903
 500% |    14 /   25.6 / 35             |   12.2                  |   4/20     |     0.03        | 0.0922

first level with a failed trial: 500%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== lam20_n256_rs32/seed2

noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8252
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8262
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8244
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.24        | 0.8202
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.23        | 0.8047
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.20        | 0.7197
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.02        | 0.3311
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.52        | 0.1139
 200% |     0 /    0.1 / 1              |    0.1                  |  20/20     |     0.37        | 0.1001
 300% |     0 /    2.9 / 6              |    1.7                  |  20/20     |     0.13        | 0.0995
 400% |     5 /   12.5 / 23             |    6.2                  |  20/20     |     0.04        | 0.0964
 500% |    14 /   25.8 / 35             |   12.3                  |   3/20     |     0.03        | 0.0896

first level with a failed trial: 500%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== lam20_n256_rs16/seed0

noise | raw errors /384  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.70        | 0.8209
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.70        | 0.8194
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.70        | 0.8199
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.70        | 0.8164
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.70        | 0.8070
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.69        | 0.7706
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.55        | 0.5084
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.20        | 0.1782
 200% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.28        | 0.1326
 300% |     0 /    0.2 / 2              |    0.1                  |  20/20     |     0.40        | 0.1058
 400% |     1 /    3.0 / 7              |    1.9                  |  20/20     |     0.10        | 0.0966
 500% |     3 /    8.9 / 13             |    5.7                  |  14/20     |     0.07        | 0.0953

first level with a failed trial: 500%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== lam20_n256_rs16/seed1

noise | raw errors /384  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8075
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8073
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8067
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8034
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.7899
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.70        | 0.7288
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.55        | 0.3942
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.20        | 0.2008
 200% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.29        | 0.1194
 300% |     0 /    0.2 / 2              |    0.1                  |  20/20     |     0.40        | 0.1085
 400% |     0 /    2.8 / 7              |    1.7                  |  20/20     |     0.10        | 0.1081
 500% |     3 /    9.0 / 13             |    5.8                  |  14/20     |     0.07        | 0.1093

first level with a failed trial: 500%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== lam20_n256_rs16/seed2

noise | raw errors /384  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8395
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8383
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8371
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8314
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.71        | 0.8173
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.69        | 0.7690
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.54        | 0.3970
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     2.19        | 0.1103
 200% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.28        | 0.1006
 300% |     0 /    0.2 / 2              |    0.1                  |  20/20     |     0.39        | 0.0869
 400% |     0 /    2.8 / 7              |    1.7                  |  20/20     |     0.10        | 0.0842
 500% |     3 /    9.2 / 13             |    5.8                  |  13/20     |     0.07        | 0.0864

first level with a failed trial: 500%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== lam20_n256_rep2/seed0

noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.85        | 0.8251
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.85        | 0.8261
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.84        | 0.8245
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.84        | 0.8220
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.83        | 0.8043
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.81        | 0.7230
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.57        | 0.2598
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.07        | 0.1015
 200% |     0 /    1.0 / 4              |    0.5                  |  20/20     |     0.25        | 0.1028
 300% |     2 /    6.8 / 14             |    3.6                  |  14/20     |     0.04        | 0.0913
 400% |    13 /   21.1 / 27             |    9.3                  |   4/20     |     0.03        | 0.0881
 500% |    27 /   39.4 / 50             |   18.1                  |   0/20     |     0.02        | 0.0879

first level with a failed trial: 300%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== lam20_n256_rep2/seed1

noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.84        | 0.8052
   1% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.84        | 0.8041
   2% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.84        | 0.8019
   5% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.84        | 0.7994
  10% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.83        | 0.7880
  20% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.81        | 0.7461
  50% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.57        | 0.5059
 100% |     0 /    0.0 / 0              |    0.0                  |  20/20     |     1.07        | 0.1766
 200% |     0 /    1.0 / 4              |    0.5                  |  20/20     |     0.25        | 0.1083
 300% |     2 /    6.8 / 14             |    3.6                  |  15/20     |     0.04        | 0.1085
 400% |    14 /   21.1 / 27             |    9.4                  |   4/20     |     0.02        | 0.0978
 500% |    27 /   39.4 / 50             |   18.1                  |   0/20     |     0.02        | 0.0954

first level with a failed trial: 300%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): PASSED
== NEGATIVE CONTROL baseline seed0

noise | raw errors /512  min/mean/max | no-ECC errors /256 mean | decoded OK | mean min|logit| | test acc
   0% |   256 /  256.0 / 256            |  125.0                  |   0/5      |     0.00        | -
   5% |   254 /  255.4 / 257            |  125.6                  |   0/5      |     0.00        | -

first level with a failed trial: 0%
DONE-WHEN (noise <= 5% -> 0 errors after decoding, every trial): NOT YET
```

**Ideas for improving P4.3 (not done yet)**

1. Noise on the carrier layer only (`layers=[layer]`) as a second sweep: isolates the watermark's own
   robustness from what happens to the rest of the network.
2. Accuracy for more than one noisy copy per level (now trial 0 only), to put error bars on it.
3. A combined plot: accuracy and decode success against noise level on one chart, which is the clearest
   single picture for the write-up.
4. Speed: the 20 trials per level copy the whole model; copying only the carrier layer would be faster.
   Not needed at this model size (the full default sweep takes under a minute on CPU).

### P4.4: Record results (local, 2026-10-26)

Recorded:
- `docs/results_log.md`: Phase 4 entry (Stage A and B tables, code comparison, accuracy limitation and
  its likely cause, noise test, Mallory incident) and Phase 5 entry; the Phase 2 and 3 entries were
  added earlier the same day.
- `docs/phase_commands.md`: the real Colab commands and outputs under P4.2, the real noise-test
  outputs under P4.3, and the Phase 5 results on the Phase 4 models under "Phase 5".
- `skills.md`: bumped to v2 (status Phases 0 to 5, environment, file list, Phase 2 to 5 design and
  results, open items, changelog).
- Run artifacts: `runs/wm_v1/**/{model.pt,final.json,metrics.csv,noise_test.json}`,
  `runs/wm_v1/summary.json`, `mallory/runs/**`. `keys/` and `mallory/keys/` stay git-ignored.

Phase 4 verdict: **done when-criterion met** (full 256-bit payload, 0 errors after decoding at
≤ 5% weight noise, every trial, every model). Known limitation: about −3 accuracy points against
the paired baseline, above the roadmap's 1 to 2 point target; the fix (margin-capped loss) waits for
the team/faculty decision.

Not done yet: nothing is committed or pushed (the user decides when), including the merge `0f77055`
that fixes the seed 0 baseline file on GitHub.

**Ideas for improving P4.4 (not done yet)**

1. A small script that regenerates the results-log tables from `summary.json` and the
   `noise_test.json` files, so numbers are never copied by hand.
2. One plot for the write-up: accuracy and decode success against noise level for rs32, rs16, rep2.
3. Commit `runs/wm_v1` in one commit and the code in another, so code history stays readable.
4. Record Colab session facts (GPU type, torch version, time per epoch) in `final.json` automatically.

---

## Phase 5: Verifier tool

Goal: one command for an auditor: model file + public key + watermark key + signed manifest in,
VERIFIED or REJECTED out. Done when: wrong key, tampered manifest, an unmarked model and a model
watermarked by someone else are all rejected, and our own model passes.

Built 2026-10-26 on Windows (native liboqs, `venv/`) while Phase 4 training was still running, so
everything below was run on the **Phase 3 models** (`runs/wm_v0/lam1_n32`, ecc none, 32 bits). The same
commands work for Phase 4 models (see "Waiting on Phase 4").

### P5.1: Verifier CLI `verify/verify_model.py` (local)

**What it adds:** `verify_model(...)` (importable) and a CLI. Checks in order, stopping at the first failing stage:
1. release (reuses `verify.verify_release`): files load, key id, algorithm, ML-DSA signature, payload.hex
2. model: architecture and width from the SIGNED manifest, weights load, parameter count == manifest `num_params`
3. watermark: X·v with the watermark key, ECC decode
4. payload: decoded bits == first n_bits of SHA-256(signed manifest) (never trusted from payload.hex, never "decoder ok" alone)

Watermark settings (ecc, n_bits, layer, mode) are not in the manifest, so they come from the command
line, else the `final.json` next to the model, else Phase 3 defaults; the source is printed.

**Commands**

```bash
python -m verify.verify_model --model runs/wm_v0/lam1_n32/seed0/model.pt      # defaults: keys/public_key.bin, keys/watermark_key.bin, release/
python -m verify.verify_model --model runs/baseline/seed0/model.pt            # unmarked model
```

**Output: our Phase 3 model**

```
watermark settings (defaults): ecc none | n_bits 32 | layer features.6.0.weight | mode mean
PASS  load release files
PASS  key id matches manifest  (manifest=bae58d20d2964be6ef068a9ff17772af key=bae58d20d2964be6ef068a9ff17772af)
PASS  algorithm is ML-DSA-65
PASS  signature valid
PASS  payload.hex matches manifest
PASS  architecture is SmallCNN  (manifest says 'SmallCNN')
PASS  model loads at signed width 32
PASS  parameter count matches manifest  (model 160234, manifest 160234)
PASS  watermark read (ecc none, 32 values)  (min margin 3.60, corrected 0, erasures 0)
PASS  extracted payload == SHA-256(signed manifest)  (32 bits match)
VERIFIED
exit code 0
```

**Output: unmarked baseline**

```
watermark settings (defaults): ecc none | n_bits 32 | layer features.6.0.weight | mode mean
PASS  load release files
PASS  key id matches manifest  (manifest=bae58d20d2964be6ef068a9ff17772af key=bae58d20d2964be6ef068a9ff17772af)
PASS  algorithm is ML-DSA-65
PASS  signature valid
PASS  payload.hex matches manifest
PASS  architecture is SmallCNN  (manifest says 'SmallCNN')
PASS  model loads at signed width 32
PASS  parameter count matches manifest  (model 160234, manifest 160234)
PASS  watermark read (ecc none, 32 values)  (min margin 0.00, corrected 0, erasures 0)
FAIL  extracted payload == SHA-256(signed manifest)  (13 of 32 bits differ)
REJECTED
exit code 1
```

**Ideas for improving P5.1**

1. Manifest v2 with a signed `watermark` config (ecc, n_bits, layer, mode, key fingerprint). Today these
   come from an unsigned `final.json` or the command line. Changing the manifest changes the payload, so
   this needs a new release and retraining; do it together with any key rotation.
2. A `--json` output mode for scripts and CI, with the same checks as data.
3. Hash the model file and print it, so a report can be tied to the exact file that was checked.
4. A confidence line: the chance that random weights pass (2^-n_bits for ecc none; the RS decoding-radius
   bound for rs32), next to VERIFIED.
5. Use `final.json`'s `key_fingerprint` as a hint ("this model was trained with a different watermark key")
   on failure only; it is unsigned, so it can never make a model pass.

### P5.2: Mallory, a second developer (local)

**What it adds**

| File | Purpose |
|---|---|
| `experiments/phase5_make_mallory.py` | second ML-DSA-65 key pair + watermark key in `mallory/keys/` (git-ignored), signed release with developer_id "Mallory" in `mallory/release/`; `write_release()` helper reused by the tests; refuses to overwrite without `--force` |
| `experiments/phase5_mallory_standin.py` | STAND-IN Mallory model: our baseline seed 1 fine-tuned 1 epoch with CE + 5·BCE, Mallory's key and payload, Phase 3 style (ecc none, 32 bits); `final.json` says `"STAND_IN": true` |
| `.gitignore` | adds `mallory/keys/` |

Mallory claims the same public CIFAR-10 dataset, so the Merkle root is copied from our signed manifest
(`--cifar-root` hashes it instead).

**Commands**

```bash
python -m experiments.phase5_make_mallory
python -m experiments.phase5_mallory_standin --data-root data          # about 7 minutes on CPU while other training ran
python -m verify.verify_model --model mallory/runs/standin_lam5_n32/seed1/model.pt \
    --public-key mallory/keys/public_key.bin --wm-key mallory/keys/watermark_key.bin --release-dir mallory/release
```

**Output**

```
developer id : Mallory
key id       : 89add2f82197061c9c0e356e7d4f243c
wm key       : fingerprint 59022180cd831ada
merkle root  : 76c4deeb4da9723777c84f81fb7bf905d99b9633af7dab930cb913817be074ca (copied from release)
payload      : 7d01074602daa866d17efe2f3c1022a75eea2e5b7c4f5c57de83ac94074d9877
wrote        : mallory\keys (git-ignored) and mallory\release

# second run, guard:
mallory\release exists. Re-running gives Mallory new keys and a new payload, so any Mallory model trained on the old ones stops verifying. Use --force only if you mean it.

# stand-in:
acc 0.8155 | bit errors 0/32 | min|logit| 2.95 | 425 s | saved mallory\runs\standin_lam5_n32\seed1
```

```
watermark settings (final.json): ecc none | n_bits 32 | layer features.6.0.weight | mode mean
PASS  load release files
PASS  key id matches manifest  (manifest=89add2f82197061c9c0e356e7d4f243c key=89add2f82197061c9c0e356e7d4f243c)
PASS  algorithm is ML-DSA-65
PASS  signature valid
PASS  payload.hex matches manifest
PASS  architecture is SmallCNN  (manifest says 'SmallCNN')
PASS  model loads at signed width 32
PASS  parameter count matches manifest  (model 160234, manifest 160234)
PASS  watermark read (ecc none, 32 values)  (min margin 2.95, corrected 0, erasures 0)
PASS  extracted payload == SHA-256(signed manifest)  (32 bits match)
VERIFIED
exit code 0
```

The stand-in costs accuracy (0.8155 vs our baseline seed 1 at 0.8532) because one epoch of fine-tuning
at λ=5 is rough; it only has to carry Mallory's watermark for the negative cases.

**Ideas for improving P5.2**

1. Real Mallory model in the Phase 4 config, trained from scratch (see "Waiting on Phase 4").
2. A forger who copies our manifest AND re-signs it with their own key: covered implicitly (key id fails),
   could be an explicit case.
3. `--keys-dir` / `--release-dir` options on `phase2_make_release.py`, so Mallory could reuse it directly.

### P5.3: Negative-case suite (local): the "done when" check

**What it adds**

| File | Purpose |
|---|---|
| `experiments/phase5_negative_cases.py` | 8 cases per seed; each REJECTED case must fail at the RIGHT check; prints the DONE-WHEN verdict; exit 0/1; tampered copies and wrong keys only in a temp folder |
| `tests/test_phase5.py` | 8 self-contained tests: temp ML-DSA keys, temp releases, small models with the watermark pushed in; includes a full 256-bit rs32 payload case and 9 garbage inputs |

**Commands**

```bash
python -m experiments.phase5_negative_cases --seeds 0 1 2
python -m pytest tests/test_phase5.py -v
python -m pytest tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py tests/test_phase5.py -q
```

**Output: negative cases on Phase 3 models**

```
seed 0  (our model: runs/wm_v0/lam1_n32/seed0/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | extracted payload == SHA-256(s | 13 of 32 bits differ     | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | extracted payload == SHA-256(s | 13 of 32 bits differ     | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | extracted payload == SHA-256(s | 16 of 32 bits differ     | yes
 our model + MALLORY's files        | REJECTED | REJECTED | extracted payload == SHA-256(s | 19 of 32 bits differ     | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

seed 1  (our model: runs/wm_v0/lam1_n32/seed1/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | extracted payload == SHA-256(s | 17 of 32 bits differ     | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | extracted payload == SHA-256(s | 15 of 32 bits differ     | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | extracted payload == SHA-256(s | 16 of 32 bits differ     | yes
 our model + MALLORY's files        | REJECTED | REJECTED | extracted payload == SHA-256(s | 20 of 32 bits differ     | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

seed 2  (our model: runs/wm_v0/lam1_n32/seed2/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | extracted payload == SHA-256(s | 14 of 32 bits differ     | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | extracted payload == SHA-256(s | 17 of 32 bits differ     | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | extracted payload == SHA-256(s | 16 of 32 bits differ     | yes
 our model + MALLORY's files        | REJECTED | REJECTED | extracted payload == SHA-256(s | 20 of 32 bits differ     | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

DONE-WHEN (4 negative cases rejected, own model passes): PASSED
```

"Right reason": a wrong public key fails at the key id, a tampered manifest at the signature, and the
watermark cases (wrong watermark key, unmarked model, someone else's model, our model under Mallory's
files) fail at the payload comparison, i.e. the bits read out are near random (13 to 20 of 32 differ).

**Output: tests**

```
tests/test_phase5.py::test_own_model_verified PASSED                     [ 12%]
tests/test_phase5.py::test_own_model_verified_rs32_full_payload PASSED   [ 25%]
tests/test_phase5.py::test_wrong_public_key_rejected PASSED              [ 37%]
tests/test_phase5.py::test_wrong_watermark_key_rejected PASSED           [ 50%]
tests/test_phase5.py::test_tampered_manifest_rejected PASSED             [ 62%]
tests/test_phase5.py::test_unmarked_model_rejected PASSED                [ 75%]
tests/test_phase5.py::test_someone_elses_model PASSED                    [ 87%]
tests/test_phase5.py::test_garbage_inputs_never_crash PASSED             [100%]
============================== 8 passed in 5.15s ==============================
26 passed   (phase 2: 5, phase 3: 5, phase 4: 8, phase 5: 8)
```

**Verdict on Phase 3 models: DONE-WHEN PASSED** (24 of 24 cases as expected, all for the right reason).

**Ideas for improving P5.3**

1. Run the suite in CI on every push (needs liboqs in the CI image).
2. Add cases for the Phase 6 attacks (fine-tuned / pruned / quantised copies of our model), with the
   expected verdict depending on attack strength.
3. A false-positive estimate: run the verifier on many unmarked models (e.g. 50 short training runs) and
   report how many pass (expected 0).

### Results on the Phase 4 models (2026-10-26, local Windows, liboqs 0.16.0)

The "Waiting on Phase 4" steps below were carried out. The real Mallory model was trained on Colab
in the Phase 4 config (rs32, λ=20, features.6.0, seed 3; commands under P4.2 step 5): accuracy
0.8274, 0 raw / 0 decoded errors, margin 2.02, key fingerprint 59022180cd831ada.

```bash
python -m verify.verify_model --model runs/wm_v1/lam20_n256_rs32/seed0/model.pt
for ecc in rs32 rs16; do
  python -m experiments.phase5_negative_cases --seeds 0 1 2 \
      --model-pattern "runs/wm_v1/lam20_n256_${ecc}/seed{seed}/model.pt" \
      --mallory-model mallory/runs/lam20_n256_rs32/seed3/model.pt
done
python -m verify.verify_model --model mallory/runs/ourkey_lam20_n256_rs32/seed3/model.pt      # insider case
python -m verify.verify_model --model mallory/runs/lam20_n256_rs32/seed3/model.pt \
    --public-key mallory/keys/public_key.bin --wm-key mallory/keys/watermark_key.bin --release-dir mallory/release
```

| Run | Cases | Result |
|---|---|---|
| rs32 seeds 0 to 2 | 8 × 3 = 24 | all as expected, each for the right reason: `DONE-WHEN ... PASSED` |
| rs16 seeds 0 to 2 | 8 × 3 = 24 | all as expected, each for the right reason: `DONE-WHEN ... PASSED` |
| insider: our watermark key, Mallory's payload | 1 | REJECTED, 116 of 256 bits differ from our signed manifest |
| Mallory's model + Mallory's files | 1 | VERIFIED, 256/256 bits, margin 2.02 |

**Phase 5 done-when: MET** on the Phase 4 models (it was already met on the Phase 3 models).

New compared with Phase 3: with Reed-Solomon, a wrong key, an unmarked model and someone else's model
mostly fail already at "watermark read" (the decoder finds no valid codeword in random-looking scores),
before the payload comparison. ECC thus adds a second, independent barrier. The insider case shows
the other one: a watermark readable with our key still fails unless it matches OUR signed manifest,
which needs our ML-DSA secret key.

Verifier on our rs32 seed 0 model:

```
watermark settings (final.json): ecc rs32 | n_bits 256 | layer features.6.0.weight | mode mean
PASS  load release files
PASS  key id matches manifest  (manifest=bae58d20d2964be6ef068a9ff17772af key=bae58d20d2964be6ef068a9ff17772af)
PASS  algorithm is ML-DSA-65
PASS  signature valid
PASS  payload.hex matches manifest
PASS  architecture is SmallCNN  (manifest says 'SmallCNN')
PASS  model loads at signed width 32
PASS  parameter count matches manifest  (model 160234, manifest 160234)
PASS  watermark read (ecc rs32, 512 values)  (min margin 2.25, corrected 0, erasures 0)
PASS  extracted payload == SHA-256(signed manifest)  (256 bits match)
VERIFIED
```

Negative-case suite output:

```
== Phase 4 rs32

seed 0  (our model: runs/wm_v1/lam20_n256_rs32/seed0/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 our model + MALLORY's files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

seed 1  (our model: runs/wm_v1/lam20_n256_rs32/seed1/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 our model + MALLORY's files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

seed 2  (our model: runs/wm_v1/lam20_n256_rs32/seed2/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 our model + MALLORY's files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

DONE-WHEN (4 negative cases rejected, own model passes): PASSED
exit 0
== Phase 4 rs16

seed 0  (our model: runs/wm_v1/lam20_n256_rs16/seed0/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 our model + MALLORY's files        | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

seed 1  (our model: runs/wm_v1/lam20_n256_rs16/seed1/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 our model + MALLORY's files        | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

seed 2  (our model: runs/wm_v1/lam20_n256_rs16/seed2/model.pt)
 case                               | expected | got      | first failing check            | detail                   | right reason
 own model + own files              | VERIFIED | VERIFIED | -                              | -                        | yes
 wrong public key                   | REJECTED | REJECTED | key id matches manifest        | manifest=bae58d20d2964be | yes
 wrong watermark key                | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 tampered manifest (developer_id)   | REJECTED | REJECTED | signature valid                | -                        | yes
 unmarked baseline model            | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 Mallory's model + OUR files        | REJECTED | REJECTED | watermark read (ecc rs32, 512  | decoder failed; min marg | yes
 our model + MALLORY's files        | REJECTED | REJECTED | watermark read (ecc rs16, 384  | decoder failed; min marg | yes
 Mallory's model + Mallory's files  | VERIFIED | VERIFIED | -                              | -                        | yes

DONE-WHEN (4 negative cases rejected, own model passes): PASSED
exit 0
```

### Waiting on Phase 4 (done 2026-10-26, see results above)

1. Verify each Stage B model (settings come from its final.json):
   `python -m verify.verify_model --model runs/wm_v1/<run name>/seed0/model.pt` (and seeds 1, 2; also the rep2 runs).
2. Real Mallory model in the Phase 4 config (Colab or local), using the existing trainer:
   `python -m training.train_watermarked --seed 0 --epochs 30 --lam <chosen> --n-bits 256 --ecc rs32 --layer <chosen> --key mallory/keys/watermark_key.bin --payload mallory/release/payload.hex --out-root mallory/runs`
3. Suite on Phase 4 models:
   `python -m experiments.phase5_negative_cases --seeds 0 1 2 --model-pattern "runs/wm_v1/<run name>/seed{seed}/model.pt" --mallory-model mallory/runs/<run name>/seed0/model.pt`
   Phase 5 is done when this prints `DONE-WHEN ... PASSED`.

**Code: `verify/verify_model.py` (new)**

```python
"""Phase 5: verify a MODEL against a signed release (runs LOCALLY, needs liboqs + torch).

    python -m verify.verify_model --model runs/wm_v0/lam1_n32/seed0/model.pt \
        --public-key keys/public_key.bin --wm-key keys/watermark_key.bin --release-dir release

Checks, in order. A failing stage stops the run, because later stages trust earlier ones:
  1. release   : files load, key id, algorithm, signature, payload.hex   (verify.verify_release)
  2. model     : architecture from the SIGNED manifest, weights load at the signed width,
                 parameter count == manifest model.num_params
  3. watermark : X @ v with the watermark key, then ECC decode
  4. payload   : decoded bits == first n_bits of SHA-256(signed manifest)
VERIFIED only if every check passes (a decoder saying "ok" is never enough on its own).
Exit code 0 = VERIFIED, 1 = REJECTED.

Watermark settings (ecc, n_bits, layer, mode) are not in the manifest (adding them would change
the payload of every trained model). They come from the command line, else from the final.json
next to the model, else the Phase 3 defaults; the source is printed.
"""
import argparse
import json
import sys
from pathlib import Path

from crypto.manifest import payload_bits
from verify.verify_release import verify_release

DEFAULTS = {"ecc": "none", "n_bits": 32, "layer": "features.6.0.weight", "mode": "mean"}


def resolve_settings(model_path, ecc=None, n_bits=None, layer=None, mode=None):
    """Return (settings dict, source text). CLI value > final.json next to the model > DEFAULTS."""
    given = {"ecc": ecc, "n_bits": n_bits, "layer": layer, "mode": mode}
    f = Path(model_path).parent / "final.json"
    try:
        run = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        run = {}
    settings, sources = {}, set()
    for k, default in DEFAULTS.items():
        if given[k] is not None:
            settings[k], src = given[k], "command line"
        elif k in run:
            settings[k], src = run[k], "final.json"
        else:
            settings[k], src = default, "defaults"
        sources.add(src)
    return settings, " + ".join(sorted(sources))


def verify_model(model_path, public_key_path, wm_key_path, release_dir,
                 ecc=None, n_bits=None, layer=None, mode=None):
    """Return (ok, checks, settings). checks = list of (name, passed, detail)."""
    settings, source = resolve_settings(model_path, ecc, n_bits, layer, mode)
    settings["source"] = source

    # 1. release: signature etc.
    ok, checks = verify_release(release_dir, public_key_path)
    if not ok:
        return False, checks, settings

    def add(name, passed, detail=""):
        checks.append((name, bool(passed), detail))
        return bool(passed)

    manifest = json.loads((Path(release_dir) / "signed_manifest.json").read_text())["manifest"]

    # 2. model
    try:
        import torch

        from embedding.extract import load_smallcnn

        arch, width = manifest["model"]["architecture"], int(manifest["model"]["width"])
        if not add("architecture is SmallCNN", arch == "SmallCNN", "manifest says %r" % arch):
            return False, checks, settings
        model = load_smallcnn(model_path, width)
        add("model loads at signed width %d" % width, True)
        n_params = sum(p.numel() for p in model.parameters())
        if not add("parameter count matches manifest", n_params == manifest["model"]["num_params"],
                   "model %d, manifest %d" % (n_params, manifest["model"]["num_params"])):
            return False, checks, settings
    except Exception as e:
        add("model loads at signed width", False, "%s: %s" % (type(e).__name__, e))
        return False, checks, settings

    # 3. watermark: extract + decode
    try:
        from embedding.ecc import get_code
        from embedding.keys import load_key
        from embedding.projection import ProjectionWatermark, get_weight

        if not 1 <= int(settings["n_bits"]) <= manifest["watermark"]["payload_bits"]:
            add("n_bits within signed payload size", False,
                "%s requested, manifest has %d" % (settings["n_bits"], manifest["watermark"]["payload_bits"]))
            return False, checks, settings
        code = get_code(settings["ecc"], int(settings["n_bits"]))
        wm = ProjectionWatermark(load_key(wm_key_path), settings["layer"], code.n_bits, settings["mode"],
                                 get_weight(model, settings["layer"]).shape)
        _, logits = wm.extract(model)
        margin = min(abs(z) for z in logits)
        d = code.decode(logits)
        if not add("watermark read (ecc %s, %d values)" % (settings["ecc"], code.n_bits), d["ok"],
                   "min margin %.2f, corrected %d, erasures %d" % (margin, d["corrected"], d["erasures"])
                   if d["ok"] else "decoder failed; min margin %.2f" % margin):
            return False, checks, settings
    except Exception as e:
        add("watermark extracted", False, "%s: %s" % (type(e).__name__, e))
        return False, checks, settings

    # 4. payload: compare with the SIGNED manifest, never with payload.hex
    expected = payload_bits(manifest, int(settings["n_bits"]))
    wrong = sum(int(a != b) for a, b in zip(d["bits"], expected))
    add("extracted payload == SHA-256(signed manifest)", wrong == 0,
        "%d bits match" % len(expected) if wrong == 0 else "%d of %d bits differ" % (wrong, len(expected)))
    return all(c[1] for c in checks), checks, settings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--public-key", default="keys/public_key.bin")
    ap.add_argument("--wm-key", default="keys/watermark_key.bin")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--ecc", default=None)
    ap.add_argument("--n-bits", type=int, default=None)
    ap.add_argument("--layer", default=None)
    ap.add_argument("--mode", default=None)
    args = ap.parse_args()

    ok, checks, s = verify_model(args.model, args.public_key, args.wm_key, args.release_dir,
                                 args.ecc, args.n_bits, args.layer, args.mode)
    print("watermark settings (%s): ecc %s | n_bits %s | layer %s | mode %s"
          % (s["source"], s["ecc"], s["n_bits"], s["layer"], s["mode"]))
    for name, passed, detail in checks:
        print("%s  %s%s" % ("PASS" if passed else "FAIL", name, "  (" + detail + ")" if detail else ""))
    print("VERIFIED" if ok else "REJECTED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

**Code: `experiments/phase5_make_mallory.py` (new)**

```python
"""Phase 5: create a SECOND developer, "Mallory", for the negative-case tests (runs LOCALLY, needs liboqs).

    python -m experiments.phase5_make_mallory

Writes mallory/keys/ (ML-DSA-65 key pair + watermark key, git-ignored) and mallory/release/
(signed manifest, payload.hex, public key), with the same layout as our own keys/ and release/.
Mallory claims the same public CIFAR-10 dataset, so the Merkle root is copied from our signed
manifest (pass --cifar-root to hash the dataset instead). Refuses to overwrite without --force.
"""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from crypto.dataset import cifar10_train_root
from crypto.manifest import bits_to_hex, build_manifest, canonical_bytes, payload_bits
from crypto.signing import ALG, generate_keys, key_id, sign
from embedding.keys import key_fingerprint
from experiments.phase2_make_release import count_params


def write_release(rel_dir, manifest, secret_key, public_key):
    """Sign `manifest` and write signed_manifest.json, payload.hex, public_key.bin (Phase 2 layout)."""
    rel_dir = Path(rel_dir)
    rel_dir.mkdir(parents=True, exist_ok=True)
    signed = {"format": "pq-signed-manifest-v1", "algorithm": ALG, "manifest": manifest,
              "signature_hex": sign(secret_key, canonical_bytes(manifest)).hex()}
    (rel_dir / "signed_manifest.json").write_text(json.dumps(signed, indent=2, sort_keys=True))
    (rel_dir / "payload.hex").write_text(bits_to_hex(payload_bits(manifest)) + "\n")
    (rel_dir / "public_key.bin").write_bytes(public_key)
    return signed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--developer-id", default="Mallory")
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--payload-bits", type=int, default=256)
    ap.add_argument("--our-release", default="release", help="Merkle root is copied from here")
    ap.add_argument("--cifar-root", default=None, help="hash CIFAR-10 here instead of copying the root")
    ap.add_argument("--out", default="mallory")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    keys_dir, rel_dir = Path(args.out) / "keys", Path(args.out) / "release"
    if (rel_dir / "signed_manifest.json").exists() and not args.force:
        sys.exit("%s exists. Re-running gives Mallory new keys and a new payload, so any Mallory model "
                 "trained on the old ones stops verifying. Use --force only if you mean it." % rel_dir)

    pk, sk = generate_keys()
    wm_key = secrets.token_bytes(32)
    keys_dir.mkdir(parents=True, exist_ok=True)
    (keys_dir / "public_key.bin").write_bytes(pk)
    (keys_dir / "secret_key.bin").write_bytes(sk)
    (keys_dir / "watermark_key.bin").write_bytes(wm_key)
    os.chmod(keys_dir / "secret_key.bin", 0o600)
    os.chmod(keys_dir / "watermark_key.bin", 0o600)

    if args.cifar_root:
        root = cifar10_train_root(args.cifar_root).hex()
    else:
        root = json.loads((Path(args.our_release) / "signed_manifest.json").read_text())["manifest"]["dataset"]["merkle_root_sha256"]

    manifest = build_manifest(args.developer_id, key_id(pk), root, 50000, args.width,
                              count_params(args.width), args.payload_bits)
    write_release(rel_dir, manifest, sk, pk)
    print("developer id : %s" % args.developer_id)
    print("key id       : %s" % key_id(pk))
    print("wm key       : fingerprint %s" % key_fingerprint(wm_key))
    print("merkle root  : %s (%s)" % (root, "hashed" if args.cifar_root else "copied from " + args.our_release))
    print("payload      : %s" % bits_to_hex(payload_bits(manifest)))
    print("wrote        : %s (git-ignored) and %s" % (keys_dir, rel_dir))


if __name__ == "__main__":
    main()
```

**Code: `experiments/phase5_mallory_standin.py` (new)**

```python
"""Phase 5: a cheap STAND-IN Mallory model for the negative-case suite (runs LOCALLY on CPU, ~2 to 5 min).

    python -m experiments.phase5_mallory_standin --data-root data

Fine-tunes OUR baseline seed 1 for one epoch with CE + lam * BCE, embedding Mallory's payload with
Mallory's watermark key (Phase 3 style: ecc none, 32 bits, features.6.0.weight, mean). It stands
for "a model watermarked by someone else". The real Mallory model is trained in the Phase 4
config once Phase 4 is finished (train_watermarked.py with --key/--payload pointing at mallory/).
"""
import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from embedding.ecc import get_code
from embedding.extract import load_smallcnn
from embedding.keys import key_fingerprint, load_key, load_payload_bits
from embedding.projection import ProjectionWatermark, get_weight
from training.seed import set_seed
from training.train_watermarked import evaluate, make_loaders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="runs/baseline/seed1/model.pt")
    ap.add_argument("--key", default="mallory/keys/watermark_key.bin")
    ap.add_argument("--payload", default="mallory/release/payload.hex")
    ap.add_argument("--data-root", default="data")
    ap.add_argument("--lam", type=float, default=5.0)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--n-bits", type=int, default=32)
    ap.add_argument("--ecc", default="none")
    ap.add_argument("--layer", default="features.6.0.weight")
    ap.add_argument("--mode", default="mean")
    ap.add_argument("--out", default="mallory/runs/standin_lam5_n32/seed1")
    args = ap.parse_args()

    set_seed(1)
    key = load_key(args.key)
    payload = load_payload_bits(args.payload, args.n_bits)
    code = get_code(args.ecc, args.n_bits)
    codeword = code.encode(payload)
    target = torch.tensor(codeword, dtype=torch.float32)
    model = load_smallcnn(args.start)
    wm = ProjectionWatermark(key, args.layer, code.n_bits, args.mode, get_weight(model, args.layer).shape)
    train_loader, test_loader = make_loaders(args.data_root, 128)
    opt = torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, nesterov=True, weight_decay=5e-4)

    t0 = time.time()
    model.train()
    for x, y in train_loader:
        loss = F.cross_entropy(model(x), y) + args.lam * wm.loss(model, target)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    acc = evaluate(model, test_loader, "cpu")
    got, logits = wm.extract(model)
    errors = sum(int(a != b) for a, b in zip(got, codeword))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")
    final = {"STAND_IN": True,
             "note": "Mallory stand-in: our baseline seed1 fine-tuned 1 epoch with Mallory's key and payload. "
                     "Not a from-scratch model; for the Phase 5 negative-case suite only.",
             "start": args.start, "epochs": 1, "lam": args.lam, "lr": args.lr, "n_bits": args.n_bits,
             "ecc": args.ecc, "codeword_bits": code.n_bits, "layer": args.layer, "mode": args.mode, "width": 32,
             "final_test_acc": acc, "bit_errors": errors, "min_abs_logit": min(abs(z) for z in logits),
             "key_fingerprint": key_fingerprint(key), "seconds": time.time() - t0}
    (out / "final.json").write_text(json.dumps(final, indent=2))
    print("acc %.4f | bit errors %d/%d | min|logit| %.2f | %.0f s | saved %s"
          % (acc, errors, code.n_bits, final["min_abs_logit"], final["seconds"], out))


if __name__ == "__main__":
    main()
```

**Code: `experiments/phase5_negative_cases.py` (new)**

```python
"""Phase 5 'done when' check (runs LOCALLY, needs liboqs): each negative case must be REJECTED for the
right reason, and both our own model and Mallory's own model must be VERIFIED.

    python -m experiments.phase5_negative_cases --seeds 0 1 2                    # Phase 3 models (now)
    python -m experiments.phase5_negative_cases --seeds 0 1 2 \
        --model-pattern "runs/wm_v1/<run name>/seed{seed}/model.pt" \
        --mallory-model mallory/runs/<run name>/seed0/model.pt                   # Phase 4 models (later)

Tampered copies, wrong keys etc. live in a temporary folder; nothing is written to release/ or runs/.
"""
import argparse
import json
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

from crypto.signing import generate_keys
from verify.verify_model import resolve_settings, verify_model

NO_WATERMARK = ("watermark read", "extracted payload")   # failing here = "this watermark is not in the model"


def first_failure(checks):
    for name, passed, detail in checks:
        if not passed:
            return name, detail
    return None, ""


def run_cases(seed, args, tmp):
    ours = args.model_pattern.format(seed=seed)
    base = args.baseline_pattern.format(seed=seed)
    m_dir = Path(args.mallory_dir)
    mine = dict(public_key_path=args.public_key, wm_key_path=args.wm_key, release_dir=args.release_dir)
    mallory = dict(public_key_path=m_dir / "keys" / "public_key.bin", wm_key_path=m_dir / "keys" / "watermark_key.bin",
                   release_dir=m_dir / "release")
    s, _ = resolve_settings(ours, args.ecc, args.n_bits)          # our settings, also used for the baseline
    ours_s = {k: s[k] for k in ("ecc", "n_bits", "layer", "mode")}

    wrong_pk = tmp / "wrong_public_key.bin"
    wrong_pk.write_bytes(generate_keys()[0])
    wrong_wm = tmp / "wrong_watermark_key.bin"
    wrong_wm.write_bytes(secrets.token_bytes(32))
    tampered = tmp / "tampered_release"
    if not tampered.exists():
        shutil.copytree(args.release_dir, tampered)
        p = tampered / "signed_manifest.json"
        d = json.loads(p.read_text())
        d["manifest"]["developer_id"] = "mallory"
        p.write_text(json.dumps(d, indent=2, sort_keys=True))

    cases = [  # (name, model, files, settings, expected verdict, acceptable failing checks)
        ("own model + own files", ours, mine, ours_s, True, None),
        ("wrong public key", ours, dict(mine, public_key_path=wrong_pk), ours_s, False, ("key id matches manifest",)),
        ("wrong watermark key", ours, dict(mine, wm_key_path=wrong_wm), ours_s, False, NO_WATERMARK),
        ("tampered manifest (developer_id)", ours, dict(mine, release_dir=tampered), ours_s, False, ("signature valid",)),
        ("unmarked baseline model", base, mine, ours_s, False, NO_WATERMARK),
        ("Mallory's model + OUR files", args.mallory_model, mine, {}, False, NO_WATERMARK),
        ("our model + MALLORY's files", ours, mallory, ours_s, False, NO_WATERMARK),
        ("Mallory's model + Mallory's files", args.mallory_model, mallory, {}, True, None),
    ]
    rows = []
    for name, model, files, settings, expect_ok, reasons in cases:
        ok, checks, _ = verify_model(model, ecc=settings.get("ecc"), n_bits=settings.get("n_bits"),
                                     layer=settings.get("layer"), mode=settings.get("mode"), **files)
        fail, detail = first_failure(checks)
        right = (ok == expect_ok) and (reasons is None or any(fail.startswith(r) for r in reasons))
        rows.append((name, expect_ok, ok, fail, detail, right))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--model-pattern", default="runs/wm_v0/lam1_n32/seed{seed}/model.pt")
    ap.add_argument("--baseline-pattern", default="runs/baseline/seed{seed}/model.pt")
    ap.add_argument("--mallory-dir", default="mallory")
    ap.add_argument("--mallory-model", default="mallory/runs/standin_lam5_n32/seed1/model.pt")
    ap.add_argument("--public-key", default="keys/public_key.bin")
    ap.add_argument("--wm-key", default="keys/watermark_key.bin")
    ap.add_argument("--release-dir", default="release")
    ap.add_argument("--ecc", default=None)
    ap.add_argument("--n-bits", type=int, default=None)
    args = ap.parse_args()

    all_right = True
    with tempfile.TemporaryDirectory() as t:
        for seed in args.seeds:
            rows = run_cases(seed, args, Path(t))
            print("\nseed %d  (our model: %s)" % (seed, args.model_pattern.format(seed=seed)))
            print(" %-34s | %-8s | %-8s | %-30s | %-24s | right reason"
                  % ("case", "expected", "got", "first failing check", "detail"))
            for name, expect_ok, ok, fail, detail, right in rows:
                print(" %-34s | %-8s | %-8s | %-30s | %-24s | %s" % (
                    name, "VERIFIED" if expect_ok else "REJECTED", "VERIFIED" if ok else "REJECTED",
                    "-" if fail is None else fail[:30], (detail or "-")[:24], "yes" if right else "NO"))
                all_right &= right
    print("\nDONE-WHEN (4 negative cases rejected, own model passes): %s" % ("PASSED" if all_right else "FAILED"))
    sys.exit(0 if all_right else 1)


if __name__ == "__main__":
    main()
```

**Code: `tests/test_phase5.py` (new)**

```python
"""Run from the project root:  python -m pytest tests/test_phase5.py -v   (expect 8 passed)

Self-contained: temporary ML-DSA keys, releases and small watermarked models; nothing in keys/,
release/ or runs/ is used or changed.
"""
import json
import secrets
import shutil

import pytest

pytest.importorskip("oqs")
torch = pytest.importorskip("torch")

from crypto.manifest import build_manifest, payload_bits  # noqa: E402
from crypto.signing import generate_keys, key_id  # noqa: E402
from embedding.ecc import get_code  # noqa: E402
from embedding.projection import ProjectionWatermark, get_weight  # noqa: E402
from experiments.phase5_make_mallory import write_release  # noqa: E402
from training.model import SmallCNN  # noqa: E402
from verify.verify_model import verify_model  # noqa: E402

LAYER = "features.6.0.weight"


def first_failure(checks):
    return next((name for name, passed, _ in checks if not passed), None)


def make_developer(root, name, width, ecc, n_bits, marked=True):
    """Keys + signed release + a model carrying this developer's payload (watermark-only optimisation)."""
    root.mkdir(parents=True)
    pk, sk = generate_keys()
    (root / "public_key.bin").write_bytes(pk)
    wm_key = secrets.token_bytes(32)
    (root / "watermark_key.bin").write_bytes(wm_key)
    torch.manual_seed(0)
    model = SmallCNN(width=width)
    manifest = build_manifest(name, key_id(pk), "00" * 32, 50000, width,
                              sum(p.numel() for p in model.parameters()), 256, created_utc="2026-10-26T00:00:00Z")
    write_release(root / "release", manifest, sk, pk)
    if marked:
        code = get_code(ecc, n_bits)
        target = torch.tensor(code.encode(payload_bits(manifest, n_bits)), dtype=torch.float32)
        wm = ProjectionWatermark(wm_key, LAYER, code.n_bits, "mean", get_weight(model, LAYER).shape)
        opt = torch.optim.SGD([get_weight(model, LAYER)], lr=5.0)
        for _ in range(300):
            opt.zero_grad()
            wm.loss(model, target).backward()
            opt.step()
    (root / "model").mkdir()
    torch.save(model.state_dict(), root / "model" / "model.pt")
    (root / "model" / "final.json").write_text(json.dumps({"ecc": ecc, "n_bits": n_bits, "layer": LAYER, "mode": "mean"}))
    return dict(model_path=root / "model" / "model.pt", public_key_path=root / "public_key.bin",
                wm_key_path=root / "watermark_key.bin", release_dir=root / "release")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    t = tmp_path_factory.mktemp("phase5")
    return {"t": t,
            "dev": make_developer(t / "dev", "dev", 8, "none", 32),
            "other": make_developer(t / "other", "Mallory", 8, "none", 32),
            "rs": make_developer(t / "rs", "dev", 32, "rs32", 256),
            "unmarked": make_developer(t / "unmarked", "dev", 8, "none", 32, marked=False)}


def test_own_model_verified(world):
    ok, checks, s = verify_model(**world["dev"])
    assert ok and first_failure(checks) is None and s["source"] == "final.json"


def test_own_model_verified_rs32_full_payload(world):
    ok, checks, _ = verify_model(**world["rs"])
    assert ok, checks


def test_wrong_public_key_rejected(world):
    ok, checks, _ = verify_model(**dict(world["dev"], public_key_path=world["other"]["public_key_path"]))
    assert not ok and first_failure(checks) == "key id matches manifest"


def test_wrong_watermark_key_rejected(world):
    ok, checks, _ = verify_model(**dict(world["dev"], wm_key_path=world["other"]["wm_key_path"]))
    assert not ok and first_failure(checks).startswith("extracted payload")


def test_tampered_manifest_rejected(world):
    rel = world["t"] / "tampered"
    shutil.copytree(world["dev"]["release_dir"], rel)
    d = json.loads((rel / "signed_manifest.json").read_text())
    d["manifest"]["developer_id"] = "mallory"
    (rel / "signed_manifest.json").write_text(json.dumps(d))
    ok, checks, _ = verify_model(**dict(world["dev"], release_dir=rel))
    assert not ok and first_failure(checks) == "signature valid"


def test_unmarked_model_rejected(world):
    files = dict(world["dev"], model_path=world["unmarked"]["model_path"])
    ok, checks, _ = verify_model(**files)
    assert not ok and first_failure(checks).startswith("extracted payload")


def test_someone_elses_model(world):
    dev, other = world["dev"], world["other"]
    ok, checks, _ = verify_model(**dict(dev, model_path=other["model_path"]))       # their model, our files
    assert not ok and first_failure(checks).startswith("extracted payload")
    ok, checks, _ = verify_model(**dict(other, model_path=dev["model_path"]))       # our model, their files
    assert not ok and first_failure(checks).startswith("extracted payload")
    assert verify_model(**other)[0]                                                 # their model, their files


def test_garbage_inputs_never_crash(world):
    t, dev = world["t"], world["dev"]
    junk = t / "junk.pt"
    junk.write_bytes(secrets.token_bytes(1000))
    wide = t / "wide.pt"
    torch.save(SmallCNN(width=16).state_dict(), wide)
    cut = t / "cut_signature"
    shutil.copytree(dev["release_dir"], cut)
    d = json.loads((cut / "signed_manifest.json").read_text())
    d["signature_hex"] = d["signature_hex"][:100]
    (cut / "signed_manifest.json").write_text(json.dumps(d))
    cases = [dict(dev, model_path=junk), dict(dev, model_path=t / "missing.pt"), dict(dev, model_path=wide),
             dict(dev, release_dir=cut), dict(dev, wm_key_path=t / "missing.bin"),
             dict(dev, release_dir=t / "no_release"), dict(dev, n_bits=300), dict(dev, layer="no.such.weight"),
             dict(dev, ecc="bch")]
    for files in cases:
        ok, checks, _ = verify_model(**files)
        assert not ok and first_failure(checks) is not None, files
```

**Change: `.gitignore`**

```diff
diff --git a/.gitignore b/.gitignore
index efbabbb..b129cce 100644
--- a/.gitignore
+++ b/.gitignore
@@ -2,6 +2,7 @@ venv/
 __pycache__/
 data/
 keys/
+mallory/keys/
 .ipynb_checkpoints/
 .env
 .env.*
```

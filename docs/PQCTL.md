# pqctl: the project control centre

One tool to run every phase (0 to 6), watch the output live and read the results, either as a
**web dashboard** or in the **terminal**. It runs the project's own scripts (the same commands that are in
`docs/phase_commands.md`), so the results are identical to running them by hand.

- Standard library only: nothing extra to install.
- Runs on Windows, Linux (Fedora, Ubuntu, WSL) and macOS. The lab tools need the same packages as the phases they use (PyTorch, liboqs-python).
- Local only: the dashboard listens on `127.0.0.1` and refuses requests from other sites.
- It never touches `keys/` except through the project's own key scripts, and only after you confirm.

## Start it

Run from the project root, with the **venv's Python** (tasks run with the Python that starts pqctl):

```bash
# Linux / WSL / macOS
source venv/bin/activate
python -m pqctl serve            # opens http://127.0.0.1:8765 in your browser
```

```powershell
# Windows (PowerShell)
venv\Scripts\python -m pqctl serve
```

Stop it with Ctrl+C (running jobs are cancelled). Use `--port 9000` for another port and `--no-browser` to not
open a browser.

## The dashboard

The left menu has three parts: **Home**, **Labs** and **Test model**; then **Phases 0 to 7**; then **Results and charts**, **Jobs** and **Environment**. The terminal is open on the right side by default.

| Page | What it does |
|---|---|
| Home | Headline numbers, the results charts, every phase's status and the three pipelines |
| Labs | One page with a tab for every interactive tool (below) |
| Test model | 11 live tests with their expected results (signature, tampering, our model, unsigned model, Mallory's model, attacked copies that should still verify, the two known weaknesses), each with a Run button, plus **Run all tests** and a readiness checklist |
| Phase 0 to 7 | Each step of that phase with its options, the exact command it will run, a **Run** button and a **Colab cell** button |
| Jobs | Everything run in this session; click one to see its log |
| Environment | What is installed, which keys and data are present, and the exact fix for anything missing. Settings: CIFAR-10 folder and the Python used for tasks |

**The Labs tabs** (each runs this project's own code)

| Tab | What it does | Project code it uses |
|---|---|---|
| Verify a model | Pick any model, get VERIFIED / REJECTED and every check | `verify/verify_model.py` |
| Watermark X-ray | The 576 carrier numbers, the 512 scores, every code value before repair, the Reed-Solomon repair and the 256 payload bits against the signed record. Read with our key, Mallory's key or a random key | `pqctl/actions/xray.py` → `embedding/projection.py`, `embedding/ecc.py`, `crypto/manifest.py` |
| Attack lab | Pick an attack and a strength; attacks a copy (saved in `.pqctl/lab/`), verifies it, shows flipped bits and optionally accuracy, next to what Phase 6 measured for the same setting | `pqctl/actions/attack_lab.py` → `attacks/make_attacked.py`, `verify/verify_model.py` |
| Tamper lab | Edit the developer, width, number of images, the dataset root, signature or payload, or use a wrong key; the fingerprint change is shown live, then a temporary copy is verified | `pqctl/actions/tamper_lab.py` → `verify/verify_release.py`, `verify/verify_model.py` |
| Signing lab | ML-DSA-65 on any text with a throwaway key pair; sizes and timings compared with RSA and elliptic curves | `pqctl/actions/sign_lab.py` → `crypto/signing.py` |
| Hash and Merkle | SHA-256 and a live 8-leaf Merkle tree in the browser, next to the project's real Merkle root | browser only; reads `release/signed_manifest.json` |
| Release and keys | The signed manifest, the exact signed bytes, payload, signature and key sizes, key id and payload checks, watermark key fingerprints, Mallory's release, the 16 frozen model hashes | `release/`, `mallory/release/`, `keys/`, `docs/phase5_model_hashes.txt` |
| Results and charts | Charts (accuracy vs attack strength, every ECC setting, every attack type by outcome), Phase 7 tables and plots, the Phase 6 table and plots, Phase 4, baselines and the docs | `results/phase6/`, `results/phase7/`, `runs/` |

The terminal on the right is open by default (on screens at least 1100 px wide) and follows whatever is running. It shows the live log of the running job (progress bars included), its result,
and a Cancel button. **Full screen** (or the F key) fills the whole screen with the terminal, which is the view to use on a
projector; Esc leaves full screen, a second Esc hides the panel; the **Terminal** button in the top bar shows it again (the choice is remembered). A− / A+ (or − / +) change the text size and Wrap (W)
switches line wrapping; both are remembered by your browser. Jobs run **one at a time, in order** (quick clicks from the Demo, Verify and phase pages go to the front of the queue); pipelines queue their steps and the panel follows
them. A pipeline marked "stop on failure" skips the remaining steps after a failure.

## The terminal

```bash
python -m pqctl                          # interactive menu: pick a phase, a step, edit options, run
python -m pqctl status                   # phase board
python -m pqctl doctor                   # environment check with fixes
python -m pqctl list                     # every step id (or: list --phase 6)
python -m pqctl run p5.verify --set model=runs/wm_v1/lam20_n256_rs16/seed2/model.pt
python -m pqctl run p4.noise --set trials=5 --set data_root=data
python -m pqctl pipeline check-all       # every check, about 5 minutes
python -m pqctl pipeline phase6          # the whole local Phase 6 run
python -m pqctl colab p4.train --set lams="5 20"   # print a Colab cell for a GPU step
python -m pqctl history                  # last result of every step
python -m pqctl run lab.xray --set model=runs/baseline/seed0/model.pt      # the X-ray, as text
python -m pqctl run lab.attack --set attack=prune_global --set strength=0.5
python -m pqctl run lab.tamper --set developer_id=Mallory
```

Exit code is 0 only if everything passed, so it also works in scripts and CI.

## Pipelines

| id | Steps | Time |
|---|---|---|
| `check-all` | ML-DSA test, all unit tests, release signature, tamper demo, Phase 3 check, Phase 3 legacy verify, every Phase 4 model, one verify, negative cases, Phase 6 compat, Phase 6 tables, Phase 7 collect + plots | ~5 min, nothing trained; only results/ tables and plots are rewritten |
| `phase6` | compat, weight attacks, control attacks, verify every attacked model, tables | ~2 h on CPU, skips finished work |
| `rebuild` | trains baselines, Phase 3 and 4 models, Mallory's stand-in, every attack (training ones too), then the checks | many hours on CPU; use Colab cells for the training steps |

## Steps that need a GPU

Training steps (`p1.train`, `p3.train`, `p4.train`, `p6.train`) are marked **GPU recommended**. You can run them
locally, but on a CPU they take hours. Their **Colab cell** button gives a ready cell for a T4 runtime with the
project in `My Drive/pq-watermark` (upload `keys/watermark_key.bin` with `files.upload()` first, as before).

## Safety rules built in

- Only the steps defined in `pqctl/tasks.py` can run; there is no free-form command box.
- Model paths must stay inside the project. Files under `keys/` are never served to the browser.
- Steps that overwrite keys or the release (`p2.make_release`, `p3.make_key`, `p5.make_mallory` with Force) need
  you to type `OVERWRITE` (dashboard) or confirm in the terminal. They are never part of a pipeline.
- Every POST needs a random token that only the dashboard page has, and requests from other origins are refused.

## Where things are saved

`.pqctl/` in the project (git-ignored by its own `.gitignore`): `settings.json`, `history.json` (last result per
step), `logs/<job>.log` (full output of every job) and `lab/` (models made by the attack lab; delete any time).

## Adding a step

Add a dict to `TASKS` in `pqctl/tasks.py` (id, phase, title, what, est, where, needs, argv, params). It appears in
the dashboard, the menu and `list` automatically. `tests/test_pqctl.py` checks that every step builds a command.

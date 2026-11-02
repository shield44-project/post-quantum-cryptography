# Work log: audit, fixes, README and Phase 6b (2026-10-29 to 2026-11-03)

A complete record of the work done with Claude Code on branch `phase6`: every finding, every change, every command
and the outputs that prove it. Four parts, in the order the work happened:

1. [Audit and bug fixes](#1-audit-and-bug-fixes-2026-10-29-committed-as-1257a2c) (committed by shield44 as `1257a2c`)
2. [Dashboard broken-pipe fix](#2-dashboard-broken-pipe-traceback-2026-10-30-in-1257a2c) (in `1257a2c`)
3. [README](#3-readme-2026-10-30-to-2026-11-02-committed-as-6017760) (committed as `6017760`, then edited again in part 4)
4. [Phase 6b: closing the removal attacks](#4-phase-6b-closing-the-removal-attacks-2026-11-03-uncommitted) (uncommitted when this log was written)

Then: [research-paper assessment](#5-research-paper-assessment-2026-11-02), [known issues still open](#6-known-issues-still-open), and [how to reproduce everything](#7-how-to-reproduce-everything).

---

## 1. Audit and bug fixes (2026-10-29, committed as `1257a2c`)

### 1.1 How the audit was done

- Read every source file: `crypto/`, `embedding/`, `training/`, `verify/`, `attacks/`, `experiments/`, `pqctl/`
  (Python, `app.js`, `labs.js`, `index.html`, `app.css`), the tests and the docs.
- Ran the test suite, started the dashboard and probed every API endpoint, ran every lab tool through the API,
  and ran the full `check-all` pipeline before and after the fixes.

Baseline before any change:

```text
$ pytest                      # bare pytest
ERROR experiments/phase4_noise_test.py::test_accuracy   fixture 'model' not found
1 error in 7.55s

$ python -m pytest -q tests
56 passed in 13.84s

$ python -m pqctl pipeline check-all     # 13 steps, all passed, 83 s
```

Dashboard security probes (all correct before and after):

```text
/api/file?path=keys/watermark_key.bin          404   (keys never served)
/api/file?path=mallory/keys/public_key.bin     404
/api/file?path=../../etc/passwd                404   (path traversal blocked)
/static/../server.py                           404
Host: evil.com                                 403
POST /api/run without token                    403
```

### 1.2 Bugs found and fixed

| # | Severity | Where | Problem | Fix |
|---|---|---|---|---|
| 1 | **Security** | `embedding/extract.py`, `attacks/common.py` | If a model file failed the safe tensor-only load, the loader retried with `torch.load(weights_only=False)`: a full unpickle. The verifier exists to check models from people you do not trust (Mallory), so a crafted `.pt` file could run code on the auditor's machine. | Plain tensors only. A file that needs a full unpickle raises `ValueError("... refusing to unpickle it, since that can run code")` and the verifier reports REJECTED. `allow_pickle=True` exists for files you made yourself. |
| 2 | High | `pqctl/runner.py` | A multi-step job's exit code was only the **last** step's, so if step 1 of 3 failed and step 3 passed, the job showed PASSED. | Track the first non-zero exit code of any step (`worst`). |
| 3 | High | Attack lab (`pqctl/actions/attack_lab.py`), `attacks/weight_attacks.py` | "Compress" at strength 1 meant 1-bit quantization: `qmax = 0`, scale = max/0, and the saved model had NaN in 6 tensors. The verifier only rejected it by accident (NaN scores read as bit 0). | `quantize()` refuses fewer than 2 bits. The lab checks every attack's strength against a valid range (`LIMITS`) and reports the reason to the dashboard. |
| 4 | High | `verify/verify_model.py` | No explicit check for NaN or inf weights. | New check `weights are finite numbers`. |
| 5 | Medium | `pqctl/static/labs.js` | Attack lab: `setAttack` set `S.attackId = a.id` *before* testing `S.attackId === a.id`, so the strength of the previous attack carried over (4 bits from "Compress" became 95% pruning after clamping). | Strength remembered per attack (`S.attackStrengths[id]`). |
| 6 | Medium | `labs.js` (Phase 7 tab) | "Collect runs" never refreshed the table; "Make plots" reloaded the whole page and wiped its own result. | Run, reload results, redraw the tab, keep the result card on top. |
| 7 | Medium | `labs.js`, `app.js` | X-ray, Attack lab, Signing lab, Test-model and Verify pages: a failed request left the spinner running forever. | Errors replace the spinner with a red card. |
| 8 | Medium | `pqctl/server.py`, `pqctl/tasks.py` | Malformed requests returned 500: bad JSON in `/api/colab`, `since=abc`, a JSON list as the POST body or as `params`. | Clean 400 errors. `clean_params` rejects a non-object. |
| 9 | Medium | `pqctl/tasks.py` | Tamper lab width and image count, and the verify page's bit count, were free text passed to argparse, so `width=abc` crashed the tool. | Typed as `int`; a bad value gets a readable 400 error. |
| 10 | Low | `pqctl/__main__.py` | Interactive menu: typing `no` for "Force" on a dangerous task was treated as yes (any non-empty string), so the run was aborted as "not confirmed". `colab` with bad options printed a traceback. | Uses the runner's `_wants_force()`; `colab` catches `ParamError`. |
| 11 | Low | repo root | A bare `pytest` collected `experiments/phase4_noise_test.py` (its name matches `*_test.py`) and errored on its `test_accuracy` function. | `pytest.ini` with `testpaths = tests` and `pythonpath = .`; the function was renamed `measure_accuracy`. |
| 12 | Low | `pqctl/state.py` | Phase board: division by zero if every baseline `final.json` lacked an accuracy. | Guarded. |
| 13 | Low | `pqctl/tasks.py`, `docs/PQCTL.md` | "Expect 42 passed" was out of date; `check-all` claimed "nothing overwritten" but rewrites the results tables and plots. | Wording corrected. |

### 1.3 Features added

- `verify_model --json`: one JSON object with verdict, settings and every check. liboqs prints a banner to stdout on
  import, so everything printed during verification is redirected to stderr to keep stdout pure JSON.
- The finite-weights check and the attack-lab strength limits above.

### 1.4 Tests added (56 → 63)

`test_quantize_refuses_one_bit`, `test_nan_weights_rejected`, `test_pickled_module_is_never_unpickled`,
`test_json_output`, `test_a_failed_step_fails_the_whole_job`, `test_options_must_be_an_object`,
`test_attack_lab_strength_limits`.

### 1.5 Outputs after the fixes

```text
$ pytest
63 passed in 17.30s

$ python -m pqctl pipeline check-all
── summary · 65s ──
  p0.mldsa passed signature OK     tests.all passed 63 passed     p2.verify_release passed VERIFIED
  p2.tamper passed PASSED          p3.check passed PASSED         p3.verify_legacy passed VERIFIED
  p4.verify_all passed all 8 VERIFIED   p5.verify passed VERIFIED  p5.negative passed PASSED
  p6.compat passed PASSED          p6.summarize passed            p7.collect passed   p7.plots passed

Dashboard re-probe:
colab with params=notjson       400 {"error": "params must be JSON"}
POST /api/run with [1,2]        400 {"error": "body must be a JSON object"}
lab.sign with params ["x"]      400 {"error": "options must be a name -> value object"}
lab.tamper width=abc            400 {"error": "Model width: invalid literal for int() with base 10: 'abc'"}
lab.attack quantize strength 1  failed {'error': 'strength 1 is out of range for quantize: use 2 to 16'}
lab.tamper width=64             passed REJECTED [{'what': 'model.width', 'old': '32', 'new': '64'}]
```

Note: `check-all` regenerated four Phase 7 result files (`results/phase7/ecc_under_attack.csv` and three plots). The
only differences were last-digit float rounding and re-rendered PNGs (another matplotlib version); no result changed.
They went into `1257a2c`.

---

## 2. Dashboard broken-pipe traceback (2026-10-30, in `1257a2c`)

**Symptom** (from the terminal running `python -m pqctl serve`):

```text
BrokenPipeError: [Errno 32] Broken pipe
During handling of the above exception, another exception occurred:
  ... self._send(500, ...) ... BrokenPipeError: [Errno 32] Broken pipe
```

**Cause:** the page polls every ~0.5 s. A reload, a tab switch or a cancelled poll closes the connection while the
server is still writing. The server treated that as a crash, tried to send a 500 error on the same dead socket, failed
again, and Python printed both.

**Fix:** `_send` in `pqctl/server.py` catches `BrokenPipeError`, `ConnectionResetError` and `ConnectionAbortedError`
and closes the connection quietly.

**Proof:** 40 requests that reset the connection immediately (like closing a tab):

```text
still serving: 200
tracebacks in log: 0
tests/test_pqctl.py: 17 passed
```

---

## 3. README (2026-10-30 to 2026-11-02, committed as `6017760`)

- New `README.md`: tagline and badges, at-a-glance table, why it exists, a Mermaid diagram of the whole pipeline,
  measured results (accuracy cost, robustness table, totals, plot gallery, signature-size comparison), quick start
  with a real verifier transcript, the pqctl dashboard, negative cases, honest limitations, repository layout,
  roadmap, tests, team, references.
- Every number came from `runs/`, `results/` and `docs/`. The verifier transcript was copied from a real run
  (margin 2.25, key id `bae58d20…`). All links to `docs/` and `results/` were checked to exist.
- 2026-11-02: decorative emojis removed. ✅ and ❌ were kept only where they carry meaning (held/removed,
  VERIFIED/REJECTED, done). Heading anchors changed with the emojis, so navigation and badge links were updated.
- 2026-11-03 (part 4): results, limitations, roadmap and test counts updated for Phase 6b.

`git fetch --all --prune` on 2026-11-02: `phase6` equal to `origin/phase6` (0 ahead, 0 behind). `origin/phase4-5`'s 22
"missing" commits were all already in `phase6` as patch-equivalent copies (`git cherry`); the one unmatched commit added
baseline models that are byte-identical in `phase6`. `pq-watermark` (the GitHub default branch) is far behind `phase6`;
no PR was opened, at your request.

---

## 4. Phase 6b: closing the removal attacks (2026-11-03, uncommitted)

### 4.1 What broke through in Phase 6

A removal counts only if the verdict is not a pass **and** the model is still useful (accuracy within 5 points of the
clean model). Of the 43 attacks, four attack types succeeded:

| Attack | Runs removed | Accuracy cost | Why it worked |
|---|---|---|---|
| `permute_in_carrier` | 9 / 9 | 0.00 | Reordering the channels feeding the carrier conv (and the previous block to match) keeps the function identical but reorders the 64 nine-number blocks of the carrier vector `v`, so `X·v` is random (agreement with our code ≈ 50%). |
| `permute_all` | 9 / 9 | 0.00 | Same, in every block. |
| `overwrite_128bit` | 3 / 3 | 3.7 pts | Fine-tuning a second watermark into the same layer flipped 12.5% of our 512 code values: too many bytes damaged for Reed-Solomon. |
| `overwrite_512bit` | 1 / 3 under the 5-point rule | 5.3 pts | Same, 23% flipped. |

The other REJECTED copies (90-95% pruning, 70-90% per-layer pruning, 2-bit quantization) only failed once the model
was already useless (accuracy 9.5% to 51%), so they never counted as removals.

Key measurement that shaped the fix, per run (agreement = share of our 512 code values still correct):

```text
overwrite_128bit    agreement [0.854, 0.91, 0.861]   acc drop [0.038, 0.039, 0.034]
overwrite_512bit    agreement [0.764, 0.797, 0.75]   acc drop [0.053, 0.063, 0.043]
permute_in_carrier  agreement 0.457 - 0.537 (9 runs) acc drop 0.0
permute_all         agreement 0.486 - 0.564 (9 runs) acc drop 0.0
2^-64 line for 512 values: 358 agreements (69.9%)
```

Hardware: no GPU (12 CPU cores, 15 GB RAM), so every fix had to work on the existing trained models without retraining.

### 4.2 The next attack: channel scaling (found and added)

With permutation fixed, the obvious next move is the scaling half of neural structural obfuscation (Yan et al.,
USENIX Security 2023): multiply channel c of the block feeding the carrier by s_c > 0 through its BatchNorm weight and
bias, and divide the carrier's input weights by s_c. ReLU and MaxPool commute with positive scaling, so the function is
unchanged, but every carrier block becomes v_c / s_c. Tested before writing any defence:

```text
max |output change| x2:  1.4e-06    -> VERIFIED (scaling x2 too weak to flip signs)
max |output change| x10: 2.9e-06    -> FAIL watermark read; EVIDENCE 390/512 -> DAMAGED
```

So ×10 scaling breaks exact verification for free, and scaling plus permutation would also beat the evidence check.
Added to the suite as 4 new attacks (3 repeats × 3 seeds each, on signed and unsigned models):
`scale_in_carrier_x2`, `scale_in_carrier_x10`, `scale_in_carrier_x100`, `permute_scale_in_x10`.

### 4.3 The defence (`embedding/align.py`, `verify/verify_model.py`)

The verifier tries, cheapest first, function-preserving re-readings of the carrier and accepts only one that decodes
to **exactly** the 256-bit signed payload:

1. **raw**: the model as given (Phase 6 behaviour).
2. **permutation**: with s = 2·codeword − 1 and A = (Xᵀs) reshaped to (64, 9), the score of a block order π is
   Σ_c A_c · v_π(c): a sum over slots, so the best order is a linear assignment problem, solved exactly by the
   Hungarian algorithm (`scipy.optimize.linear_sum_assignment`).
3. **scaling**: find positive factors a_c making every code value of Σ_c a_c X_c v_c read as the codeword, with the
   largest worst-case margin: a linear program (`scipy.optimize.linprog`, HiGHS) with 65 variables and 512 constraints.
4. **permutation + scaling**: match the order on scale-normalised blocks, then solve the scales.

**Why it cannot make an unmarked model pass.** 64 positive factors can realise at most about 2^275 of the 2^512 sign
patterns of 512 code values (Cover's function-counting theorem, 1965), so fitting a codeword the model never carried
has probability about 2^-239.7. The search runs only when this bound is ≤ 2^-64 **and** the full signed payload is
being checked (`undo_is_safe`). Bounds computed by `log2_cover_fraction`:

```text
512 values, 64 channels (rs32):     2^-239.7   search allowed
384 values, 64 channels (rs16):     2^-139.9   search allowed
32 values, 16 channels (legacy):    2^-1.0     search REFUSED
```

That guard was added because of a real failure found during development: the first version made three Phase 5 tests
pass a wrong key, an unmarked model and someone else's model. Those tiny test models (width 8, no ECC, 32 values over
16 channels) let 16 free factors fit 32 signs almost always. With the guard, all Phase 5 tests pass again, and
`test_search_is_refused_when_it_could_fit_anything` locks it in.

**DAMAGED verdict (overwrite).** If exact verification fails after the signature and model checks pass, the verifier
counts how many code values agree with the signed codeword **in the model's own channel order** (no search, so the null
distribution is exactly Binomial(512, ½)). At 358 or more the chance for an unmarked model is below 2^-64 and the
verdict is **DAMAGED** (exit code 2): not a proof of the exact payload, but statistical proof that the copy was derived
from a model carrying our signed payload. The CLI prints an `EVIDENCE` line before the verdict. Not applied to legacy
short payloads (32 values cannot reach 2^-64).

New verifier options: `--no-align` (Phase 6 behaviour, for ablations). Exit codes: 0 VERIFIED, 1 REJECTED, 2 DAMAGED.

First checks on the broken-through models:

```text
runs/wm_v1/lam20_n256_rs32/seed2            VERIFIED  (margin 2.24)
scale x10 (scratch model)                   VERIFIED  after undoing channel scaling (margin 1.33)
permute_all + scale x10 (scratch model)     VERIFIED  after undoing channel permutation + scaling (62 of 64 moved)
permute_in_carrier seed2 rep1               VERIFIED  after undoing channel permutation (64 of 64 moved)
overwrite_128bit seeds 0,1,2                DAMAGED   e.g. 437/512 agree, chance 2^-208.4
overwrite_512bit seeds 0,1,2                DAMAGED   e.g. 384/512 agree, chance 2^-100.7
baseline seeds 0,1,2 (rs32 forced)          REJECTED
Mallory's model (rs32 forced)               REJECTED  264/512 agree, chance 2^-2.0
```

An approach that was tried and **not** used: weighting each carrier block by an invariant channel gain
(BN slope × previous filter norm). It is perfectly scale-invariant (clean and ×10-scaled models both gave 490/512) but
too inexact to decode (≈ 22 wrong values left), so the linear program replaced it.

### 4.4 False-accept stress test (`experiments/phase6b_false_accept.py`)

Every null case is read with our signed codeword and rs32 settings, through the full search:

```text
             group  cases  exact_accepts  damaged_verdicts  max_raw_agree  mean_raw_agree
         wrong key    600              0                 0            284           255.8
          baseline      3              0                 0            256           253.3
baseline scrambled     15              0                 0            278           258.5
           mallory      1              0                 0            264           264.0
 mallory scrambled      5              0                 0            265           259.2
       random init    100              0                 0            289           256.1

DAMAGED threshold 358 of 512. Worst raw agreement on any null case: 289.
DONE-WHEN (0 false VERIFIED, 0 false DAMAGED over 724 null cases): PASSED
real 2m16.9s
```

"wrong key" = our real trained watermarked models read with 200 random keys each, the hardest null (a genuinely
marked model, just not with this key). "scrambled" = randomly permuted and ×10 scaled.

### 4.5 Full rerun of the attack suite

Generated the 72 new attacked copies (36 signed, 36 unsigned control); accuracy unchanged on every one
(`drop +0.0000`, about 21 s each for the CIFAR-10 evaluation). Re-verified all 306 attacked copies with the new
verifier, writing `verify_6b.json` next to each (the Phase 6 `verify.json` files are untouched):

```text
$ python -m attacks.evaluate_attacked --jobs 4 --verify-file verify_6b.json --csv results/phase6b/attack_results.csv
seed 0: clean verdict VERIFIED | probe on (reproduced verifier margin 2.248)
seed 1: clean verdict VERIFIED | probe on (reproduced verifier margin 2.243)
seed 2: clean verdict VERIFIED | probe on (reproduced verifier margin 2.241)
wrote results/phase6b/attack_results.csv (306 rows)

$ python -m attacks.summarize --csv results/phase6b/attack_results.csv --out docs/phase6b_results.md --plots results/phase6b/plots
## Successful removals (verdict REJECTED, model still useful)
None. Every attack either left the watermark verified or destroyed the model.
False-accept rate (verifier says VERIFIED or DAMAGED on a model that never had the watermark): 0.000 over 54 checkpoints.
```

**Before and after:**

```text
Phase 6  wm 216: VERIFIED 177, DAMAGED  0, REJECTED 39 | baseline 18: false accepts 0 | attack configs 43
Phase 6b wm 252: VERIFIED 231, DAMAGED 20, REJECTED  1 | baseline 54: false accepts 0 | attack configs 47
```

Per-attack changes on the signed models:

```text
attack_id              Phase 6    Phase 6b
overwrite_128bit       REJECTED   DAMAGED     3
overwrite_512bit       REJECTED   DAMAGED     3
permute_all            REJECTED   VERIFIED    9
permute_in_carrier     REJECTED   VERIFIED    9
permute_scale_in_x10   (new)      VERIFIED    9
scale_in_carrier_x2    (new)      VERIFIED    9
scale_in_carrier_x10   (new)      VERIFIED    9
scale_in_carrier_x100  (new)      VERIFIED    9
prune_global_0.9       REJECTED   DAMAGED     3     (model already useless, acc ~10%)
prune_global_0.95      REJECTED   DAMAGED     3     (useless)
prune_layer_0.7        REJECTED   DAMAGED     3     (useless, drop 31 pts)
prune_layer_0.9        REJECTED   DAMAGED     3     (useless)
quant_pt_2             REJECTED   DAMAGED     2     (useless, acc 9.5%); 1 run still REJECTED
lowest margin after undoing: scale x2 0.01, x100 0.17, permute+scale x10 0.72, x10 1.09
```

**Successful removals: 4 attack types → 0.** Every one of the 47 attacks now leaves the copy VERIFIED, or DAMAGED
(provably ours), or destroys the model.

### 4.6 Every file changed in Phase 6b

| File | Change |
|---|---|
| `embedding/align.py` (new, 152 lines) | Permutation alignment (Hungarian), scale recovery (LP), `candidate_readouts`, Cover bound (`log2_cover_fraction`, `undo_is_safe`), exact binomial tail (`log2_tail`), `evidence_threshold` (358 for 512), `agreement`. |
| `verify/verify_model.py` | Candidate readouts after a failed exact read (full payload only), `_evidence()` and the DAMAGED verdict, `EVIDENCE` line, `--no-align`, exit codes 0/1/2, `settings["realigned"]`, docstring. |
| `embedding/projection.py` | `ProjectionWatermark.matrix()` public accessor for the secret matrix. |
| `attacks/weight_attacks.py` | `scale_carrier_inputs()` (function-preserving input-channel scaling). |
| `attacks/registry.py` | 4 new configs (family `scale_in`): 47 attacks + control. |
| `attacks/make_attacked.py` | `scale_in` family, optionally after `permute_channels(..., "all")`. |
| `attacks/measure.py` | Parses the `DAMAGED` verdict line. |
| `attacks/summarize.py` | `detected` = VERIFIED or DAMAGED; a removal needs REJECTED and a useful model; `detected_rate` column; `scale_in` in the function-preserving sanity check; report wording. |
| `attacks/evaluate_attacked.py` | `--verify-file` so Phase 6b writes `verify_6b.json` and keeps the Phase 6 reports. |
| `experiments/phase6b_false_accept.py` (new) | The 724-case stress test, writes `results/phase6b/false_accept.csv`. |
| `pqctl/actions/xray.py` | Same undo search and DAMAGED rule as the verifier, so the X-ray never disagrees with it; prints `undone` and `evidence`. |
| `pqctl/actions/attack_lab.py` | Attacks `scale_in` and `permute_scale`; reports DAMAGED, evidence and what was undone. |
| `pqctl/tasks.py` | Tasks `p6.obfuscate`, `p6.evaluate6b`, `p6.summarize6b`, `p6.false_accept`; pipeline `phase6b`; `p6.false_accept` added to `check-all`; Phase 6 card and roadmap text. |
| `pqctl/runner.py` | Verdict regex includes DAMAGED; DAMAGED tone is amber ("warn"); multi-step summary counts DAMAGED. |
| `pqctl/state.py` | Dashboard reads `results/phase6b` when present (`source` field); totals count DAMAGED; false accepts count VERIFIED or DAMAGED. |
| `pqctl/static/app.js`, `labs.js`, `app.css` | DAMAGED everywhere: verdict boxes, result cards, log colouring, Attack lab history, outcome "damaged" in the results table and filter; Test-model page: the "known weaknesses" group became "Former weaknesses, fixed in Phase 6b" (shuffled → VERIFIED, shuffled + rescaled → VERIFIED, overwritten → DAMAGED); new Attack lab cards; amber styles. |
| `tests/test_phase6b.py` (new, 12 tests) | Clean model needs no undo; 5 function-preserving attacks broken without `--no-align` and undone with it (`permute_in`, `permute_all`, `scale_x10`, `scale_x100`, `permute_scale_x10`, each checked to be truly function-preserving); simulated overwrite → DAMAGED; unmarked and wrong-key → REJECTED; binomial tail against scipy; exact inverse permutation and scales on synthetic data; LP cannot fit noise; search refused for short codes. |
| `tests/test_pqctl.py` | `test_damaged_verdict_is_parsed_and_amber`. |
| `docs/threat_model.md` | Measured Remover results (Phase 6 and 6b), not-yet-tested attacks, operational notes (auditor learns the key; keys shared over a chat app; `created_utc` is self-declared, so priority disputes need RFC 3161 or a transparency log). |
| `docs/phase6b_results.md`, `results/phase6b/` (new) | Generated tables, per-attack summary, 10 plots (new `scale_in.png`), `false_accept.csv`. |
| `docs/phase6_results.md`, `results/phase6/attack_summary.csv` | Regenerated by `check-all` with the new summarize code: wording plus the `detected_rate` column; **numbers identical** (Phase 6 data has no DAMAGED). |
| `runs/attacks/**/verify_6b.json` (306), new attack folders (72 runs, 45 MB of models) | Phase 6b reports and the new attacked copies. |
| `README.md`, `skills.md`, `docs/PQCTL.md` | Results, limitations, roadmap, test counts; changelog v3.2; `phase6b` pipeline row. |

Size: 25 tracked files changed, 813 insertions, 143 deletions (excluding `runs/` and `results/`).

### 4.7 Final verification

```text
$ pytest
76 passed in 20.96s

$ python -m pqctl pipeline check-all       # now 14 steps, includes the false-accept stress test
── summary · 235s ──
  p0.mldsa           passed    signature OK
  tests.all          passed    76 passed
  p2.verify_release  passed    VERIFIED
  p2.tamper          passed    PASSED
  p3.check           passed    PASSED
  p3.verify_legacy   passed    VERIFIED
  p4.verify_all      passed    all 8 VERIFIED
  p5.verify          passed    VERIFIED
  p5.negative        passed    PASSED
  p6.compat          passed    PASSED
  p6.summarize       passed
  p6.false_accept    passed    PASSED
  p7.collect         passed
  p7.plots           passed
```

---

## 5. Research-paper assessment (2026-11-02)

Verdict at the time: suitable for an IEEE student or regional conference; IEEE Access with more work; not yet a top
venue. Main reviewer objections and their status after Phase 6b:

| Objection | Status |
|---|---|
| Novelty is integration (Uchida 2017, Li et al. piracy-resistant watermarks, TATTOOED's ECC); argue the post-quantum angle (forge-later threat). | Open, writing task. |
| Permutation removal is a known published attack (Yan et al. USENIX Sec 2023, DeepEclipse USENIX Sec 2024). | **Addressed:** permutation and scaling are undone with a provable false-fit bound; compare with CANON (Jiang et al. 2026). |
| No ambiguity attack evaluation; `created_utc` self-declared. | Open: needs an experiment plus RFC 3161 or a transparency log. |
| Auditor needs the secret watermark key. | Documented; zero-knowledge verification as future work. |
| Small scale: SmallCNN, CIFAR-10, 3 seeds, −3.1 pts accuracy cost. | Open: ResNet-18, CIFAR-100, 5 seeds, margin-capped loss. |
| Overwrite still erases the exact payload. | Partly addressed: DAMAGED gives provable evidence of origin; a robust exact fix needs retraining (for example multiple or secret carrier layers). |

---

## 6. Known issues still open

- Dummy-neuron obfuscation, overwriting a different layer, much longer fine-tuning, attacks on the rs16 models: not tested.
- The permutation-plus-scaling search has an empirical false-accept rate of 0/724 and a provable bound for scaling
  alone; a rigorous bound for the combined search (a union bound over 64! orders is too loose) is still open.
- DAMAGED is evidence, not proof of the exact payload; a priority dispute still needs a trusted timestamp.
- Watermark settings (ecc, layer, mode) are unsigned (manifest v2 idea); the manifest has no training config.
- X-ray earlier gave VERIFIED for a legacy 32-bit model that the verifier rejects without `--allow-short` (unchanged).
- Small: `.gitignore` lacks `.venv/`; `phase2_tamper_demo.py` hard-codes the key path; `train_watermarked.py` with 0
  epochs crashes and always pins memory; the raw-flip probe supports only `mean` mode; the dashboard job list grows
  without limit; the GitHub repo description mentions a desktop app and ResNet-18 that do not exist.

---

## 7. How to reproduce everything

```bash
pytest                                                     # 76 tests
python -m pqctl pipeline check-all                         # every check incl. the false-accept stress test
python -m pqctl pipeline phase6b                           # new attacks, re-verify all copies, tables, stress test
python -m verify.verify_model --model runs/attacks/wm/seed0/permute_in_carrier/rep0/model.pt      # VERIFIED (undone)
python -m verify.verify_model --model runs/attacks/wm/seed0/overwrite_128bit/rep0/model.pt        # DAMAGED
python -m verify.verify_model --no-align --model runs/attacks/wm/seed0/permute_in_carrier/rep0/model.pt   # REJECTED (Phase 6)
python -m experiments.phase6b_false_accept                 # 0 false accepts over 724 null cases
```

"""Every runnable step of the project, grouped by phase, plus pipelines that chain them.

A task is a plain dict:
  id, phase, title, what (plain words), cost ("seconds" | "minutes" | "hours"), est (text),
  where ("local" | "colab"; colab = a GPU is strongly recommended), needs (subset of NEEDS),
  danger (text, or None: tasks that overwrite keys/releases need an explicit confirmation),
  params (list of param dicts), argv (module/script + fixed args) or build (function -> list of steps).

A param dict: name, label, type, default, flag, help, choices.
  types: int, ints, float, floats, str, choice, choices, bool, model (an existing .pt file in the repo), model_opt (same, or blank)
  default "@cifar" means "the CIFAR-10 folder from the settings".

Only tasks listed here can be run: neither the CLI nor the dashboard accepts free-form commands.
"""
import glob
import os
import shlex
from pathlib import Path

NEEDS = {
    "torch": "PyTorch",
    "liboqs": "liboqs-python (ML-DSA)",
    "pandas": "pandas + matplotlib",
    "pytest": "pytest",
    "cifar": "CIFAR-10 in the data folder",
    "keys": "keys/ (public key + watermark key)",
    "secret": "keys/secret_key.bin (ML-DSA signing key)",
    "mallory": "mallory/keys/ (second developer)",
}

PHASES = [
    {"n": 0, "title": "Scope and setup", "plain": "Tools installed and the post-quantum signature library tested.",
     "artifacts": ["tests/test_mldsa.py", "docs/threat_model.md"]},
    {"n": 1, "title": "Baseline model", "plain": "A normal CIFAR-10 image classifier with no watermark, 3 seeds, to compare against.",
     "artifacts": ["runs/baseline/seed0/model.pt", "runs/baseline/seed1/model.pt", "runs/baseline/seed2/model.pt"]},
    {"n": 2, "title": "Signing and provenance", "plain": "Merkle root of the 50,000 training images, a manifest, and an ML-DSA-65 signature over it.",
     "artifacts": ["release/signed_manifest.json", "release/payload.hex", "release/public_key.bin"]},
    {"n": 3, "title": "First watermark", "plain": "A 32-bit piece of the payload hidden in the weights by projection, no error correction.",
     "artifacts": ["runs/wm_v0/lam1_n32/seed0/model.pt"]},
    {"n": 4, "title": "Full payload with ECC", "plain": "The full 256-bit payload, Reed-Solomon protected, plus a weight-noise test.",
     "artifacts": ["runs/wm_v1/summary.json", "runs/wm_v1/lam20_n256_rs32/seed0/model.pt"]},
    {"n": 5, "title": "Verifier and negative cases", "plain": "One command says VERIFIED or REJECTED; wrong keys, tampered files, unmarked and foreign models are rejected.",
     "artifacts": ["verify/verify_model.py", "mallory/release/signed_manifest.json"]},
    {"n": 6, "title": "Attack suite", "plain": "43 attacks (noise, pruning, quantization, fine-tuning, permutation, overwrite) and a results table.",
     "artifacts": ["results/phase6/attack_results.csv", "docs/phase6_results.md"]},
    {"n": 7, "title": "Evaluation (started)", "plain": "P7.1: every finished run in one table, plus lambda, ECC, payload and ECC-under-attack plots. More seeds and ablations to come.",
     "artifacts": ["experiments/phase7/collect_runs.py", "results/phase7/wm_runs.csv", "results/phase7/plots/lambda_tradeoff.png"]},
]

FUTURE = [
    {"n": "6b", "title": "Fix the weak spots", "plain": "Permutation defence, attack rs16, stronger fine-tuning."},
    {"n": "7+", "title": "Rest of Phase 7", "plain": "5 seeds, payload size sweep, ECC on/off, a second model (ResNet-18)."},
    {"n": 8, "title": "Write-up and demo", "plain": "Report, 3-minute live demo, mentor Q and A."},
]

SEEDS = {"name": "seeds", "label": "Seeds", "type": "ints", "default": [0, 1, 2], "flag": "--seeds"}
DATA = {"name": "data_root", "label": "CIFAR-10 folder", "type": "str", "default": "@cifar", "flag": "--data-root"}


def _p(name, label, type_, default=None, flag=None, help=None, choices=None):
    return {"name": name, "label": label, "type": type_, "default": default, "flag": flag, "help": help, "choices": choices}


def _model(default, flag="--model", label="Model"):
    return _p("model", label, "model", default, flag)


def _verify_phase4_models(params, root):
    pats = ["runs/wm_v1/lam20_n256_rs32/seed*/model.pt", "runs/wm_v1/lam20_n256_rs16/seed*/model.pt",
            "runs/wm_v1/lam20_n256_rep2/seed*/model.pt"]
    found = []
    for pat in pats:
        found += sorted(glob.glob(str(Path(root) / pat)))
    rel = [os.path.relpath(f, root).replace(os.sep, "/") for f in found]
    return [("verify " + r, ["-m", "verify.verify_model", "--model", r]) for r in rel]


TASKS = [
    # ---------------- Phase 0
    dict(id="p0.mldsa", phase=0, title="ML-DSA self-test", cost="seconds", est="5 s", where="local", needs=["liboqs"],
         what="Signs 'hello' with ML-DSA-65 and checks that a tampered message fails.",
         argv=["tests/test_mldsa.py"]),
    dict(id="p0.torch", phase=0, title="PyTorch and CIFAR-10 check", cost="seconds", est="10 s (first download: up to 30 min)",
         where="local", needs=["torch"], what="Prints the torch version, GPU availability and loads one CIFAR-10 image (downloads it into data/ if missing).",
         argv=["tests/test_torch.py"]),
    dict(id="tests.all", phase=0, title="Every unit test", cost="seconds", est="15 s", where="local", needs=["pytest", "torch", "liboqs"],
         what="pytest over tests/ (phases 2 to 7 and pqctl). Every test must pass.", argv=["-m", "pytest", "tests", "-q"]),

    # ---------------- Phase 1
    dict(id="p1.train", phase=1, title="Train the baseline models", cost="hours", est="~8.5 min per seed on a T4, hours on CPU",
         where="colab", needs=["torch", "cifar"], what="Trains SmallCNN on CIFAR-10 for each seed. Finished seeds are skipped.",
         argv=["-m", "experiments.run_baseline_seeds"],
         params=[SEEDS, _p("epochs", "Epochs", "int", 30, "--epochs"), _p("width", "Width", "int", 32, "--width")]),

    # ---------------- Phase 2
    dict(id="p2.verify_release", phase=2, title="Verify the signed release", cost="seconds", est="5 s (+1 min with dataset)",
         where="local", needs=["liboqs", "keys"], what="Checks the ML-DSA signature on release/signed_manifest.json with your trusted public key.",
         argv=["-m", "verify.verify_release", "--release-dir", "release"],
         params=[_p("public_key", "Public key", "str", "keys/public_key.bin", "--public-key"),
                 _p("check_dataset", "Also re-hash CIFAR-10 (Merkle root)", "bool", False, "--check-dataset"),
                 _p("cifar_root", "CIFAR-10 folder", "str", "@cifar", "--cifar-root")]),
    dict(id="p2.tamper", phase=2, title="Tamper demo", cost="seconds", est="10 s", where="local", needs=["liboqs", "keys"],
         what="Edits copies of the release 6 different ways; every edit must be REJECTED.",
         argv=["-m", "experiments.phase2_tamper_demo"]),
    dict(id="p2.tests", phase=2, title="Phase 2 tests", cost="seconds", est="5 s", where="local", needs=["pytest", "liboqs"],
         what="Merkle tree, manifest and signing unit tests.", argv=["-m", "pytest", "tests/test_phase2.py", "-q"]),
    dict(id="p2.make_release", phase=2, title="Create a new signed release", cost="minutes", est="1-2 min", where="local",
         needs=["liboqs", "cifar"], danger="Makes NEW keys and a new release if --force is set. Every model trained with the old payload stops verifying.",
         what="Builds the manifest (Merkle root of CIFAR-10, model info, key id) and signs it. Refuses to overwrite without Force.",
         argv=["-m", "experiments.phase2_make_release"],
         params=[_p("developer_id", "Developer id", "str", "Post-Quantum-Testing", "--developer-id"),
                 _p("width", "Width", "int", 32, "--width"), _p("cifar_root", "CIFAR-10 folder", "str", "@cifar", "--cifar-root"),
                 _p("force", "Force (overwrite)", "bool", False, "--force")]),

    # ---------------- Phase 3
    dict(id="p3.check", phase=3, title="Check the 32-bit watermark", cost="seconds", est="30 s", where="local", needs=["torch", "keys"],
         what="Bit errors with the right key, with 50 wrong keys, and on an unmarked baseline.",
         argv=["-m", "experiments.phase3_check_extraction", "--n-bits", "32"],
         params=[_model("runs/wm_v0/lam1_n32/seed0/model.pt"),
                 _p("baseline", "Unmarked baseline", "model", "runs/baseline/seed0/model.pt", "--baseline-model")]),
    dict(id="p3.verify_legacy", phase=3, title="Verify a Phase 3 model (legacy mode)", cost="seconds", est="10 s", where="local",
         needs=["torch", "liboqs", "keys"], what="Phase 3 models embed 32 of the 256 signed bits, so they need --allow-short (prints a WARNING).",
         argv=["-m", "verify.verify_model", "--n-bits", "32", "--allow-short"],
         params=[_model("runs/wm_v0/lam1_n32/seed0/model.pt")]),
    dict(id="p3.train", phase=3, title="Train Phase 3 watermarked models", cost="hours", est="~8.5 min per run on a T4",
         where="colab", needs=["torch", "cifar", "keys"], what="Trains every (lambda, seed) pair with a 32-bit payload, then compares to the baseline.",
         argv=["-m", "experiments.run_phase3"],
         params=[_p("lams", "Lambdas", "floats", [0.1, 1, 5], "--lams"), SEEDS, _p("epochs", "Epochs", "int", 30, "--epochs"),
                 _p("n_bits", "Bits", "int", 32, "--n-bits")]),
    dict(id="p3.tests", phase=3, title="Phase 3 tests", cost="seconds", est="5 s", where="local", needs=["pytest", "torch"],
         what="Projection watermark unit tests.", argv=["-m", "pytest", "tests/test_phase3.py", "-q"]),
    dict(id="p3.make_key", phase=3, title="Create a watermark key", cost="seconds", est="1 s", where="local", needs=[],
         danger="With Force, replaces keys/watermark_key.bin. Every existing watermark becomes unreadable.",
         what="Writes 32 random bytes to keys/watermark_key.bin. Refuses to overwrite without Force.",
         argv=["-m", "experiments.phase3_make_wm_key"], params=[_p("force", "Force (overwrite)", "bool", False, "--force")]),

    # ---------------- Phase 4
    dict(id="p4.verify_all", phase=4, title="Verify every Phase 4 model", cost="seconds", est="1 min", where="local",
         needs=["torch", "liboqs", "keys"], what="Runs the verifier on all rs32, rs16 and rep2 models. Each must say VERIFIED.",
         build=_verify_phase4_models),
    dict(id="p4.noise", phase=4, title="Weight-noise test", cost="minutes", est="2-3 min (+ accuracy if CIFAR-10 given)",
         where="local", needs=["torch", "keys"], what="Adds noise at 12 levels, 20 trials each, and checks the payload still decodes. Writes noise_test.json.",
         argv=["-m", "experiments.phase4_noise_test"],
         params=[_model("runs/wm_v1/lam20_n256_rs32/seed0/model.pt"), _p("trials", "Trials per level", "int", 20, "--trials"),
                 _p("data_root", "CIFAR-10 folder (blank = skip accuracy)", "str", "", "--data-root")]),
    dict(id="p4.train", phase=4, title="Train Phase 4 watermarked models", cost="hours", est="~8.5 min per run on a T4",
         where="colab", needs=["torch", "cifar", "keys"], what="Trains every (ECC, layer, lambda, seed) combination with the full 256-bit payload.",
         argv=["-m", "experiments.run_phase4"],
         params=[_p("eccs", "ECC codes", "choices", ["rs32"], "--eccs", choices=["rs32", "rs16", "rep2", "none"]),
                 _p("layers", "Layers", "choices", ["features.6.0.weight"], "--layers", choices=["features.6.0.weight", "features.4.0.weight"]),
                 _p("lams", "Lambdas", "floats", [20], "--lams"), SEEDS, _p("epochs", "Epochs", "int", 30, "--epochs")]),
    dict(id="p4.tests", phase=4, title="Phase 4 tests", cost="seconds", est="5 s", where="local", needs=["pytest", "torch"],
         what="Error-correcting code unit tests.", argv=["-m", "pytest", "tests/test_phase4.py", "-q"]),

    # ---------------- Phase 5
    dict(id="p5.verify", phase=5, title="Verify one model", cost="seconds", est="10 s", where="local", needs=["torch", "liboqs", "keys"],
         what="The auditor's command: signature, model, watermark, payload. Prints VERIFIED or REJECTED with reasons.",
         argv=["-m", "verify.verify_model"],
         params=[_model("runs/wm_v1/lam20_n256_rs32/seed0/model.pt"),
                 _p("allow_short", "Legacy model (allow short payload)", "bool", False, "--allow-short"),
                 _p("n_bits", "Bits (blank = from manifest)", "int", "", "--n-bits")]),
    dict(id="p5.negative", phase=5, title="Negative-case suite", cost="minutes", est="1-2 min", where="local",
         needs=["torch", "liboqs", "keys", "mallory"], what="8 cases per seed: wrong keys, tampered manifest, unmarked and Mallory's models must be rejected for the right reason.",
         argv=["-m", "experiments.phase5_negative_cases"],
         params=[SEEDS, _p("model_pattern", "Model pattern", "choice", "runs/wm_v1/lam20_n256_rs32/seed{seed}/model.pt", "--model-pattern",
                           choices=["runs/wm_v1/lam20_n256_rs32/seed{seed}/model.pt", "runs/wm_v1/lam20_n256_rs16/seed{seed}/model.pt"])]),
    dict(id="p5.tests", phase=5, title="Phase 5 tests", cost="seconds", est="5 s", where="local", needs=["pytest", "torch", "liboqs"],
         what="Verifier unit tests, including the full-payload rule (fix H1).", argv=["-m", "pytest", "tests/test_phase5.py", "-q"]),
    dict(id="p5.make_mallory", phase=5, title="Create Mallory (second developer)", cost="seconds", est="5 s", where="local", needs=["liboqs"],
         danger="With Force, replaces mallory/keys and mallory/release. Mallory's trained models stop verifying.",
         what="Mallory's own ML-DSA key, watermark key and signed manifest, for the negative cases.",
         argv=["-m", "experiments.phase5_make_mallory"], params=[_p("force", "Force (overwrite)", "bool", False, "--force")]),
    dict(id="p5.standin", phase=5, title="Train Mallory's stand-in model", cost="minutes", est="2-5 min on CPU", where="local",
         needs=["torch", "cifar", "mallory"], what="One epoch of fine-tuning that embeds Mallory's payload with Mallory's key.",
         argv=["-m", "experiments.phase5_mallory_standin"], params=[DATA]),

    # ---------------- Phase 6
    dict(id="p6.compat", phase=6, title="Compatibility check (run first)", cost="seconds", est="30 s", where="local",
         needs=["torch", "liboqs", "keys"], what="Confirms the attack suite can drive your verifier. Must print COMPAT CHECK: PASSED.",
         argv=["-m", "attacks.check_compat"], params=[_model("runs/wm_v1/lam20_n256_rs32/seed0/model.pt")]),
    dict(id="p6.cheap", phase=6, title="Weight attacks on signed models", cost="hours", est="~1.5 h on CPU", where="local",
         needs=["torch", "cifar"], what="Noise, pruning, quantization, rescale, permutation. Finished attacks are skipped.",
         argv=["-m", "attacks.make_attacked", "--cost", "cheap"], params=[SEEDS, DATA]),
    dict(id="p6.control", phase=6, title="Same attacks on unsigned models", cost="minutes", est="~5 min on CPU", where="local",
         needs=["torch", "cifar"], what="Control group: the verifier must never accept an unsigned model.",
         argv=["-m", "attacks.make_attacked", "--source", "baseline", "--ids", "none", "prune_global_0.5",
               "noise_all_s0.1", "quant_pt_8"], params=[SEEDS, DATA]),
    dict(id="p6.train", phase=6, title="Training attacks", cost="hours", est="~20 min on a T4, hours on CPU", where="colab",
         needs=["torch", "cifar"], what="Fine-tuning, prune + fine-tune, overwrite with a second watermark.",
         argv=["-m", "attacks.make_attacked", "--cost", "train"], params=[SEEDS, DATA]),
    dict(id="p6.evaluate", phase=6, title="Verify every attacked model", cost="minutes", est="~20 min", where="local",
         needs=["torch", "liboqs", "keys"], what="Runs the real verifier on each attacked copy. Writes results/phase6/attack_results.csv. Finished ones are skipped.",
         argv=["-m", "attacks.evaluate_attacked"], params=[_p("jobs", "Parallel jobs", "int", 2, "--jobs")]),
    dict(id="p6.summarize", phase=6, title="Build the results tables and plots", cost="seconds", est="10 s", where="local",
         needs=["pandas"], what="Per-attack table, successful removals, false-accept rate, plots. Writes docs/phase6_results.md.",
         argv=["-m", "attacks.summarize"], params=[_p("useful_drop", "Max accuracy drop for a 'useful' model", "float", 0.05, "--useful-drop")]),
    dict(id="p6.tests", phase=6, title="Phase 6 tests", cost="seconds", est="10 s", where="local", needs=["pytest", "torch"],
         what="Attack code unit tests.", argv=["-m", "pytest", "tests/test_phase6_attacks.py", "tests/test_phase6_logic.py", "-q"]),
    # ---------------- Phase 7
    dict(id="p7.collect", phase=7, title="Collect every run into one table", cost="seconds", est="5 s", where="local", needs=["pandas"],
         what="P7.1: reads every finished watermark run and the baselines, writes results/phase7/wm_runs.csv and wm_config_summary.csv.",
         argv=["-m", "experiments.phase7.collect_runs"]),
    dict(id="p7.plots", phase=7, title="Phase 7 plots", cost="seconds", est="10 s", where="local", needs=["pandas"],
         what="Lambda trade-off, ECC comparison, payload vs accuracy and ECC under attack. Run 'Collect' first.",
         argv=["-m", "experiments.phase7.make_plots"],
         params=[_p("lam", "Lambda for the ECC and payload plots", "float", 20.0, "--lam")]),

    # ---------------- interactive lab tools (used by the dashboard's GUI pages; also runnable from the CLI)
    dict(id="lab.xray", phase="lab", title="Watermark X-ray", cost="seconds", est="5 s", where="local", needs=["torch"], lab=True,
         what="Reads the hidden code out of any model and shows all 512 code values, the repair and the 256 payload bits.",
         argv=["-m", "pqctl.actions.xray"],
         params=[_model("runs/wm_v1/lam20_n256_rs32/seed0/model.pt"),
                 _p("key", "Read with which watermark key", "choice", "ours", "--key", choices=["ours", "mallory", "random"])]),
    dict(id="lab.attack", phase="lab", title="Attack lab", cost="minutes", est="5-60 s (+ accuracy ~30 s)", where="local", needs=["torch", "liboqs", "keys"], lab=True,
         what="Applies one Phase 6 attack at the strength you pick, verifies the copy and shows which bits flipped.",
         argv=["-m", "pqctl.actions.attack_lab"],
         params=[_model("runs/wm_v1/lam20_n256_rs32/seed0/model.pt"),
                 _p("attack", "Attack", "choice", "noise_all", "--attack", choices=["noise_all", "noise_carrier", "prune_global", "prune_layer",
                    "quantize", "quantize_pc", "half", "rescale", "permute_out", "permute_in", "permute_all", "finetune", "overwrite"]),
                 _p("strength", "Strength", "float", 0.1, "--strength"),
                 _p("accuracy", "Also measure accuracy (needs CIFAR-10)", "bool", False, "--accuracy"),
                 _p("data_root", "CIFAR-10 folder", "str", "@cifar", "--data-root")]),
    dict(id="lab.tamper", phase="lab", title="Tamper lab", cost="seconds", est="3 s", where="local", needs=["liboqs", "keys"], lab=True,
         what="Edits a temporary copy of the signed release the way you choose, then verifies it. The real release is never touched.",
         argv=["-m", "pqctl.actions.tamper_lab"],
         params=[_p("developer_id", "Developer id", "str", "", "--developer-id"),
                 _p("width", "Model width", "int", "", "--width"),
                 _p("num_samples", "Number of training images", "int", "", "--num-samples"),
                 _p("flip_root", "Change 1 character of the dataset fingerprint", "bool", False, "--flip-root"),
                 _p("flip_signature", "Change 1 character of the signature", "bool", False, "--flip-signature"),
                 _p("flip_payload", "Change 1 character of payload.hex", "bool", False, "--flip-payload"),
                 _p("wrong_key", "Check with an unrelated public key", "bool", False, "--wrong-key"),
                 _p("model", "Also verify this model against the edited release (blank = no)", "model_opt", "", "--model")]),
    dict(id="lab.sign", phase="lab", title="Signing lab", cost="seconds", est="1 s", where="local", needs=["liboqs"], lab=True,
         what="Signs any text with a throwaway ML-DSA-65 key pair and checks it against the text you choose.",
         argv=["-m", "pqctl.actions.sign_lab"],
         params=[_p("message", "Text to sign", "str", "This model was trained by our team on CIFAR-10.", "--message"),
                 _p("check", "Text the verifier receives", "str", "This model was trained by our team on CIFAR-10.", "--check")]),
]

BY_ID = {t["id"]: t for t in TASKS}

PIPELINES = [
    {"id": "check-all", "title": "Run every check", "est": "~5 min", "stop_on_fail": False,
     "what": "Re-proves phases 0 to 7 from what is already in the repo: tests, signature, tamper demo, every watermark, negative cases, attack-suite compatibility, results tables and Phase 7 plots. No training; models, keys and the release are never changed (only the results tables and plots are rewritten).",
     "steps": ["p0.mldsa", "tests.all", "p2.verify_release", "p2.tamper", "p3.check", "p3.verify_legacy", "p4.verify_all",
               "p5.verify", "p5.negative", "p6.compat", "p6.summarize", "p7.collect", "p7.plots"]},
    {"id": "phase6", "title": "Phase 6 attack run (local)", "est": "~2 h on CPU", "stop_on_fail": True,
     "what": "Compatibility check, weight attacks, control group, verification of every attacked model, results. Skips anything already done.",
     "steps": ["p6.compat", "p6.cheap", "p6.control", "p6.evaluate", "p6.summarize"]},
    {"id": "rebuild", "title": "Rebuild everything from scratch", "est": "many hours on CPU",
     "stop_on_fail": True,
     "what": "Trains the baselines, the Phase 3 and Phase 4 models, Mallory's stand-in, runs every attack (training ones too) and then every check. Uses your existing keys and release. Finished runs are skipped, so delete runs/ folders first for a true rebuild.",
     "steps": ["p0.torch", "p1.train", "p3.train", "p4.train", "p4.noise", "p5.standin", "p6.compat", "p6.cheap", "p6.control",
               "p6.train", "p6.evaluate", "p6.summarize", "tests.all", "p2.verify_release", "p4.verify_all", "p5.negative"]},
]
PIPE_BY_ID = {p["id"]: p for p in PIPELINES}


# ------------------------------------------------------------------ parameters

class ParamError(ValueError):
    pass


def defaults(task, settings):
    out = {}
    for p in task.get("params", []):
        v = p["default"]
        if v == "@cifar":
            v = settings.get("cifar_root", "data")
        out[p["name"]] = v
    return out


def _as_list(v):
    if isinstance(v, (list, tuple)):
        return list(v)
    if v is None:
        return []
    return [x for x in str(v).replace(",", " ").split() if x]


def clean_params(task, given, settings, root):
    """Validate user values against the task's param specs. Unknown names are rejected."""
    if given is not None and not isinstance(given, dict):
        raise ParamError("options must be a name -> value object")
    vals = defaults(task, settings)
    specs = {p["name"]: p for p in task.get("params", [])}
    for k, v in (given or {}).items():
        if k not in specs:
            raise ParamError("unknown option '%s' for %s" % (k, task["id"]))
        vals[k] = v
    out = {}
    for name, p in specs.items():
        v, t = vals.get(name), p["type"]
        try:
            if t == "bool":
                v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "y", "on")
            elif t == "int":
                v = None if v in (None, "") else int(v)
            elif t == "float":
                v = None if v in (None, "") else float(v)
            elif t == "ints":
                v = [int(x) for x in _as_list(v)]
            elif t == "floats":
                v = [float(x) for x in _as_list(v)]
            elif t == "choices":
                v = _as_list(v)
                bad = [x for x in v if x not in p["choices"]]
                if bad:
                    raise ParamError("%s: %s not allowed" % (p["label"], ", ".join(bad)))
            elif t == "choice":
                v = str(v)
                if v not in p["choices"]:
                    raise ParamError("%s: '%s' not allowed" % (p["label"], v))
            elif t == "model":
                v = safe_relpath(str(v), root, must_exist=True, suffix=".pt")
            elif t == "model_opt":
                v = "" if v in (None, "") else safe_relpath(str(v), root, must_exist=True, suffix=".pt")
            else:
                v = "" if v is None else str(v)
                if "\n" in v or "\x00" in v:
                    raise ParamError("%s: invalid characters" % p["label"])
        except (TypeError, ValueError) as e:
            if isinstance(e, ParamError):
                raise
            raise ParamError("%s: %s" % (p["label"], e))
        out[name] = v
    return out


def safe_relpath(path, root, must_exist=False, suffix=None):
    root = Path(root).resolve()
    p = (root / path).resolve()
    if root != p and root not in p.parents:
        raise ParamError("path must stay inside the project: %s" % path)
    if suffix and p.suffix != suffix:
        raise ParamError("expected a %s file: %s" % (suffix, path))
    if must_exist and not p.exists():
        raise ParamError("file not found: %s" % path)
    return os.path.relpath(p, root).replace(os.sep, "/")


def steps_for(task, params, root):
    """Return [(label, argv_without_python)]. argv[0] is either '-m' or a script path."""
    if "build" in task:
        return task["build"](params, root)
    argv = list(task["argv"])
    for p in task.get("params", []):
        v, flag = params.get(p["name"]), p["flag"]
        if not flag:
            continue
        if p["type"] == "bool":
            if v:
                argv.append(flag)
        elif isinstance(v, list):
            if v:
                argv += [flag] + [_fmt(x) for x in v]
        elif v not in (None, ""):
            argv += [flag, _fmt(v)]
    return [(task["title"], argv)]


def _fmt(x):
    if isinstance(x, float) and x.is_integer():
        return str(int(x)) if abs(x) >= 1 else repr(x)
    return str(x)


def display_cmd(argv, python="python"):
    return " ".join(shlex.quote(a) for a in [python] + argv)


def colab_cell(task, params, root):
    """A notebook cell that runs this task on Colab (project in Drive: My Drive/pq-watermark)."""
    lines = ["from google.colab import drive",
             "drive.mount('/content/drive')",
             "%cd /content/drive/MyDrive/pq-watermark",
             "!pip install -q \"reedsolo>=1.7\""]
    if "keys" in task.get("needs", []):
        lines.append("# upload keys/watermark_key.bin with files.upload() first and check its fingerprint")
    for _, argv in steps_for(task, params, root):
        argv = [("/content/data" if a == params.get("data_root") and params.get("data_root") else a) for a in argv]
        lines.append("!CIFAR_ROOT=/content/data PYTHONUNBUFFERED=1 " + display_cmd(argv))
    return "\n".join(lines)

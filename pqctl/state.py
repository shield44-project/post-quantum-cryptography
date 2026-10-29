"""Reads the project folder: environment health, phase status, models and results. Read-only."""
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from pqctl import tasks as T

EXPECTED_WM_FINGERPRINT_FROM = "runs/wm_v1/lam20_n256_rs32/seed0/final.json"
SKIP_DIRS = {".git", "venv", ".venv", "__pycache__", "data", "keys", ".pqctl", "node_modules"}

_PROBE = r"""
import json, importlib.util, importlib.metadata as md
out = {}
for mod, dist in [("torch","torch"),("torchvision","torchvision"),("numpy","numpy"),("pandas","pandas"),
                  ("matplotlib","matplotlib"),("reedsolo","reedsolo"),("pytest","pytest"),("oqs","liboqs-python")]:
    spec = importlib.util.find_spec(mod)
    v = None
    if spec:
        try: v = md.version(dist)
        except Exception: v = "installed"
    out[mod] = v
try:
    import torch
    out["cuda"] = bool(torch.cuda.is_available())
    out["cuda_name"] = torch.cuda.get_device_name(0) if out["cuda"] else None
except Exception as e:
    out["cuda"] = None
import sys
out["python"] = sys.version.split()[0]
out["executable"] = sys.executable
print("PQCTL_PROBE " + json.dumps(out))
"""

_cache = {}


def _read_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def probe_python(python, fresh=False):
    """Which packages the task interpreter has. Cached for 2 minutes (torch import is slow)."""
    key = ("probe", python)
    if not fresh and key in _cache and time.time() - _cache[key][0] < 120:
        return _cache[key][1]
    try:
        r = subprocess.run([python, "-c", _PROBE], capture_output=True, text=True, timeout=90)
        line = [l for l in r.stdout.splitlines() if l.startswith("PQCTL_PROBE ")]
        res = json.loads(line[-1][12:]) if line else {"error": (r.stderr or r.stdout)[-400:]}
    except Exception as e:
        res = {"error": str(e)}
    _cache[key] = (time.time(), res)
    return res


def wm_fingerprint(path):
    try:
        return hashlib.sha256(b"wm-key-fingerprint|" + Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def git_info(root):
    def g(*a):
        try:
            return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            return ""
    return {"branch": g("rev-parse", "--abbrev-ref", "HEAD"), "commit": g("rev-parse", "--short", "HEAD"),
            "subject": g("log", "-1", "--format=%s"), "dirty": bool(g("status", "--porcelain", "--untracked-files=no"))}


def doctor(root, settings, fresh=False):
    """List of {id, label, state ok|warn|bad, detail, fix}. Also returns which NEEDS are met."""
    root = Path(root)
    pr = probe_python(settings.get("python", sys.executable), fresh)
    checks, met = [], {}

    def add(id_, label, state, detail="", fix=""):
        checks.append({"id": id_, "label": label, "state": state, "detail": detail, "fix": fix})

    if "error" in pr:
        add("python", "Task interpreter", "bad", pr["error"], "Set the Python path in Settings to your venv's python.")
    else:
        add("python", "Task interpreter", "ok", "Python %s at %s" % (pr["python"], pr["executable"]))
    pkg = lambda m: pr.get(m) if "error" not in pr else None
    win = os.name == "nt"
    pipfix = ("venv\\Scripts\\python -m pip install " if win else "pip install ")
    for mod, label, fix in [("torch", "PyTorch", (pipfix + "torch torchvision --index-url https://download.pytorch.org/whl/cpu")),
                            ("reedsolo", "reedsolo (ECC)", pipfix + "\"reedsolo>=1.7\""),
                            ("pandas", "pandas", pipfix + "pandas matplotlib"), ("pytest", "pytest", pipfix + "pytest"),
                            ("oqs", "liboqs-python (ML-DSA)", "Build liboqs-python: see docs/HOW_TO_CHECK.md, step 2")]:
        v = pkg(mod)
        add("pkg-" + mod, label, "ok" if v else "bad", v or "not installed", "" if v else fix)
    met["torch"] = bool(pkg("torch") and pkg("torchvision") and pkg("reedsolo"))
    met["liboqs"] = bool(pkg("oqs"))
    met["pandas"] = bool(pkg("pandas") and pkg("matplotlib"))
    met["pytest"] = bool(pkg("pytest"))
    if "error" not in pr:
        if pr.get("cuda"):
            add("gpu", "GPU", "ok", pr.get("cuda_name") or "CUDA available")
        else:
            add("gpu", "GPU", "warn", "none (CPU only)", "Training tasks are much faster on Colab.")

    cifar = Path(settings.get("cifar_root", "data"))
    cifar = cifar if cifar.is_absolute() else root / cifar
    has_cifar = (cifar / "cifar-10-batches-py").is_dir()
    met["cifar"] = has_cifar
    add("cifar", "CIFAR-10", "ok" if has_cifar else "warn", str(cifar / "cifar-10-batches-py") + (" found" if has_cifar else " missing"),
        "" if has_cifar else "Run 'PyTorch and CIFAR-10 check' (Phase 0) once to download it, or point Settings at your copy.")

    pk, wk, sk = root / "keys/public_key.bin", root / "keys/watermark_key.bin", root / "keys/secret_key.bin"
    met["keys"] = pk.exists() and wk.exists()
    add("pubkey", "Public key", "ok" if pk.exists() else "bad", "keys/public_key.bin" + ("" if pk.exists() else " missing"),
        "" if pk.exists() else "Copy keys/ from the teammate who made the release (it is git-ignored).")
    rel_pk = root / "release/public_key.bin"
    if pk.exists() and rel_pk.exists() and pk.read_bytes() != rel_pk.read_bytes():
        add("pubkey-match", "Public key matches release", "bad", "keys/public_key.bin differs from release/public_key.bin",
            "You have another developer's key. Get the right keys/ folder.")
    expected = (_read_json(root / EXPECTED_WM_FINGERPRINT_FROM) or {}).get("key_fingerprint")
    fp = wm_fingerprint(wk)
    if not fp:
        add("wmkey", "Watermark key", "bad", "keys/watermark_key.bin missing", "Copy it from the team (never commit it).")
    elif expected and fp != expected:
        add("wmkey", "Watermark key", "bad", "fingerprint %s, models expect %s" % (fp, expected), "Wrong watermark key file.")
    else:
        add("wmkey", "Watermark key", "ok", "fingerprint " + fp)
    met["secret"] = sk.exists()
    add("secret", "ML-DSA secret key", "ok" if sk.exists() else "warn", "present" if sk.exists() else "missing (only needed to sign a new release)")
    mk = root / "mallory/keys/public_key.bin"
    met["mallory"] = mk.exists() and (root / "mallory/keys/watermark_key.bin").exists()
    add("mallory", "Mallory's keys", "ok" if met["mallory"] else "warn", "mallory/keys/" + (" found" if met["mallory"] else " missing"),
        "" if met["mallory"] else "Needed for the negative-case suite. Copy mallory/keys/ from the team or run 'Create Mallory'.")
    for f in ("release/signed_manifest.json", "release/payload.hex"):
        ok = (root / f).exists()
        add("rel-" + f, f, "ok" if ok else "bad", "found" if ok else "missing")
    gi = git_info(root)
    if gi["commit"]:
        add("git", "Git", "ok" if not gi["dirty"] else "warn", "%s @ %s: %s%s" % (gi["branch"], gi["commit"], gi["subject"],
                                                                              " (uncommitted changes)" if gi["dirty"] else ""))
    return {"checks": checks, "met": met, "probe": pr, "git": gi}


def missing_needs(task, met):
    return [T.NEEDS[n] for n in task.get("needs", []) if not met.get(n, True)]


# ------------------------------------------------------------------ phases and results

def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def baseline(root):
    out = []
    for s in (0, 1, 2, 3, 4):
        d = _read_json(Path(root) / ("runs/baseline/seed%d/final.json" % s))
        if d:
            out.append({"seed": s, "acc": d.get("test_acc"), "seconds": d.get("train_seconds")})
    return out


def phase4(root):
    d = _read_json(Path(root) / "runs/wm_v1/summary.json") or {}
    out = []
    for k, v in d.items():
        rows = v.get("rows", [])
        out.append({"config": k, "seeds": len(rows), "mean_wm_acc": v.get("mean_wm_acc"), "diff_pts": (v.get("mean_paired_diff") or 0) * 100,
                    "margin": v.get("min_abs_logit"), "decoded_errors": v.get("total_decoded_errors"),
                    "raw_errors": v.get("total_raw_bit_errors")})
    return out


def phase6(root):
    root = Path(root)
    res = {"summary": [], "totals": None, "plots": []}
    sp = root / "results/phase6/attack_summary.csv"
    if sp.exists():
        with open(sp, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                res["summary"].append({k: (_f(v) if k not in ("attack_id", "family") else v) for k, v in r.items()})
    rp = root / "results/phase6/attack_results.csv"
    if rp.exists():
        with open(rp, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        wm = [r for r in rows if r.get("source") == "wm"]
        base = [r for r in rows if r.get("source") == "baseline"]
        res["totals"] = {"wm_runs": len(wm), "wm_verified": sum(r.get("verdict") == "VERIFIED" for r in wm),
                         "base_runs": len(base), "base_false_accepts": sum(r.get("verdict") == "VERIFIED" for r in base),
                         "removed_types": sum(1 for r in res["summary"] if (r.get("removal_success") or 0) > 0)}
    pd_ = root / "results/phase6/plots"
    if pd_.is_dir():
        res["plots"] = sorted("results/phase6/plots/" + p.name for p in pd_.glob("*.png"))
    return res


def phases(root, history):
    root = Path(root)
    out = []
    b, p4, p6 = baseline(root), phase4(root), phase6(root)
    for ph in T.PHASES:
        have = [a for a in ph["artifacts"] if (root / a).exists()]
        state = "done" if len(have) == len(ph["artifacts"]) else ("partial" if have else "missing")
        tids = [t["id"] for t in T.TASKS if t["phase"] == ph["n"]]
        runs = {t: history[t] for t in tids if t in history}
        metric = None
        if ph["n"] == 1 and b:
            accs = [x["acc"] for x in b if x["acc"]]
            metric = {"value": "%.1f%%" % (100 * sum(accs) / len(accs)), "label": "mean accuracy, %d seeds" % len(accs)}
        elif ph["n"] == 2:
            m = (_read_json(root / "release/signed_manifest.json") or {}).get("manifest", {})
            if m:
                metric = {"value": m.get("signature_algorithm", "?"), "label": "key " + str(m.get("key_id", ""))[:8]}
        elif ph["n"] == 3:
            n = len(list((root / "runs/wm_v0").glob("*/seed*/model.pt")))
            metric = {"value": str(n), "label": "32-bit models"} if n else None
        elif ph["n"] == 4 and p4:
            best = next((x for x in p4 if x["config"] == "rs32/features.6.0/lam20"), p4[0])
            metric = {"value": "%+.1f pts" % best["diff_pts"], "label": "accuracy cost, %s" % best["config"].split("/")[0]}
        elif ph["n"] == 5:
            n = len(list((root / "mallory/runs").glob("*/seed*/model.pt")))
            metric = {"value": str(n), "label": "foreign models to reject"} if n else None
        elif ph["n"] == 7:
            p7 = phase7(root)
            if p7["configs"]:
                metric = {"value": "%d configs" % len(p7["configs"]), "label": "%d plots" % len(p7["plots"])}
        elif ph["n"] == 6 and p6["totals"]:
            t = p6["totals"]
            metric = {"value": "%d/%d" % (t["wm_verified"], t["wm_runs"]), "label": "attacked copies still verified"}
        out.append({**ph, "state": state, "have": have, "metric": metric, "runs": runs})
    return out


def models(root):
    root = Path(root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "model.pt" in filenames:
            rel = os.path.relpath(os.path.join(dirpath, "model.pt"), root).replace(os.sep, "/")
            fin = _read_json(os.path.join(dirpath, "final.json")) or {}
            group = rel.split("/")[0] + "/" + rel.split("/")[1] if rel.count("/") >= 2 else rel.split("/")[0]
            out.append({"path": rel, "group": group, "acc": fin.get("final_test_acc", fin.get("test_acc")),
                        "ecc": fin.get("ecc"), "n_bits": fin.get("n_bits"), "attack": rel.startswith("runs/attacks/")})
    rank = ["runs/wm_v1", "runs/wm_v0", "runs/baseline", "mallory/runs"]
    out.sort(key=lambda m: (m["attack"], rank.index(m["group"]) if m["group"] in rank else len(rank), m["path"]))
    return out


DOCS = ["docs/results_log.md", "docs/phase6_results.md", "docs/threat_model.md", "docs/HOW_TO_CHECK.md", "docs/PQCTL.md", "skills.md"]
SERVABLE = {".png": "image/png", ".csv": "text/csv; charset=utf-8", ".json": "application/json", ".md": "text/plain; charset=utf-8",
            ".txt": "text/plain; charset=utf-8"}


def safe_file(root, rel):
    """Resolve a file the dashboard may show. Never anything under keys/ or outside the project."""
    root = Path(root).resolve()
    p = (root / rel).resolve()
    if root not in p.parents:
        return None
    parts = p.relative_to(root).parts
    if parts and parts[0] in ("keys", ".git", "venv", ".venv") or "keys" in parts:
        return None
    if p.suffix not in SERVABLE or not p.is_file():
        return None
    return p


# ------------------------------------------------------------------ inspector (pure Python, no torch / liboqs)

def _canonical(manifest):
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def release_info(root, rel="release", pk_path="keys/public_key.bin"):
    """Everything about a signed release that can be shown without liboqs. The signature itself is checked by the
    verify tasks; here we recompute the hashes and compare files."""
    root = Path(root)
    signed = _read_json(root / rel / "signed_manifest.json")
    if not signed:
        return None
    m = signed["manifest"]
    canon = _canonical(m)
    digest = hashlib.sha256(canon).hexdigest()
    payload_file = (root / rel / "payload.hex").read_text().strip() if (root / rel / "payload.hex").exists() else None
    rel_pk = root / rel / "public_key.bin"
    trusted = root / pk_path
    info = {
        "dir": rel, "manifest": m, "algorithm": signed.get("algorithm"), "format": signed.get("format"),
        "canonical_bytes": len(canon), "canonical_preview": canon[:600].decode("ascii", "replace"),
        "sha256": digest, "payload_file": payload_file, "payload_matches": payload_file == digest,
        "payload_bits": "".join(format(int(c, 16), "04b") for c in digest),
        "signature_bytes": len(signed.get("signature_hex", "")) // 2,
        "signature_head": signed.get("signature_hex", "")[:64], "signature_tail": signed.get("signature_hex", "")[-32:],
        "public_key_bytes": rel_pk.stat().st_size if rel_pk.exists() else None,
        "key_id_of_release_key": hashlib.sha256(rel_pk.read_bytes()).hexdigest()[:32] if rel_pk.exists() else None,
        "trusted_key_present": trusted.exists(),
        "trusted_key_matches_release": trusted.exists() and rel_pk.exists() and trusted.read_bytes() == rel_pk.read_bytes(),
    }
    info["key_id_matches"] = info["key_id_of_release_key"] == m.get("key_id")
    return info


def inspect(root):
    root = Path(root)
    fin = _read_json(root / EXPECTED_WM_FINGERPRINT_FROM) or {}
    keys = {
        "ours": {"path": "keys/watermark_key.bin", "fingerprint": wm_fingerprint(root / "keys/watermark_key.bin"),
                 "expected": fin.get("key_fingerprint")},
        "mallory": {"path": "mallory/keys/watermark_key.bin", "fingerprint": wm_fingerprint(root / "mallory/keys/watermark_key.bin"),
                    "expected": (_read_json(root / "mallory/runs/lam20_n256_rs32/seed3/final.json") or {}).get("key_fingerprint")},
    }
    hashes = []
    hp = root / "docs/phase5_model_hashes.txt"
    if hp.exists():
        for line in hp.read_text().splitlines():
            parts = line.split()
            if len(parts) == 2:
                f = root / parts[1]
                now = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
                hashes.append({"path": parts[1], "frozen": parts[0], "now": now, "same": now == parts[0]})
    return {"ours": release_info(root), "mallory": release_info(root, "mallory/release", "mallory/keys/public_key.bin"),
            "keys": keys, "frozen_hashes": hashes, "model": fin}


def phase7(root):
    root = Path(root)
    out = {"configs": [], "under_attack": [], "plots": []}
    for name, key in (("results/phase7/wm_config_summary.csv", "configs"), ("results/phase7/ecc_under_attack.csv", "under_attack")):
        p = root / name
        if p.exists():
            with open(p, newline="", encoding="utf-8") as f:
                out[key] = [{k: (v if _f(v) is None else _f(v)) for k, v in row.items()} for row in csv.DictReader(f)]
    pd_ = root / "results/phase7/plots"
    if pd_.is_dir():
        out["plots"] = sorted("results/phase7/plots/" + p.name for p in pd_.glob("*.png"))
    return out

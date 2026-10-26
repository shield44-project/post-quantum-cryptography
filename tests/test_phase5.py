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

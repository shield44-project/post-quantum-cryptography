"""Tests for the pqctl control centre. No PyTorch or liboqs needed."""
import sys
import time
from pathlib import Path

import pytest

from pqctl import tasks as T
from pqctl import state as S
from pqctl.runner import Job, Runner, parse_verdict

ROOT = Path(__file__).resolve().parents[1]


def test_every_task_builds_a_command():
    r = Runner.__new__(Runner)
    settings = {"cifar_root": "data", "python": sys.executable}
    for t in T.TASKS:
        if any(p["type"] == "model" for p in t.get("params", [])):
            continue                                  # needs model files, covered below
        p = T.clean_params(t, None, settings, ROOT)
        steps = T.steps_for(t, p, ROOT)
        assert steps and all(isinstance(a, list) and a for _, a in steps), t["id"]


def test_pipelines_only_name_real_tasks():
    for p in T.PIPELINES:
        for s in p["steps"]:
            assert s in T.BY_ID, (p["id"], s)
    assert not any(T.BY_ID[s].get("danger") for p in T.PIPELINES for s in p["steps"])


def test_params_are_validated(tmp_path):
    t = T.BY_ID["p5.verify"]
    with pytest.raises(T.ParamError):
        T.clean_params(t, {"model": "../outside.pt"}, {}, tmp_path)
    with pytest.raises(T.ParamError):
        T.clean_params(t, {"nope": 1}, {}, tmp_path)
    with pytest.raises(T.ParamError):
        T.clean_params(T.BY_ID["p4.train"], {"eccs": "rs32 evil"}, {}, tmp_path)
    (tmp_path / "m.pt").write_bytes(b"x")
    p = T.clean_params(t, {"model": "m.pt", "allow_short": "yes"}, {}, tmp_path)
    assert T.steps_for(t, p, tmp_path)[0][1] == ["-m", "verify.verify_model", "--model", "m.pt", "--allow-short"]


def test_seeds_and_floats_format():
    t = T.BY_ID["p3.train"]
    p = T.clean_params(t, {"lams": "0.1, 1 5", "seeds": "0 2"}, {}, ROOT)
    argv = T.steps_for(t, p, ROOT)[0][1]
    assert argv[argv.index("--lams") + 1: argv.index("--lams") + 4] == ["0.1", "1", "5"]
    assert argv[argv.index("--seeds") + 1: argv.index("--seeds") + 3] == ["0", "2"]


def test_force_needs_confirmation(tmp_path):
    r = Runner(tmp_path)
    with pytest.raises(T.ParamError):
        r.make_job("p3.make_key", {"force": True})
    assert r.make_job("p3.make_key", {"force": True}, confirm=True)
    assert r.make_job("p3.make_key", {"force": False})


def test_verdict_parsing():
    assert parse_verdict(["x", "VERIFIED"]) == "VERIFIED"
    assert parse_verdict(["COMPAT CHECK: PASSED"]) == "PASSED"
    assert parse_verdict(["DONE-WHEN (4 negative cases rejected, own model passes): FAILED"]) == "FAILED"
    assert parse_verdict(["===== 42 passed in 13.21s ====="]) == "42 passed"
    assert parse_verdict(["correct message: True"]) == "signature OK"


def test_runner_streams_progress_and_records(tmp_path):
    r = Runner(tmp_path)
    code = "import sys,time\nfor i in range(3): sys.stdout.write('\\r%d%%' % (i*50)); sys.stdout.flush()\nprint()\nprint('VERIFIED')"
    j = Job("p5.verify", "demo", [("demo", ["-c", code])], {}, python=sys.executable)
    r.run(j)
    assert j.status == "passed" and j.verdict == "VERIFIED"
    assert "100%" in j.lines and not any("\r" in l for l in j.lines)
    assert r.history["p5.verify"]["status"] == "passed"
    assert (tmp_path / ".pqctl" / "logs" / (j.id + ".log")).exists()


def test_cancel_stops_a_running_job(tmp_path):
    r = Runner(tmp_path)
    j = Job("p0.mldsa", "sleepy", [("s", ["-c", "import time; print('start', flush=True); time.sleep(60)"])], {}, python=sys.executable)
    r.submit(j)
    t0 = time.time()
    while not j.lines and time.time() - t0 < 10:
        time.sleep(0.05)
    r.cancel(j.id)
    while j.status == "running" and time.time() - t0 < 15:
        time.sleep(0.05)
    assert j.status == "cancelled" and time.time() - t0 < 15


def test_dashboard_never_serves_keys(tmp_path):
    (tmp_path / "keys").mkdir()
    (tmp_path / "keys" / "x.json").write_text("{}")
    (tmp_path / "ok.csv").write_text("a\n")
    assert S.safe_file(tmp_path, "keys/x.json") is None
    assert S.safe_file(tmp_path, "../etc/passwd") is None
    assert S.safe_file(tmp_path, "ok.csv") is not None


def test_quick_jobs_can_jump_the_queue(tmp_path):
    r = Runner(tmp_path)
    slow = Job("p0.mldsa", "slow", [("s", ["-c", "import time; time.sleep(1)"])], {}, python=sys.executable)
    later = Job("p2.tamper", "later", [("l", ["-c", "pass"])], {}, python=sys.executable)
    quick = Job("p5.verify", "quick", [("q", ["-c", "pass"])], {}, python=sys.executable)
    r.submit(slow)
    time.sleep(0.2)
    r.submit(later)
    r.submit(quick, front=True)
    t0 = time.time()
    while later.status != "passed" and time.time() - t0 < 15:
        time.sleep(0.05)
    assert quick.started < later.started


def test_lab_tools_and_phase7_are_registered():
    for tid in ("lab.xray", "lab.attack", "lab.tamper", "lab.sign", "p7.collect", "p7.plots"):
        t = T.BY_ID[tid]
        argv = T.steps_for(t, T.clean_params(t, None, {"cifar_root": "data"}, ROOT), ROOT)[0][1]
        assert argv[0] == "-m"
    p = T.clean_params(T.BY_ID["lab.tamper"], {"developer_id": "Mallory", "flip_signature": True}, {}, ROOT)
    argv = T.steps_for(T.BY_ID["lab.tamper"], p, ROOT)[0][1]
    assert argv[argv.index("--developer-id") + 1] == "Mallory" and "--flip-signature" in argv and "--model" not in argv


def test_runner_captures_tool_result(tmp_path):
    r = Runner(tmp_path)
    code = "print('working'); print('PQCTL_JSON ' + %r); print('REJECTED')" % '{"verdict": "REJECTED", "n": 3}'
    j = Job("lab.tamper", "t", [("t", ["-c", code])], {}, python=sys.executable)
    r.run(j)
    assert j.result == {"verdict": "REJECTED", "n": 3}
    assert not any(l.startswith("PQCTL_JSON") for l in j.lines)
    assert j.status == "passed"          # REJECTED is a valid answer for a lab tool, not a failure


def test_tamper_lab_changes_the_fingerprint():
    """Runs the real tool on the real release (no liboqs needed for the hash part)."""
    import json
    import subprocess
    out = subprocess.run([sys.executable, "-m", "pqctl.actions.tamper_lab", "--developer-id", "Mallory"],
                         cwd=ROOT, capture_output=True, text=True, timeout=60).stdout
    data = json.loads([l for l in out.splitlines() if l.startswith("PQCTL_JSON ")][-1][11:])
    assert data["changes"][0]["what"] == "developer_id"
    assert data["hash_before"] != data["hash_after"]
    assert data["verdict"] == "REJECTED"
    assert (ROOT / "release" / "signed_manifest.json").read_text().count("Mallory") == 0   # real release untouched


def test_inspector_reads_the_release():
    info = S.inspect(ROOT)
    o = info["ours"]
    assert o["payload_matches"] and o["key_id_matches"]
    assert o["signature_bytes"] == 3309 and o["public_key_bytes"] == 1952

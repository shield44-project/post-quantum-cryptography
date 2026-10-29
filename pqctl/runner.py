"""Runs tasks as subprocesses, one at a time, keeps their logs and remembers the last result of each task.

The CLI and the dashboard share this code. State lives in .pqctl/ inside the project (git-ignored by its own
.gitignore): settings.json, history.json and one log file per job.
"""
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from pqctl import tasks as T

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
VERDICTS = [
    (re.compile(r"COMPAT CHECK:\s*(PASSED|FAILED)"), None),
    (re.compile(r"DONE-WHEN[^\n]*?(PASSED|FAILED|NOT YET)"), None),
    (re.compile(r"^(VERIFIED|REJECTED)\s*$"), None),
    (re.compile(r"=+\s*(.*?\b(?:passed|failed|error)\b.*?)\s+in\s+[\d.]+s"), "pytest"),
    (re.compile(r"^\s*(\d+ passed.*?)\s+in\s+[\d.]+s\s*$"), "pytest"),
    (re.compile(r"^correct message:\s*(True|False)"), "mldsa"),
]

IS_WIN = os.name == "nt"
MISSING = re.compile(r"No module named '?([\w.]+)'?")


def state_dir(root):
    d = Path(root) / ".pqctl"
    (d / "logs").mkdir(parents=True, exist_ok=True)
    gi = d / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n")
    return d


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def default_settings():
    return {"cifar_root": os.environ.get("CIFAR_ROOT", "data"), "python": sys.executable}


def parse_verdict(lines):
    """Last recognisable verdict line in the log, e.g. 'PASSED', 'VERIFIED', '42 passed'."""
    found = None
    for line in lines:
        for rx, kind in VERDICTS:
            m = rx.search(line)
            if m:
                v = m.group(1).strip()
                if kind == "mldsa":
                    v = "signature OK" if v == "True" else "signature FAILED"
                found = v
    return found


def verdict_tone(verdict, status):
    if status == "cancelled":
        return "muted"
    if not verdict:
        return "ok" if status == "passed" else ("bad" if status == "failed" else "muted")
    v = verdict.lower()
    if "fail" in v or "rejected" in v or "error" in v or "not yet" in v or v.startswith("missing"):
        return "bad"
    return "ok"


class Job:
    def __init__(self, task_id, title, steps, params, group=None, python=None, env=None):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.task_id, self.title, self.steps, self.params, self.group = task_id, title, steps, params, group
        self.python = python or sys.executable
        self.env = env or {}
        self.status = "queued"          # queued | running | passed | failed | cancelled | skipped
        self.verdict = None
        self.exit_code = None
        self.created = time.time()
        self.started = self.ended = None
        self.lines = []                 # committed log lines
        self.result = None              # structured data from a lab tool's final "PQCTL_JSON {...}" line
        self.live = ""                  # current partial line (progress bars)
        self.step_index = 0
        self.proc = None
        self.cancel_requested = False
        self.lock = threading.Lock()

    def summary(self):
        return {"id": self.id, "task_id": self.task_id, "title": self.title, "group": self.group, "status": self.status,
                "verdict": self.verdict, "tone": verdict_tone(self.verdict, self.status), "exit_code": self.exit_code,
                "created": self.created, "started": self.started, "ended": self.ended, "lines": len(self.lines),
                "step": self.step_index, "steps": [s[0] for s in self.steps], "has_result": self.result is not None,
                "commands": [T.display_cmd(a, "python") for _, a in self.steps]}

    def add_text(self, text, out=None):
        """Feed raw output. '\\r' rewrites the live line (tqdm), '\\n' commits it."""
        with self.lock:
            for ch in re.split(r"(\r\n|\r|\n)", text):
                if ch in ("\n", "\r\n"):
                    self.lines.append(ANSI.sub("", self.live))
                    self.live = ""
                elif ch == "\r":
                    self.live = ""
                else:
                    self.live += ch
        if out:
            out(text)

    def note(self, text, out=None):
        self.add_text(text + "\n", out)


class Runner:
    """A FIFO queue with one worker thread. Pipelines enqueue several jobs that share a group id."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.dir = state_dir(self.root)
        self.settings = {**default_settings(), **load_json(self.dir / "settings.json", {})}
        self.history = load_json(self.dir / "history.json", {})
        self.jobs = {}
        self.order = deque(maxlen=300)
        self.queue = deque()
        self.groups = {}
        self.cv = threading.Condition()
        self.worker = None

    # ------------------------------------------------------------- settings / history
    def set_settings(self, new):
        for k in ("cifar_root", "python"):
            if k in new and isinstance(new[k], str) and new[k].strip():
                v = new[k].strip()
                if k == "python" and not Path(v).is_file():
                    raise T.ParamError("Python interpreter not found: %s" % v)
                self.settings[k] = v
        save_json(self.dir / "settings.json", self.settings)
        return self.settings

    def _record(self, job):
        self.history[job.task_id] = {"status": job.status, "verdict": job.verdict, "tone": verdict_tone(job.verdict, job.status),
                                     "ended": job.ended, "job": job.id, "seconds": round((job.ended or 0) - (job.started or 0), 1)}
        save_json(self.dir / "history.json", self.history)

    # ------------------------------------------------------------- building jobs
    def make_job(self, task_id, params=None, group=None, confirm=False):
        task = T.BY_ID.get(task_id)
        if not task:
            raise T.ParamError("unknown task '%s'" % task_id)
        if task.get("danger") and _wants_force(params) and not confirm:
            raise T.ParamError("'%s' would overwrite files: %s Confirm to run it." % (task["title"], task["danger"]))
        p = T.clean_params(task, params, self.settings, self.root)
        steps = T.steps_for(task, p, self.root)
        if not steps:
            raise T.ParamError("nothing to run for %s (no matching files found)" % task["title"])
        env = {"CIFAR_ROOT": self.settings.get("cifar_root", "data")}
        return Job(task_id, task["title"], steps, p, group, self.settings.get("python"), env)

    def submit(self, job, front=False):
        """front=True puts a quick interactive job (a demo click, a verify) next in line, ahead of queued pipeline steps."""
        with self.cv:
            self.jobs[job.id] = job
            self.order.append(job.id)
            if front:
                self.queue.appendleft(job)
            else:
                self.queue.append(job)
            self.cv.notify_all()
        self._ensure_worker()
        return job

    def submit_task(self, task_id, params=None, confirm=False, front=False):
        return self.submit(self.make_job(task_id, params, confirm=confirm), front=front)

    def submit_pipeline(self, pipe_id):
        pipe = T.PIPE_BY_ID.get(pipe_id)
        if not pipe:
            raise T.ParamError("unknown pipeline '%s'" % pipe_id)
        gid = "pipe-" + uuid.uuid4().hex[:6]
        self.groups[gid] = {"pipeline": pipe_id, "stop_on_fail": pipe["stop_on_fail"]}
        jobs, problems = [], []
        for tid in pipe["steps"]:
            try:
                jobs.append(self.make_job(tid, None, group=gid))
            except T.ParamError as e:
                problems.append(str(e))
        for j in jobs:
            self.submit(j)
        return gid, jobs, problems

    # ------------------------------------------------------------- control
    def cancel(self, job_id):
        job = self.jobs.get(job_id)
        if not job:
            return False
        job.cancel_requested = True
        with self.cv:
            if job.status == "queued":
                job.status = "cancelled"
                job.ended = time.time()
                try:
                    self.queue.remove(job)
                except ValueError:
                    pass
                return True
        if job.proc and job.proc.poll() is None:
            kill_tree(job.proc)
        return True

    def cancel_group(self, gid):
        for jid in list(self.order):
            j = self.jobs[jid]
            if j.group == gid and j.status in ("queued", "running"):
                self.cancel(jid)

    def _ensure_worker(self):
        if self.worker and self.worker.is_alive():
            return
        self.worker = threading.Thread(target=self._loop, daemon=True, name="pqctl-worker")
        self.worker.start()

    def _loop(self):
        while True:
            with self.cv:
                while not self.queue:
                    self.cv.wait()
                job = self.queue.popleft()
            if job.status != "queued":
                continue
            if job.group and self._group_failed(job.group):
                job.status, job.ended = "skipped", time.time()
                job.note("skipped: an earlier step of this pipeline failed")
                continue
            self.run(job)

    def _group_failed(self, gid):
        g = self.groups.get(gid, {})
        if not g.get("stop_on_fail"):
            return False
        return any(self.jobs[j].group == gid and self.jobs[j].status in ("failed", "cancelled") for j in self.order)

    # ------------------------------------------------------------- the actual run
    def run(self, job, out=None):
        """Run every step of `job` in the project root. `out` (optional) receives raw output as it arrives."""
        job.status, job.started = "running", time.time()
        log_path = self.dir / "logs" / (job.id + ".log")
        env = {**os.environ, **job.env, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        env["PYTHONPATH"] = str(self.root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        code = worst = 0                  # worst: first non-zero exit code of any step, so one failed step fails the job
        for i, (label, argv) in enumerate(job.steps):
            if job.cancel_requested:
                break
            job.step_index = i
            cmd = [job.python] + argv
            job.note("$ " + T.display_cmd(argv, "python"), out)
            try:
                kw = dict(cwd=str(self.root), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                if IS_WIN:
                    kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    kw["start_new_session"] = True
                job.proc = subprocess.Popen(cmd, **kw)
            except OSError as e:
                job.note("could not start: %s" % e, out)
                code = worst = 127
                break
            if job.cancel_requested:          # cancel arrived while the process was starting
                kill_tree(job.proc)
            fd = job.proc.stdout
            while True:
                chunk = fd.read1(4096) if hasattr(fd, "read1") else fd.read(1)
                if not chunk:
                    break
                job.add_text(chunk.decode("utf-8", errors="replace"), out)
            code = job.proc.wait()
            worst = worst or code
            if job.live:
                job.add_text("\n", out)
            if job.cancel_requested:
                break
            if code != 0 and len(job.steps) > 1:
                job.note("(exit code %d)" % code, out)
        code = job.exit_code = worst
        job.ended = time.time()
        with job.lock:                   # lift the lab tools' data line out of the human log
            data = [l for l in job.lines if l.startswith("PQCTL_JSON ")]
            if data:
                try:
                    job.result = json.loads(data[-1][len("PQCTL_JSON "):])
                except ValueError:
                    job.result = {"error": "could not read the tool's result"}
                job.lines = [l for l in job.lines if not l.startswith("PQCTL_JSON ")]
        job.verdict = parse_verdict(job.lines)
        if job.cancel_requested:
            job.status = "cancelled"
        else:
            job.status = "passed" if code == 0 else "failed"
            if len(job.steps) > 1:
                nv = sum(1 for l in job.lines if l.strip() == "VERIFIED")
                nr = sum(1 for l in job.lines if l.strip() == "REJECTED")
                if nv or nr:
                    job.verdict = "%d VERIFIED, %d REJECTED" % (nv, nr) if nr else "all %d VERIFIED" % nv
            is_lab = bool(T.BY_ID.get(job.task_id, {}).get("lab"))
            if job.status == "passed" and verdict_tone(job.verdict, "passed") == "bad" and not is_lab:
                job.status = "failed"         # some scripts print FAILED but still exit 0
            if job.status == "failed":
                missing = sorted({m.group(1) for l in job.lines for m in [MISSING.search(l)] if m})
                if missing:
                    job.note("hint: not installed in this Python: %s (see Environment / python -m pqctl doctor)" % ", ".join(missing), out)
                    if not job.verdict or job.verdict in ("FAILED", "REJECTED"):
                        job.verdict = "missing " + ", ".join(missing)
        job.note("[%s] %s in %.1fs%s" % (job.status.upper(), job.title, job.ended - job.started,
                                         (" - " + job.verdict) if job.verdict else ""), out)
        try:
            log_path.write_text("\n".join(job.lines) + "\n", encoding="utf-8")
        except OSError:
            pass
        self._record(job)
        return job


def _wants_force(params):
    if not params:
        return False
    v = params.get("force")
    return v is True or str(v).lower() in ("1", "true", "yes", "y", "on")


def kill_tree(proc):
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            for _ in range(50):
                if proc.poll() is not None:
                    return
                time.sleep(0.1)
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass

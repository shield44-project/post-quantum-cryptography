"""Terminal interface. Run `python -m pqctl --help`.

    python -m pqctl                          interactive menu (phases -> tasks -> run)
    python -m pqctl serve [--port 8765]      web dashboard
    python -m pqctl status                   phase board
    python -m pqctl doctor                   environment check
    python -m pqctl list [--phase N]         every task id
    python -m pqctl run p5.verify --set model=runs/wm_v1/lam20_n256_rs32/seed1/model.pt
    python -m pqctl pipeline check-all       run a whole pipeline
    python -m pqctl colab p4.train           print a Colab cell for a GPU task
    python -m pqctl history                  last result of every task
"""
import argparse
import os
import sys
import time
from pathlib import Path

from pqctl import __version__
from pqctl import state as S
from pqctl import tasks as T
from pqctl.runner import Runner, kill_tree, verdict_tone

# ------------------------------------------------------------------ terminal styling
_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
if os.name == "nt" and _COLOR:
    os.system("")      # enables ANSI escape codes in Windows 10+ consoles


def c(text, code):
    return "\x1b[%sm%s\x1b[0m" % (code, text) if _COLOR else text


BOLD, DIM, OK, BAD, WARN, ACC = "1", "2", "38;5;84", "38;5;203", "38;5;214", "38;5;117"
TONE = {"ok": OK, "bad": BAD, "warn": WARN, "muted": DIM}
STATE = {"done": (OK, "done"), "partial": (WARN, "partial"), "missing": (DIM, "missing")}


def rule(title=""):
    w = min(96, max(40, _width()))
    t = (" %s " % title) if title else ""
    print(c("─" * 2 + t + "─" * max(0, w - len(t) - 2), DIM))


def _width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def find_root(start=None):
    p = Path(start or os.getcwd()).resolve()
    for d in [p, *p.parents]:
        if (d / "crypto").is_dir() and (d / "embedding").is_dir() and (d / "verify").is_dir():
            return d
    sys.exit(c("pqctl: run this from inside the post-quantum-cryptography project (or pass --root).", BAD))


# ------------------------------------------------------------------ commands
def cmd_status(r, args):
    rule("pqctl %s  ·  %s" % (__version__, r.root.name))
    gi = S.git_info(r.root)
    if gi["commit"]:
        print("  git  %s @ %s  %s" % (c(gi["branch"], ACC), gi["commit"], c(gi["subject"], DIM)))
    print()
    for ph in S.phases(r.root, r.history):
        col, word = STATE[ph["state"]]
        m = ph["metric"]
        metric = ("%s %s" % (c(m["value"], BOLD), c(m["label"], DIM))) if m else ""
        print("  %s  Phase %-2s %-28s %s  %s" % (c("●", col), ph["n"], ph["title"], c("%-8s" % word, col), metric))
    for f in T.FUTURE:
        print("  %s  Phase %-2s %-28s %s" % (c("○", DIM), f["n"], f["title"], c("planned", DIM)))
    print()


def cmd_doctor(r, args):
    rule("environment")
    d = S.doctor(r.root, r.settings, fresh=True)
    for ch in d["checks"]:
        mark = {"ok": c("OK  ", OK), "warn": c("WARN", WARN), "bad": c("FAIL", BAD)}[ch["state"]]
        print("  %s  %-26s %s" % (mark, ch["label"], c(ch["detail"], DIM)))
        if ch["fix"]:
            print("    %s %s" % (c("fix:", WARN), ch["fix"]))
    print()
    bad = sum(ch["state"] == "bad" for ch in d["checks"])
    print("  " + (c("ready", OK) if not bad else c("%d problem(s) to fix before every task can run" % bad, BAD)))
    print()


def cmd_list(r, args):
    met = S.doctor(r.root, r.settings)["met"]
    for ph in [p for p in T.PHASES if args.phase is None or p["n"] == args.phase]:
        rule("Phase %d · %s" % (ph["n"], ph["title"]))
        for t in [t for t in T.TASKS if t["phase"] == ph["n"]]:
            miss = S.missing_needs(t, met)
            flags = []
            if t["where"] == "colab":
                flags.append(c("GPU/Colab", WARN))
            if t.get("danger"):
                flags.append(c("overwrites with force", BAD))
            if miss:
                flags.append(c("needs " + ", ".join(miss), BAD))
            print("  %-18s %-40s %s %s" % (c(t["id"], ACC), t["title"], c(t["est"], DIM), " ".join(flags)))
    if args.phase is None:
        rule("lab tools (the dashboard's interactive pages)")
        for t in [t for t in T.TASKS if t["phase"] == "lab"]:
            print("  %-18s %-40s %s" % (c(t["id"], ACC), t["title"], c(t["est"], DIM)))
    rule("pipelines")
    for p in T.PIPELINES:
        print("  %-18s %-40s %s" % (c(p["id"], ACC), p["title"], c(p["est"], DIM)))
    print()


def parse_sets(pairs):
    out = {}
    for s in pairs or []:
        if "=" not in s:
            sys.exit(c("--set expects name=value, got '%s'" % s, BAD))
        k, v = s.split("=", 1)
        out[k.strip()] = v
    return out


class _HideData:
    """Pass output through to the terminal, except the lab tools' machine-readable PQCTL_JSON line."""
    def __init__(self):
        self.buf = ""

    def __call__(self, text):
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if not line.startswith("PQCTL_JSON "):
                sys.stdout.write(line + "\n")
        if self.buf and not "PQCTL_JSON ".startswith(self.buf[:11]) and not self.buf.startswith("PQCTL_JSON"):
            sys.stdout.write(self.buf)
            self.buf = ""
        sys.stdout.flush()


def _run_job(r, job):
    print()
    rule(job.title)
    try:
        r.run(job, out=_HideData())
    except KeyboardInterrupt:
        job.cancel_requested = True
        if job.proc:
            kill_tree(job.proc)
        job.status = "cancelled"
        print(c("\n  cancelled", WARN))
    tone = TONE[verdict_tone(job.verdict, job.status)]
    extra = (" · " + job.verdict) if job.verdict and job.verdict.upper() != job.status.upper() else ""
    print(c("  result: %s%s" % (job.status.upper(), extra), tone + ";1"))
    return job


def _confirm_danger(task, params, yes):
    if task.get("danger") and str(params.get("force", "")).lower() in ("1", "true", "yes", "y", "on"):
        print(c("  ! " + task["danger"], BAD))
        if yes:
            return True
        return input("  type OVERWRITE to continue: ").strip() == "OVERWRITE"
    return False


def cmd_run(r, args):
    t = T.BY_ID.get(args.task)
    if not t:
        sys.exit(c("unknown task '%s'. See: python -m pqctl list" % args.task, BAD))
    params = parse_sets(args.set)
    confirm = _confirm_danger(t, params, args.yes)
    try:
        job = r.make_job(args.task, params, confirm=confirm)
    except T.ParamError as e:
        sys.exit(c("  " + str(e), BAD))
    met = S.doctor(r.root, r.settings)["met"]
    miss = S.missing_needs(t, met)
    if miss:
        print(c("  ! missing: " + ", ".join(miss) + " (running anyway)", WARN))
    job = _run_job(r, job)
    sys.exit(0 if job.status == "passed" else 1)


def cmd_pipeline(r, args):
    p = T.PIPE_BY_ID.get(args.id)
    if not p:
        sys.exit(c("unknown pipeline '%s'. Options: %s" % (args.id, ", ".join(T.PIPE_BY_ID)), BAD))
    rule(p["title"])
    print("  " + p["what"])
    print("  steps: " + " → ".join(p["steps"]))
    stop = p["stop_on_fail"] and not args.keep_going
    done = []
    t0 = time.time()
    for tid in p["steps"]:
        try:
            job = r.make_job(tid)
        except T.ParamError as e:
            print(c("  skip %s: %s" % (tid, e), WARN))
            done.append((tid, "skipped", str(e)))
            continue
        try:
            job = _run_job(r, job)
        except KeyboardInterrupt:
            break
        done.append((tid, job.status, job.verdict or ""))
        if job.status == "cancelled" or (stop and job.status == "failed"):
            print(c("  stopping the pipeline (use --keep-going to continue past failures)", WARN))
            break
    print()
    rule("summary · %.0fs" % (time.time() - t0))
    for tid, st, v in done:
        col = OK if st == "passed" else (BAD if st == "failed" else WARN)
        print("  %s %-18s %-9s %s" % (c("●", col), tid, c(st, col), c(v, DIM)))
    print()
    sys.exit(0 if done and all(st == "passed" for _, st, _ in done) else 1)


def cmd_colab(r, args):
    t = T.BY_ID.get(args.task) or sys.exit(c("unknown task", BAD))
    p = T.clean_params(t, parse_sets(args.set), r.settings, r.root)
    print(T.colab_cell(t, p, r.root))


def cmd_history(r, args):
    rule("last result per task")
    for t in T.TASKS:
        h = r.history.get(t["id"])
        if not h:
            continue
        when = time.strftime("%d %b %H:%M", time.localtime(h["ended"])) if h.get("ended") else ""
        print("  %s %-18s %-10s %-28s %s" % (c("●", TONE[h["tone"]]), t["id"], h["status"], h.get("verdict") or "", c(when, DIM)))
    print()


def cmd_serve(r, args):
    from pqctl.server import serve
    serve(r.root, args.port, not args.no_browser)


# ------------------------------------------------------------------ interactive menu
def _ask(prompt, default=""):
    try:
        v = input(prompt)
    except EOFError:
        raise KeyboardInterrupt
    return v.strip() or default


def menu(r):
    while True:
        cmd_status(r, None)
        print("  " + "  ".join([c("[0-7]", ACC) + " open a phase", c("[a]", ACC) + " run every check",
                                c("[d]", ACC) + " doctor", c("[w]", ACC) + " web dashboard", c("[q]", ACC) + " quit"]))
        ch = _ask(c("\n  › ", ACC)).lower()
        if ch in ("q", "quit", "exit"):
            return
        if ch == "d":
            cmd_doctor(r, None)
            _ask(c("  enter to go back ", DIM))
        elif ch == "w":
            return cmd_serve(r, argparse.Namespace(port=8765, no_browser=False))
        elif ch == "a":
            try:
                cmd_pipeline(r, argparse.Namespace(id="check-all", keep_going=True))
            except SystemExit:
                pass
            _ask(c("  enter to go back ", DIM))
        elif ch.isdigit() and int(ch) in [p["n"] for p in T.PHASES]:
            phase_menu(r, int(ch))


def phase_menu(r, n):
    ph = next(p for p in T.PHASES if p["n"] == n)
    tasks = [t for t in T.TASKS if t["phase"] == n]
    while True:
        rule("Phase %d · %s" % (n, ph["title"]))
        print("  " + c(ph["plain"], DIM) + "\n")
        for i, t in enumerate(tasks, 1):
            h = r.history.get(t["id"])
            last = c(" last: %s %s" % (h["status"], h.get("verdict") or ""), TONE[h["tone"]]) if h else ""
            tag = c(" GPU/Colab", WARN) if t["where"] == "colab" else ""
            print("  %s %-38s %s%s%s" % (c("[%d]" % i, ACC), t["title"], c(t["est"], DIM), tag, last))
        ch = _ask(c("\n  pick a task, [b] back › ", ACC)).lower()
        if ch in ("b", ""):
            return
        if ch.isdigit() and 1 <= int(ch) <= len(tasks):
            task_menu(r, tasks[int(ch) - 1])


def task_menu(r, t):
    rule(t["title"])
    print("  " + t["what"])
    if t.get("danger"):
        print(c("  ! " + t["danger"], BAD))
    if t["where"] == "colab":
        print(c("  This needs a GPU to finish in reasonable time. [c] prints the Colab cell.", WARN))
    params = {}
    for p in t.get("params", []):
        d = T.defaults(t, r.settings)[p["name"]]
        shown = " ".join(map(str, d)) if isinstance(d, list) else ("yes" if d is True else "no" if d is False else d)
        if p.get("choices"):
            print(c("    options: " + ", ".join(p["choices"]), DIM))
        v = _ask("  %s [%s]: " % (p["label"], shown))
        if v:
            params[p["name"]] = v
    try:
        job_preview = r.make_job(t["id"], params, confirm=True)
    except T.ParamError as e:
        print(c("  " + str(e), BAD))
        return
    for cmd in job_preview.summary()["commands"]:
        print(c("  $ " + cmd, DIM))
    ch = _ask(c("  [enter] run   [c] Colab cell   [b] back › ", ACC)).lower()
    if ch == "c":
        print("\n" + T.colab_cell(t, job_preview.params, r.root) + "\n")
        _ask(c("  enter to go back ", DIM))
        return
    if ch == "b":
        return
    if not _confirm_danger(t, params, False) and t.get("danger") and params.get("force"):
        print(c("  not confirmed", WARN))
        return
    _run_job(r, job_preview)
    _ask(c("  enter to go back ", DIM))


# ------------------------------------------------------------------ entry
def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m pqctl", description="Control centre for the PQ watermarking project.")
    ap.add_argument("--root", help="project folder (default: found from the current folder)")
    ap.add_argument("--version", action="version", version="pqctl " + __version__)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="start the web dashboard")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")
    sub.add_parser("status", help="phase board")
    sub.add_parser("doctor", help="environment check")
    s = sub.add_parser("list", help="every task and pipeline")
    s.add_argument("--phase", type=int)
    s = sub.add_parser("run", help="run one task")
    s.add_argument("task")
    s.add_argument("--set", action="append", metavar="NAME=VALUE")
    s.add_argument("--yes", action="store_true", help="confirm tasks that overwrite files")
    s = sub.add_parser("pipeline", help="run a pipeline: " + ", ".join(T.PIPE_BY_ID))
    s.add_argument("id")
    s.add_argument("--keep-going", action="store_true")
    s = sub.add_parser("colab", help="print the Colab cell for a task")
    s.add_argument("task")
    s.add_argument("--set", action="append", metavar="NAME=VALUE")
    sub.add_parser("history", help="last result of every task")
    sub.add_parser("menu", help="interactive menu")
    args = ap.parse_args(argv)

    r = Runner(find_root(args.root))
    fns = {"serve": cmd_serve, "status": cmd_status, "doctor": cmd_doctor, "list": cmd_list, "run": cmd_run,
           "pipeline": cmd_pipeline, "colab": cmd_colab, "history": cmd_history}
    if args.cmd in fns:
        return fns[args.cmd](r, args)
    if sys.stdin.isatty():
        try:
            return menu(r)
        except KeyboardInterrupt:
            print()
            return
    cmd_status(r, args)


if __name__ == "__main__":
    main()

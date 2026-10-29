"""The dashboard's local web server (standard library only).

Listens on 127.0.0.1 only. Every POST needs the per-start token embedded in the page, and requests whose Host or
Origin is not this machine are refused, so other websites cannot start jobs on your computer.
"""
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pqctl import __version__
from pqctl import state as S
from pqctl import tasks as T
from pqctl.runner import Runner

STATIC = Path(__file__).parent / "static"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".svg": "image/svg+xml"}


def task_view(t, settings, met):
    d = {k: v for k, v in t.items() if k not in ("build", "argv")}
    d["defaults"] = T.defaults(t, settings)
    d["missing"] = S.missing_needs(t, met) if met else []
    d["multi"] = "build" in t
    return d


class App:
    def __init__(self, root, port):
        self.root = Path(root).resolve()
        self.port = port
        self.runner = Runner(self.root)
        self.token = secrets.token_urlsafe(24)
        self._met, self._met_at = {}, 0

    def met(self, fresh=False):
        if fresh or time.time() - self._met_at > 120:
            self._doc = S.doctor(self.root, self.runner.settings, fresh)
            self._met, self._met_at = self._doc["met"], time.time()
        return self._met

    # --------------------------------------------------------------- GET handlers
    def overview(self, q):
        r = self.runner
        jobs = [r.jobs[j].summary() for j in reversed(r.order)]
        return {"version": __version__, "root": str(self.root), "git": S.git_info(self.root),
                "phases": S.phases(self.root, r.history), "future": T.FUTURE,
                "pipelines": T.PIPELINES, "jobs": jobs[:12],
                "running": next((j for j in jobs if j["status"] == "running"), None),
                "queued": sum(1 for j in jobs if j["status"] == "queued")}

    def tasks(self, q):
        met = self.met()
        return {"tasks": [task_view(t, self.runner.settings, met) for t in T.TASKS], "needs": T.NEEDS,
                "history": self.runner.history, "met": met}

    def doctor(self, q):
        fresh = q.get("fresh", ["0"])[0] == "1"
        self.met(fresh=True if fresh else False)
        return {**self._doc, "settings": self.runner.settings}

    def inspect(self, q):
        return S.inspect(self.root)

    def models(self, q):
        return {"models": S.models(self.root)}

    def results(self, q):
        return {"baseline": S.baseline(self.root), "phase4": S.phase4(self.root), "phase6": S.phase6(self.root), "phase7": S.phase7(self.root),
                "docs": [d for d in S.DOCS if (self.root / d).exists()]}

    def jobs(self, q):
        r = self.runner
        return {"jobs": [r.jobs[j].summary() for j in reversed(r.order)], "groups": r.groups}

    def job(self, jid, q):
        j = self.runner.jobs.get(jid)
        if not j:
            return None
        since = int(q.get("since", ["0"])[0] or 0)
        with j.lock:
            lines, live = j.lines[since:], j.live
        out = {**j.summary(), "since": since, "new": lines, "live": live}
        if j.result is not None and j.status not in ("running", "queued"):
            out["result"] = j.result
        return out

    def colab(self, q):
        t = T.BY_ID.get(q.get("task", [""])[0])
        if not t:
            raise T.ParamError("unknown task")
        params = json.loads(q.get("params", ["{}"])[0] or "{}")
        p = T.clean_params(t, params, self.runner.settings, self.root)
        return {"cell": T.colab_cell(t, p, self.root)}

    # --------------------------------------------------------------- POST handlers
    def preview(self, body):
        t = T.BY_ID.get(body.get("task"))
        if not t:
            raise T.ParamError("unknown task")
        p = T.clean_params(t, body.get("params"), self.runner.settings, self.root)
        return {"commands": [T.display_cmd(a, "python") for _, a in T.steps_for(t, p, self.root)]}

    def run(self, body):
        t = T.BY_ID.get(body.get("task"), {})
        quick = t.get("cost") == "seconds" or bool(t.get("lab"))
        job = self.runner.submit_task(body.get("task"), body.get("params"), confirm=bool(body.get("confirm")),
                                      front=bool(body.get("priority")) and quick)
        return {"job": job.summary()}

    def pipeline(self, body):
        gid, jobs, problems = self.runner.submit_pipeline(body.get("id"))
        return {"group": gid, "jobs": [j.summary() for j in jobs], "problems": problems}

    def cancel(self, body):
        if body.get("group"):
            self.runner.cancel_group(body["group"])
            return {"ok": True}
        return {"ok": self.runner.cancel(body.get("job", ""))}

    def settings(self, body):
        s = self.runner.set_settings(body or {})
        self._met_at = 0
        return {"settings": s}


def make_handler(app):
    allowed_hosts = {"127.0.0.1:%d" % app.port, "localhost:%d" % app.port}

    class H(BaseHTTPRequestHandler):
        server_version = "pqctl/" + __version__

        def log_message(self, fmt, *a):      # keep the terminal quiet
            pass

        def _send(self, code, body, ctype="application/json", extra=None):
            data = body if isinstance(body, bytes) else (json.dumps(body).encode() if ctype == "application/json" else body.encode())
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _host_ok(self):
            if self.headers.get("Host") not in allowed_hosts:
                self._send(403, {"error": "bad host"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in ("http://" + h for h in allowed_hosts):
                self._send(403, {"error": "bad origin"})
                return False
            return True

        def do_GET(self):
            if not self._host_ok():
                return
            u = urlparse(self.path)
            q = parse_qs(u.query)
            path = u.path
            try:
                if path in ("/", "/index.html"):
                    html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__PQCTL_TOKEN__", app.token)
                    return self._send(200, html, TYPES[".html"], {
                        "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; "
                                                   "font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"})
                if path.startswith("/static/"):
                    f = (STATIC / path[len("/static/"):]).resolve()
                    if STATIC.resolve() in f.parents and f.is_file() and f.suffix in TYPES:
                        return self._send(200, f.read_bytes(), TYPES[f.suffix])
                    return self._send(404, {"error": "not found"})
                if path == "/api/file":
                    f = S.safe_file(app.root, q.get("path", [""])[0])
                    if not f:
                        return self._send(404, {"error": "not available"})
                    return self._send(200, f.read_bytes(), S.SERVABLE[f.suffix])
                if path.startswith("/api/jobs/"):
                    r = app.job(path[len("/api/jobs/"):], q)
                    return self._send(200 if r else 404, r or {"error": "no such job"})
                routes = {"/api/overview": app.overview, "/api/tasks": app.tasks, "/api/doctor": app.doctor,
                          "/api/models": app.models, "/api/results": app.results, "/api/inspect": app.inspect, "/api/jobs": app.jobs, "/api/colab": app.colab}
                if path in routes:
                    return self._send(200, routes[path](q))
                return self._send(404, {"error": "not found"})
            except T.ParamError as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:  # pragma: no cover
                return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def do_POST(self):
            if not self._host_ok():
                return
            if not secrets.compare_digest(self.headers.get("X-PQCTL-Token", ""), app.token):
                return self._send(403, {"error": "missing or wrong token; reload the page"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(min(n, 1_000_000)) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._send(400, {"error": "bad JSON"})
            routes = {"/api/run": app.run, "/api/pipeline": app.pipeline, "/api/cancel": app.cancel,
                      "/api/settings": app.settings, "/api/preview": app.preview}
            fn = routes.get(urlparse(self.path).path)
            if not fn:
                return self._send(404, {"error": "not found"})
            try:
                return self._send(200, fn(body))
            except T.ParamError as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:  # pragma: no cover
                return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

    return H


def serve(root, port=8765, open_browser=True):
    app = App(root, port)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    httpd.daemon_threads = True
    url = "http://127.0.0.1:%d/" % port
    print("\n  pqctl %s  |  project %s" % (__version__, app.root))
    print("  dashboard  %s   (local only, Ctrl+C to stop)\n" % url)
    threading.Thread(target=app.met, daemon=True).start()     # warm the environment probe
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopping; cancelling running jobs")
        for jid in list(app.runner.order):
            if app.runner.jobs[jid].status in ("running", "queued"):
                app.runner.cancel(jid)
    finally:
        httpd.server_close()

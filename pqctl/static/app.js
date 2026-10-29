/* pqctl dashboard. Plain JS, no build step. Everything is built with DOM APIs (textContent), never innerHTML. */
(() => {
  "use strict";
  const TOKEN = document.querySelector('meta[name="pqctl-token"]').content;
  const $ = (s, el = document) => el.querySelector(s);
  const view = $("#view");
  const S = { tasks: null, met: {}, history: {}, models: null, dockJob: null, dockSince: 0, dockLines: [], dockTimer: null,
              lastRunning: null, verifyJob: null, results: null, resultsTab: "charts", sort: { key: null, dir: 1 }, filter: "all" };

  // ------------------------------------------------------------------ helpers
  // replaceChildren/append turn null into the text "null"; pages pass null for "nothing here", so skip those.
  for (const proto of [Element.prototype, DocumentFragment.prototype]) {
    for (const name of ["replaceChildren", "append", "prepend"]) {
      const orig = proto[name];
      proto[name] = function (...kids) { return orig.apply(this, kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)); };
    }
  }
  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "style") Object.assign(el.style, v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  async function api(path, body) {
    const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-PQCTL-Token": TOKEN }, body: JSON.stringify(body) };
    const r = await fetch(path, opt);
    let data = null;
    try { data = await r.json(); } catch (e) { data = { error: "bad response" }; }
    if (!r.ok) throw new Error(data && data.error ? data.error : "request failed (" + r.status + ")");
    return data;
  }
  function toast(msg, tone = "") {
    const t = h("div", { class: "toast " + tone, text: msg });
    $("#toasts").append(t);
    setTimeout(() => t.remove(), tone === "bad" ? 7000 : 3500);
  }
  const pct = (x, d = 1) => (x === null || x === undefined || isNaN(x)) ? "—" : (100 * x).toFixed(d) + "%";
  const fix = (x, d = 1) => { if (x === null || x === undefined || isNaN(x)) return "—"; const v = Number(x).toFixed(d); return /^-0\.?0*$/.test(v) ? v.slice(1) : v; };
  const ago = (t) => {
    if (!t) return "";
    const s = Math.round(Date.now() / 1000 - t);
    if (s < 60) return s + "s ago";
    if (s < 3600) return Math.round(s / 60) + " min ago";
    if (s < 86400) return Math.round(s / 3600) + " h ago";
    return new Date(t * 1000).toLocaleDateString();
  };
  const dur = (a, b) => {
    if (!a) return "";
    const s = Math.max(0, Math.round((b || Date.now() / 1000) - a));
    return s < 60 ? s + "s" : s < 3600 ? Math.floor(s / 60) + "m " + (s % 60) + "s" : Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
  };
  function statusChip(job) {
    const map = { running: "acc running", queued: "", passed: "ok", failed: "bad", cancelled: "warn", skipped: "" };
    return h("span", { class: "chip " + (map[job.status] || ""), text: job.status });
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast("Copied", "ok"); }
    catch (e) { toast("Copy failed; select the text instead", "bad"); }
  }
  function modal({ title, body, ok = "Continue", danger = false, typeword = null }) {
    return new Promise((resolve) => {
      const m = $("#modal");
      $("#modal-title").textContent = title;
      const b = $("#modal-body");
      b.replaceChildren(...(Array.isArray(body) ? body : [body]));
      const okb = $("#modal-ok");
      okb.textContent = ok;
      okb.className = "btn " + (danger ? "danger" : "primary");
      let input = null;
      if (typeword) {
        input = h("input", { type: "text", class: "search", placeholder: "type " + typeword, "aria-label": "Confirmation" });
        b.append(h("div", { class: "field" }, h("label", { text: "Type " + typeword + " to confirm" }), input));
        okb.disabled = true;
        input.addEventListener("input", () => { okb.disabled = input.value.trim() !== typeword; });
      } else okb.disabled = false;
      m.hidden = false;
      (input || okb).focus();
      const done = (v) => { m.hidden = true; okb.onclick = null; $("#modal-cancel").onclick = null; resolve(v); };
      okb.onclick = () => done(true);
      $("#modal-cancel").onclick = () => done(false);
      m.onclick = (e) => { if (e.target === m) done(false); };
      m.onkeydown = (e) => { if (e.key === "Escape") done(false); };
    });
  }

  // ------------------------------------------------------------------ data
  async function loadTasks(force) {
    if (S.tasks && !force) return S.tasks;
    const d = await api("/api/tasks");
    S.tasks = d.tasks; S.met = d.met; S.history = d.history; S.needs = d.needs;
    return S.tasks;
  }
  async function loadModels() {
    if (!S.models) S.models = (await api("/api/models")).models;
    return S.models;
  }

  // ------------------------------------------------------------------ router
  const ROUTES = { overview: renderOverview, test: renderTest, demo: () => location.replace("#test"), phase: renderPhase, results: renderResults, jobs: renderJobs, env: renderEnv };
  async function route() {
    const [name, arg] = (location.hash.slice(1) || "overview").split("/");
    const fn = ROUTES[name] || renderOverview;
    document.querySelectorAll(".nav a").forEach((a) => { const href = a.getAttribute("href");
      a.classList.toggle("on", href === "#" + (arg !== undefined ? name + "/" + arg : name) || (name === "labs" && arg !== "results" && href === "#labs")); });
    document.body.classList.remove("rail-open");
    try { await fn(arg); }
    catch (e) { view.replaceChildren(h("div", { class: "empty", text: "Could not load this page: " + e.message })); }
    view.focus({ preventScroll: true });
  }
  function crumbs(...parts) {
    $("#crumbs").replaceChildren(...parts.map((p, i) => i === parts.length - 1 ? h("b", { text: p }) : h("span", {}, p, h("span", { class: "faint", text: "  /" }))));
  }

  // ------------------------------------------------------------------ shell refresh (rail, running job)
  async function refreshShell() {
    try {
      const o = await api("/api/overview");
      const g = o.git || {};
      $("#git-pill").textContent = g.commit ? (g.branch + " @ " + g.commit + (g.dirty ? " *" : "")) : "no git";
      const np = $("#nav-phases");
      if (!np.childElementCount) {
        for (const p of o.phases) np.append(h("a", { href: "#phase/" + p.n, "data-route": "phase" }, h("span", { class: "pnum", text: p.n }), p.title, h("span", { class: "sdot " + p.state, "data-phase-dot": p.n })));
        route();
      } else for (const p of o.phases) { const d = np.querySelector('[data-phase-dot="' + p.n + '"]'); if (d) d.className = "sdot " + p.state; }
      const rj = $("#rail-job");
      if (o.running) {
        rj.hidden = false;
        $("#rail-job-title").textContent = o.running.title;
        $("#rail-job-sub").textContent = dur(o.running.started) + (o.queued ? "  ·  " + o.queued + " queued" : "");
        rj.onclick = () => openDock(o.running.id);
      } else rj.hidden = true;
      if (o.running && !$("#dock").hidden && S.dockDone && S.dockJob !== o.running.id) openDock(o.running.id);   // follow whatever is running
      const prev = S.lastRunning;
      S.lastRunning = o.running ? o.running.id : null;
      if (prev && prev !== S.lastRunning) onJobFinished();
      $("#nav-jobs-count").textContent = o.jobs.length ? String(o.jobs.length) : "";
    } catch (e) { /* server stopped: keep last state */ }
  }
  async function onJobFinished() {
    const d = await api("/api/tasks").catch(() => null);
    if (!d) return;
    S.history = d.history;
    document.querySelectorAll("[data-last]").forEach((el) => fillLast(el, el.getAttribute("data-last")));
    const [name] = (location.hash.slice(1) || "overview").split("/");
    if (name === "overview" || name === "jobs") route();
  }

  // ------------------------------------------------------------------ overview
  async function renderOverview() {
    crumbs("Overview");
    const [o, r] = await Promise.all([api("/api/overview"), api("/api/results")]);
    const t = r.phase6.totals;
    const done = o.phases.filter((p) => p.state === "done").length;
    const base = r.baseline.map((b) => b.acc).filter(Boolean);
    const p4 = r.phase4.find((x) => x.config === "rs32/features.6.0/lam20");
    const stats = h("div", { class: "stats" },
      stat(done + "/" + o.phases.length, "phases complete"),
      stat(base.length ? pct(base.reduce((a, b) => a + b, 0) / base.length) : "—", "baseline accuracy"),
      stat(p4 ? fix(p4.diff_pts) + " pts" : "—", "accuracy cost of the watermark"),
      stat(t ? t.wm_verified + "/" + t.wm_runs : "—", "attacked copies still verified", "ok"),
      stat(t ? t.base_false_accepts + "/" + t.base_runs : "—", "unsigned models accepted", t && t.base_false_accepts === 0 ? "ok" : "bad"),
      stat(t ? String(t.removed_types) : "—", "attack types that removed it", t && t.removed_types ? "bad" : "ok"));

    const pipes = h("div", { class: "grid" }, o.pipelines.map((p) => h("div", { class: "card pipe" },
      h("div", { class: "section-head" }, h("h3", { text: p.title }), p.id === "rebuild" ? h("span", { class: "chip warn", text: "GPU recommended" }) : null),
      h("p", { class: "what", text: p.what }),
      h("div", { class: "flow" }, p.steps.map((s) => h("span", { text: s }))),
      h("div", { class: "foot" }, h("span", { class: "est", text: p.est }),
        h("button", { class: "btn " + (p.id === "check-all" ? "primary" : ""), type: "button", text: "Run", onclick: () => runPipeline(p) })))));

    const track = h("div", { class: "track" },
      o.phases.map((p) => h("a", { class: "phase " + p.state, href: "#phase/" + p.n },
        h("div", { class: "n" }, h("span", { class: "sdot " + p.state }), "PHASE " + p.n),
        h("div", { class: "t", text: p.title }),
        p.metric ? [h("div", { class: "m", text: p.metric.value }), h("div", { class: "ml", text: p.metric.label })] : h("div", { class: "ml", text: p.plain }))),
      o.future.map((p) => h("div", { class: "phase future" }, h("div", { class: "n", text: "PHASE " + p.n }), h("div", { class: "t", text: p.title }), h("div", { class: "ml", text: p.plain }))));

    view.replaceChildren(
      h("div", { class: "hero" }, h("span", { class: "eyebrow", text: "Post-Quantum AI Provenance Watermarking" }),
        h("h1", { text: "Every phase, one place" }),
        h("p", { text: "An ML-DSA signed manifest bound to a CIFAR-10 CNN by a 256-bit watermark in its weights. Run any phase, watch it live, and check the results. Jobs run one at a time on this computer, in this project folder." })),
      stats,
      h("section", { class: "section" }, h("div", { class: "section-head" }, h("h2", { text: "Phases" }), h("span", { class: "muted", text: "click a phase to run its steps" })), track),
      h("section", { class: "section" }, h("div", { class: "section-head" }, h("h2", { text: "Run many steps at once" })), pipes),
      h("section", { class: "section" }, h("div", { class: "section-head" }, h("h2", { text: "Recent jobs" }), h("a", { href: "#jobs", class: "muted", text: "all jobs →" })),
        o.jobs.length ? jobsTable(o.jobs.slice(0, 6)) : h("div", { class: "empty", text: "No jobs yet. Try “Run every check”." })));
  }
  function stat(v, l, tone = "") { return h("div", { class: "stat" }, h("div", { class: "v " + tone, text: v }), h("div", { class: "l", text: l })); }

  async function runPipeline(p) {
    if (p.id === "rebuild") {
      const ok = await modal({ title: "Rebuild everything?", ok: "Start rebuild", danger: true,
        body: [h("p", { text: "This trains every model again (baselines, Phase 3, Phase 4, attacks). On a laptop CPU it can take a day. Finished runs are skipped, so it only redoes what is missing." }),
               h("p", { text: "For speed, run the training steps on Colab instead (each GPU step has a Colab cell button)." })] });
      if (!ok) return;
    }
    try {
      const r = await api("/api/pipeline", { id: p.id });
      if (r.problems.length) toast("Skipped: " + r.problems.join("; "), "bad");
      toast(p.title + ": " + r.jobs.length + " steps queued", "ok");
      if (r.jobs.length) openDock(r.jobs[0].id);
      refreshShell();
    } catch (e) { toast(e.message, "bad"); }
  }

  // ------------------------------------------------------------------ phase page
  async function renderPhase(n) {
    n = Number(n);
    const [o, tasks] = await Promise.all([api("/api/overview"), loadTasks(true)]);
    const ph = o.phases.find((p) => p.n === n);
    if (!ph) return renderOverview();
    crumbs("Phases", "Phase " + n + " · " + ph.title);
    const mine = tasks.filter((t) => t.phase === n);
    const chip = { done: ["ok", "complete"], partial: ["warn", "partly done"], missing: ["", "not started"] }[ph.state];
    view.replaceChildren(
      h("div", { class: "phase-head" },
        h("span", { class: "eyebrow", text: "Phase " + n }),
        h("div", { class: "row" }, h("h1", { text: ph.title }), h("span", { class: "chip " + chip[0], text: chip[1] }),
          ph.metric ? h("span", { class: "chip acc", text: ph.metric.value + " · " + ph.metric.label }) : null),
        h("p", { class: "muted", text: ph.plain }),
        h("div", { class: "artifacts" }, ph.artifacts.map((a) => h("span", { class: ph.have.includes(a) ? "have" : "miss", text: a })))),
      h("div", { class: "grid wide" }, await Promise.all(mine.map(renderTask))));
  }

  function fillLast(el, tid) {
    const hst = S.history[tid];
    if (!hst) { el.replaceChildren(h("span", { class: "faint", text: "never run here" })); return; }
    el.replaceChildren(h("span", { class: "chip " + hst.tone, text: hst.status }), hst.verdict ? h("span", { text: hst.verdict }) : null,
      h("span", { class: "faint", text: ago(hst.ended) }),
      h("button", { class: "btn ghost sm", type: "button", text: "log", onclick: () => openDock(hst.job) }));
  }

  async function renderTask(t) {
    const fields = {};
    const form = h("div", { class: "form" });
    const needModels = (t.params || []).some((p) => p.type === "model");
    const models = needModels ? await loadModels() : [];
    for (const p of t.params || []) {
      const def = t.defaults[p.name];
      let input, wrap;
      if (p.type === "bool") {
        input = h("input", { type: "checkbox", id: t.id + "-" + p.name });
        input.checked = !!def;
        wrap = h("div", { class: "field check" }, input, h("label", { for: input.id, text: p.label }));
      } else if (p.type === "choices") {
        const boxes = p.choices.map((c) => { const cb = h("input", { type: "checkbox", value: c }); cb.checked = (def || []).includes(c); return h("label", {}, cb, c); });
        input = { get value() { return boxes.map((l) => l.firstChild).filter((c) => c.checked).map((c) => c.value); }, addEventListener: (ev, fn) => boxes.forEach((b) => b.addEventListener("change", fn)) };
        wrap = h("div", { class: "field", style: { gridColumn: "1 / -1" } }, h("label", { text: p.label }), h("div", { class: "multi" }, boxes));
      } else if (p.type === "choice") {
        input = h("select", { id: t.id + "-" + p.name }, p.choices.map((c) => h("option", { value: c, text: c })));
        input.value = def;
        wrap = h("div", { class: "field", style: { gridColumn: "1 / -1" } }, h("label", { for: input.id, text: p.label }), input);
      } else {
        const listId = p.type === "model" ? "models-" + t.id + "-" + p.name : null;
        input = h("input", { type: "text", id: t.id + "-" + p.name, list: listId, spellcheck: "false", autocomplete: "off" });
        input.value = Array.isArray(def) ? def.join(" ") : (def ?? "");
        wrap = h("div", { class: "field", style: p.type === "model" ? { gridColumn: "1 / -1" } : null },
          h("label", { for: input.id, text: p.label }), input,
          listId ? h("datalist", { id: listId }, models.filter((m) => !m.attack).map((m) => h("option", { value: m.path }))) : null);
      }
      fields[p.name] = input;
      form.append(wrap);
    }
    const collect = () => {
      const out = {};
      for (const [k, el] of Object.entries(fields)) out[k] = el.type === "checkbox" ? el.checked : el.value;
      return out;
    };
    const cmd = h("div", { class: "cmd", text: "…" });
    let timer = null;
    const preview = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        try { cmd.textContent = (await api("/api/preview", { task: t.id, params: collect() })).commands.join("\n"); cmd.classList.remove("bad"); }
        catch (e) { cmd.textContent = e.message; }
      }, 200);
    };
    Object.values(fields).forEach((el) => { el.addEventListener("input", preview); el.addEventListener("change", preview); });
    preview();

    const badges = h("div", { class: "badges" },
      h("span", { class: "chip", text: t.est }),
      t.where === "colab" ? h("span", { class: "chip warn", text: "GPU recommended" }) : h("span", { class: "chip", text: "local" }),
      (t.missing || []).map((m) => h("span", { class: "chip bad", text: "needs " + m })));
    const last = h("div", { class: "last", "data-last": t.id });
    fillLast(last, t.id);
    const runBtn = h("button", { class: "btn primary", type: "button", text: "Run", onclick: () => runTask(t, collect) });
    return h("div", { class: "card task", "data-task": t.id },
      h("div", { class: "task-top" },
        h("div", { class: "left" }, h("span", { class: "id", text: t.id }), h("h3", { text: t.title }), h("p", { class: "what", text: t.what }))),
      badges,
      t.danger ? h("div", { class: "warnbox", text: "Warning: " + t.danger }) : null,
      (t.params || []).length ? h("details", { class: "opts", open: t.where === "colab" || needModels ? true : null }, h("summary", { text: "Options" }), form) : null,
      cmd,
      h("div", { class: "task-foot" }, last,
        h("button", { class: "btn ghost sm", type: "button", text: "Colab cell", onclick: () => showColab(t, collect()) }),
        runBtn));
  }

  async function runTask(t, collect) {
    const params = collect();
    let confirm = false;
    if (t.danger && params.force) {
      confirm = await modal({ title: "Overwrite files?", danger: true, ok: "Overwrite", typeword: "OVERWRITE", body: h("p", { text: t.danger }) });
      if (!confirm) return;
    }
    if (t.where === "colab") {
      const ok = await modal({ title: "This step trains models", ok: "Run here anyway",
        body: [h("p", { text: t.title + " takes " + t.est + ". On a CPU it can run for hours. The Colab cell button gives you the same command for a free GPU." })] });
      if (!ok) return;
    }
    if ((t.missing || []).length) {
      const ok = await modal({ title: "Something is missing", ok: "Run anyway",
        body: [h("p", { text: "This step needs: " + t.missing.join(", ") + ". It will probably fail. See Environment for how to fix it." })] });
      if (!ok) return;
    }
    try {
      const r = await api("/api/run", { task: t.id, params, confirm, priority: true });
      openDock(r.job.id);
      refreshShell();
    } catch (e) { toast(e.message, "bad"); }
  }

  async function showColab(t, params) {
    try {
      const q = new URLSearchParams({ task: t.id, params: JSON.stringify(params) });
      const r = await api("/api/colab?" + q);
      const pre = h("pre", { class: "cmd", style: { whiteSpace: "pre", maxHeight: "300px" }, text: r.cell });
      pre.classList.remove("cmd");
      pre.className = "term";
      pre.style.border = "1px solid var(--line)"; pre.style.borderRadius = "8px";
      const ok = await modal({ title: "Colab cell · " + t.title, ok: "Copy cell",
        body: [h("p", { text: "Paste into a Colab notebook with a T4 GPU runtime. The project must be in My Drive/pq-watermark." }), pre] });
      if (ok) copy(r.cell);
    } catch (e) { toast(e.message, "bad"); }
  }

  // ------------------------------------------------------------------ dock (live job output)
  function classify(line) {
    if (line.startsWith("$ ")) return "cmdline";
    if (/^\[(PASSED)\]|\bVERIFIED\b|\bPASSED\b|^PASS\b| passed\b/.test(line) && !/\bfailed\b|FAIL\b/.test(line)) return "ok";
    if (/^\[(FAILED|CANCELLED)\]|REJECTED|\bFAILED\b|^FAIL\b|Traceback|Error\b|\bfailed\b/.test(line)) return "bad";
    if (/WARNING|^SKIP|skipped|NOTE/.test(line)) return "warn";
    return "";
  }
  function showDock() {
    $("#dock").hidden = false;
    document.body.classList.add("docked");
    $("#term-toggle").setAttribute("aria-pressed", "true");
    try { localStorage.setItem("pqctl.dockClosed", "0"); } catch (e) { /* ignore */ }
  }
  function idleDock() {
    clearTimeout(S.dockTimer);
    S.dockJob = null; S.dockDone = true; S.dockLines = [];
    $("#dock-name").textContent = "Terminal";
    $("#dock-status").replaceWith(Object.assign(h("span", { class: "chip", text: "idle" }), { id: "dock-status" }));
    $("#dock-time").textContent = "";
    $("#dock-steps").replaceChildren();
    $("#dock-cancel").hidden = true;
    $("#dock-verdict").className = "verdict muted";
    $("#dock-verdict").textContent = "waiting for a job";
    $("#term").replaceChildren(h("span", { class: "dim", text: "No job is running. The live output of anything you run (a step, a pipeline, a lab tool) appears here.\nPress F for full screen." }), h("span", { class: "live" }));
    showDock();
  }
  async function openDock(jobId) {
    if (!jobId) return;
    clearTimeout(S.dockTimer);
    S.dockJob = jobId; S.dockSince = 0; S.dockLines = []; S.dockDone = false;
    $("#term").replaceChildren(h("span", { class: "live" }));
    showDock();
    pollDock();
  }
  function closeDock() {
    if ($("#dock").classList.contains("full")) { $("#dock").classList.remove("full"); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); }
    clearTimeout(S.dockTimer);
    S.dockJob = null;
    $("#dock").hidden = true;
    document.body.classList.remove("docked");
    $("#term-toggle").setAttribute("aria-pressed", "false");
    try { localStorage.setItem("pqctl.dockClosed", "1"); } catch (e) { /* ignore */ }
  }
  async function pollDock() {
    const id = S.dockJob;
    if (!id) return;
    let j;
    try { j = await api("/api/jobs/" + id + "?since=" + S.dockSince); }
    catch (e) { $("#dock-name").textContent = "job not found (server restarted?)"; return; }
    if (id !== S.dockJob) return;
    const term = $("#term");
    const live = term.lastChild;
    if (j.new.length) {
      const frag = document.createDocumentFragment();
      for (const line of j.new) {
        S.dockLines.push(line);
        const cls = classify(line);
        frag.append(cls ? h("span", { class: cls, text: line }) : document.createTextNode(line), "\n");
      }
      term.insertBefore(frag, live);
      S.dockSince = j.since + j.new.length;
    }
    live.textContent = j.live || "";
    if ($("#follow").checked) term.scrollTop = term.scrollHeight;
    $("#dock-name").textContent = j.title;
    $("#dock-status").replaceWith(Object.assign(statusChip(j), { id: "dock-status" }));
    $("#dock-time").textContent = j.started ? dur(j.started, j.ended) : "waiting in queue";
    $("#dock-steps").replaceChildren(...(j.steps.length > 1 ? j.steps.map((s, i) => h("span", { title: s,
      class: i < j.step || (i === j.step && j.status === "passed") ? "done" : i === j.step ? (j.status === "running" ? "cur" : j.status === "failed" ? "err" : "") : "" })) : []));
    const v = $("#dock-verdict");
    v.className = "verdict " + (j.status === "running" || j.status === "queued" ? "" : j.tone);
    v.textContent = j.status === "running" ? "running… " + (j.commands[j.step] || "") : j.status === "queued" ? "queued" : (j.verdict ? j.status + " · " + j.verdict : j.status);
    $("#dock-cancel").hidden = !(j.status === "running" || j.status === "queued");
    $("#dock-cancel").onclick = async () => {
      const all = j.group && await modal({ title: "Cancel", ok: "Cancel whole pipeline", body: h("p", { text: "This step is part of a pipeline. Cancel only this step, or the whole pipeline?" }) });
      try { await api("/api/cancel", all ? { group: j.group } : { job: j.id }); toast("Cancelling…"); } catch (e) { toast(e.message, "bad"); }
    };
    if (j.status === "running" || j.status === "queued") { S.dockTimer = setTimeout(pollDock, 500); return; }
    S.dockDone = true;
    if (j.group) {   // follow the pipeline to its next step
      const all = await api("/api/jobs").catch(() => null);
      const next = all && all.jobs.slice().reverse().find((x) => x.group === j.group && (x.status === "running" || x.status === "queued"));
      if (next && S.dockJob === id) { setTimeout(() => openDock(next.id), 900); }
    }
  }
  $("#dock-close").onclick = closeDock;
  $("#dock-copy").onclick = () => copy(S.dockLines.join("\n"));

  // terminal view preferences (kept per browser; storage may be unavailable)
  const pref = { get(k, d) { try { const v = localStorage.getItem("pqctl." + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
                 set(k, v) { try { localStorage.setItem("pqctl." + k, JSON.stringify(v)); } catch (e) { /* ignore */ } } };
  let termSize = pref.get("termSize", 12), termWrap = pref.get("termWrap", true);
  function applyTerm() {
    const t = $("#term");
    t.style.setProperty("--term-size", termSize + "px");
    t.classList.toggle("nowrap", !termWrap);
    $("#term-wrap").setAttribute("aria-pressed", String(termWrap));
  }
  function sizeBy(d) { termSize = Math.max(9, Math.min(28, termSize + d)); pref.set("termSize", termSize); applyTerm(); }
  function isFull() { return $("#dock").classList.contains("full"); }
  async function setFull(on) {
    const dock = $("#dock");
    dock.classList.toggle("full", on);
    $("#dock-full").setAttribute("aria-pressed", String(on));
    $("#dock-full").textContent = on ? "Exit full screen" : "Full screen";
    try {
      if (on && dock.requestFullscreen && !document.fullscreenElement) await dock.requestFullscreen();
      if (!on && document.fullscreenElement) await document.exitFullscreen();
    } catch (e) { /* the window-filling view still works without the browser's full screen */ }
    const t = $("#term");
    if ($("#follow").checked) t.scrollTop = t.scrollHeight;
    t.focus({ preventScroll: true });
  }
  document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement && isFull()) setFull(false); });
  $("#dock-full").onclick = () => setFull(!isFull());
  $("#term-bigger").onclick = () => sizeBy(1);
  $("#term-smaller").onclick = () => sizeBy(-1);
  $("#term-wrap").onclick = () => { termWrap = !termWrap; pref.set("termWrap", termWrap); applyTerm(); };
  applyTerm();
  document.addEventListener("keydown", (e) => {
    if ($("#dock").hidden || !$("#modal").hidden) return;
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "");
    if (e.key === "Escape") { e.preventDefault(); if (isFull()) setFull(false); else closeDock(); return; }
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "f" || e.key === "F") { e.preventDefault(); setFull(!isFull()); }
    else if (e.key === "+" || e.key === "=") { e.preventDefault(); sizeBy(1); }
    else if (e.key === "-" || e.key === "_") { e.preventDefault(); sizeBy(-1); }
    else if (e.key === "w" || e.key === "W") { e.preventDefault(); $("#term-wrap").click(); }
  });

  // ------------------------------------------------------------------ verify
  async function renderVerify(root) {
    const target = root || view;
    const models = await loadModels();
    let selected = models.find((m) => m.path === "runs/wm_v1/lam20_n256_rs32/seed0/model.pt") || models[0];
    let showAttacks = false;
    const list = h("div", { class: "model-list", role: "listbox", "aria-label": "Models" });
    const search = h("input", { type: "text", class: "search", placeholder: "Filter models, e.g. rs16, seed2, mallory, permute", "aria-label": "Filter models" });
    const legacy = h("input", { type: "checkbox", id: "legacy" });
    const info = h("div", { class: "mono faint", style: { fontSize: "12px" } });
    const result = h("div", { class: "section" });
    const draw = () => {
      const q = search.value.trim().toLowerCase();
      const items = models.filter((m) => (showAttacks || !m.attack) && (!q || m.path.toLowerCase().includes(q)));
      const groups = {};
      for (const m of items) (groups[m.group] = groups[m.group] || []).push(m);
      list.replaceChildren(...Object.entries(groups).map(([g, ms]) => [h("div", { class: "model-group", text: g + "  ·  " + ms.length }),
        ms.slice(0, 400).map((m) => h("button", { type: "button", class: "model" + (selected && m.path === selected.path ? " on" : ""), role: "option",
          onclick: () => { selected = m; legacy.checked = m.n_bits === 32 || m.path.includes("wm_v0") || m.path.includes("n32"); draw(); } },
          h("span", { class: "p", text: m.path.split("/").slice(1, -1).join("/") }),
          h("span", { class: "a", text: m.acc ? pct(m.acc) : "" })))]).flat(2));
      if (!items.length) list.append(h("div", { class: "empty", text: "No models match." }));
      info.textContent = selected ? selected.path + (selected.ecc ? "  ·  ecc " + selected.ecc + ", " + selected.n_bits + " bits" : "") : "";
    };
    search.addEventListener("input", draw);
    const att = h("input", { type: "checkbox", id: "attacked" });
    att.addEventListener("change", () => { showAttacks = att.checked; draw(); });
    draw();
    requestAnimationFrame(() => { const on = list.querySelector(".model.on"); if (on) list.scrollTop = on.offsetTop - 60; });
    const go = h("button", { class: "btn primary", type: "button", text: "Verify", onclick: async () => {
      if (!selected) return;
      try {
        const r = await api("/api/run", { task: "p5.verify", priority: true, params: { model: selected.path, allow_short: legacy.checked, n_bits: legacy.checked ? "32" : "" } });
        S.verifyJob = r.job.id;
        waitVerify(r.job.id, result);
      } catch (e) { toast(e.message, "bad"); }
    } });
    result.append(verdictBox("wait", "Pick a model", "The verifier checks, in order: the ML-DSA signature on the manifest, the model architecture, the hidden watermark, and that the decoded payload equals the signed hash."));
    target.replaceChildren(
      h("div", { class: "lab-head" }, h("h2", { text: "Verify a model" }),
        h("p", { class: "muted lede2", text: "Pick any model in the project. Signed models should say VERIFIED; baselines, Mallory's models and successfully attacked copies should say REJECTED." })),
      h("div", { class: "verify" },
        h("div", { class: "card" }, search, list,
          h("div", { class: "field check", style: { paddingTop: "0" } }, att, h("label", { for: "attacked", text: "Include attacked copies (Phase 6)" })),
          h("div", { class: "field check", style: { paddingTop: "0" } }, legacy, h("label", { for: "legacy", text: "Legacy 32-bit model (Phase 3, prints a WARNING)" })),
          info, h("div", { class: "task-foot" }, h("span", { class: "last" }), go)),
        h("div", { class: "card" }, result)));
  }
  function verdictBox(tone, word, text) {
    return h("div", { class: "verdict-big " + tone }, h("div", { class: "g", text: tone === "ok" ? "OK" : tone === "bad" ? "NO" : "..." }),
      h("div", {}, h("div", { class: "w", text: word }), h("div", { class: "muted", text })));
  }
  async function waitVerify(id, box) {
    box.replaceChildren(verdictBox("wait", "Checking…", "Running verify.verify_model"));
    let lines = [], since = 0, j;
    try {
      for (;;) {
        j = await api("/api/jobs/" + id + "?since=" + since);
        lines = lines.concat(j.new); since = j.since + j.new.length;
        if (j.status !== "running" && j.status !== "queued") break;
        await new Promise((r) => setTimeout(r, 400));
        if (S.verifyJob !== id) return;
      }
    } catch (e) { box.replaceChildren(verdictBox("bad", "ERROR", e.message)); return; }
    const verdict = lines.find((l) => /^(VERIFIED|REJECTED)\s*$/.test(l.trim()));
    const settings = lines.find((l) => l.startsWith("watermark settings"));
    const checks = lines.filter((l) => /^(PASS|FAIL|WARNING)\s/.test(l));
    const ok = verdict && verdict.trim() === "VERIFIED";
    const firstFail = checks.find((c) => c.startsWith("FAIL"));
    box.replaceChildren(
      verdictBox(ok ? "ok" : "bad", verdict ? verdict.trim() : "ERROR", ok ? "Signature valid and the hidden payload matches the signed manifest." :
        firstFail ? "Stopped at: " + firstFail.replace(/^FAIL\s+/, "") : "The verifier did not finish. Open the log for details."),
      settings ? h("div", { class: "mono faint", style: { fontSize: "12px" }, text: settings }) : null,
      checks.length ? h("div", { class: "checks" }, checks.map((c) => {
        const m = c.match(/^(PASS|FAIL|WARNING)\s+(.*?)(?:\s+\((.*)\))?$/);
        const kind = m ? m[1] : "PASS";
        return h("div", { class: kind === "PASS" ? "pass" : kind === "FAIL" ? "fail" : "warn" }, h("b", { text: kind }),
          h("span", {}, m ? m[2] : c, m && m[3] ? h("small", { text: m[3] }) : null));
      })) : null,
      h("div", { class: "task-foot" }, h("span", { class: "last" }), h("button", { class: "btn ghost sm", type: "button", text: "Open full log", onclick: () => openDock(id) })));
  }

  // ------------------------------------------------------------------ results
  async function renderResults() {
    crumbs("Tools", "Results");
    S.results = await api("/api/results");
    const tabs = [["attacks", "Phase 6 · attacks"], ["plots", "Phase 6 · plots"], ["phase4", "Phase 4 · ECC runs"], ["baseline", "Phase 1 · baseline"], ["docs", "Documents"]];
    const body = h("div", { class: "section" });
    const bar = h("div", { class: "tabs", role: "tablist" }, tabs.map(([k, l]) => h("button", { type: "button", role: "tab", "aria-selected": String(S.resultsTab === k),
      text: l, onclick: (e) => { S.resultsTab = k; bar.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b === e.target))); drawTab(body); } })));
    view.replaceChildren(h("div", { class: "phase-head" }, h("span", { class: "eyebrow", text: "Measured numbers" }), h("h1", { text: "Results" })), bar, body);
    drawTab(body);
  }
  function outcome(r) {
    if ((r.removal_success || 0) > 0) return ["bad", "removed"];
    if ((r.verified_rate ?? 1) < 1) return ["warn", "model ruined"];
    return ["ok", "held"];
  }
  function drawTab(body) {
    const R = S.results;
    const tab = S.resultsTab;
    if (tab === "attacks") {
      let rows = R.phase6.summary.filter((r) => r.family !== "control");
      if (!rows.length) return body.replaceChildren(h("div", { class: "empty", text: "No Phase 6 results yet. Run the Phase 6 pipeline." }));
      const t = R.phase6.totals;
      if (S.filter !== "all") rows = rows.filter((r) => outcome(r)[1] === S.filter);
      if (S.sort.key) rows = rows.slice().sort((a, b) => ((a[S.sort.key] ?? -1) > (b[S.sort.key] ?? -1) ? 1 : -1) * S.sort.dir);
      const th = (k, l, num) => h("th", { class: num ? "num" : "" }, h("button", { type: "button", text: l + (S.sort.key === k ? (S.sort.dir > 0 ? " ↑" : " ↓") : ""),
        onclick: () => { S.sort = { key: k, dir: S.sort.key === k ? -S.sort.dir : 1 }; drawTab(body); } }));
      const filt = h("div", { class: "multi" }, ["all", "held", "removed", "model ruined"].map((f) => {
        const cb = h("input", { type: "radio", name: "of", value: f }); cb.checked = S.filter === f;
        cb.addEventListener("change", () => { S.filter = f; drawTab(body); });
        return h("label", {}, cb, f);
      }));
      body.replaceChildren(
        h("div", { class: "stats" }, stat(t.wm_verified + "/" + t.wm_runs, "attacked copies verified", "ok"), stat(t.base_false_accepts + "/" + t.base_runs, "unsigned models accepted", t.base_false_accepts ? "bad" : "ok"),
          stat(String(t.removed_types), "attack types that removed it (model still useful)", t.removed_types ? "bad" : "ok")),
        filt,
        h("div", { class: "tbl-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, th("attack_id", "Attack"), th("family", "Family"), th("runs", "Runs", 1), th("verified_rate", "Verified", 1),
            th("mean_acc", "Accuracy after", 1), th("mean_drop", "Drop (pts)", 1), th("mean_flip", "Bits flipped", 1), th("removal_success", "Outcome"))),
          h("tbody", {}, rows.map((r) => { const [tone, word] = outcome(r); return h("tr", {},
            h("td", { class: "mono", text: r.attack_id }), h("td", { class: "muted", text: r.family }), h("td", { class: "num", text: fix(r.runs, 0) }),
            h("td", { class: "num" }, h("div", { style: { display: "flex", gap: "8px", alignItems: "center", justifyContent: "flex-end" } }, h("div", { class: "bar" }, h("i", { style: { width: (100 * r.verified_rate) + "%" } })), pct(r.verified_rate, 0))),
            h("td", { class: "num", text: pct(r.mean_acc) }), h("td", { class: "num", text: r.mean_drop === null ? "—" : fix(100 * r.mean_drop) }), h("td", { class: "num", text: r.mean_flip === null ? "—" : pct(r.mean_flip) }),
            h("td", {}, h("span", { class: "chip " + tone, text: word }))); })))),
        h("p", { class: "muted", text: "Removed = the verifier stopped saying VERIFIED while accuracy dropped by at most 5 points. Model ruined = the watermark was lost only by destroying the model." }));
    } else if (tab === "plots") {
      body.replaceChildren(R.phase6.plots.length ? h("div", { class: "plots" }, R.phase6.plots.map((p) => h("figure", {},
        h("img", { src: "/api/file?path=" + encodeURIComponent(p), alt: "Phase 6 plot " + p, loading: "lazy" }), h("figcaption", { text: p.split("/").pop() })))) :
        h("div", { class: "empty", text: "No plots yet. Run “Build the results tables and plots” in Phase 6." }));
    } else if (tab === "phase4") {
      body.replaceChildren(R.phase4.length ? h("div", { class: "tbl-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Config", "Seeds", "Accuracy", "Cost (pts)", "Min margin", "Raw errors", "Decoded errors"].map((x, i) => h("th", { class: i ? "num" : "", text: x })))),
        h("tbody", {}, R.phase4.map((r) => h("tr", {}, h("td", { class: "mono", text: r.config }), h("td", { class: "num", text: r.seeds }),
          h("td", { class: "num", text: pct(r.mean_wm_acc) }), h("td", { class: "num", text: fix(r.diff_pts) }), h("td", { class: "num", text: fix(r.margin, 2) }),
          h("td", { class: "num", text: r.raw_errors }), h("td", { class: "num", text: r.decoded_errors }))))))
        : h("div", { class: "empty", text: "No runs/wm_v1/summary.json yet." }));
    } else if (tab === "baseline") {
      body.replaceChildren(R.baseline.length ? h("div", { class: "tbl-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", { text: "Seed" }), h("th", { class: "num", text: "Test accuracy" }), h("th", { class: "num", text: "Train time" }))),
        h("tbody", {}, R.baseline.map((b) => h("tr", {}, h("td", { class: "mono", text: "seed " + b.seed }), h("td", { class: "num", text: pct(b.acc, 2) }),
          h("td", { class: "num", text: b.seconds ? Math.round(b.seconds / 60) + " min" : "—" }))))))
        : h("div", { class: "empty", text: "No baseline models yet." }));
    } else if (tab === "docs") {
      const out = h("div", { class: "md" });
      const pick = h("div", { class: "multi" }, R.docs.map((d, i) => {
        const rb = h("input", { type: "radio", name: "doc", value: d }); if (!i) rb.checked = true;
        rb.addEventListener("change", () => loadDoc(d, out));
        return h("label", {}, rb, d);
      }));
      body.replaceChildren(pick, h("div", { class: "card" }, out));
      if (R.docs[0]) loadDoc(R.docs[0], out);
    }
  }
  async function loadDoc(path, out) {
    out.replaceChildren(h("span", { class: "muted", text: "loading…" }));
    const r = await fetch("/api/file?path=" + encodeURIComponent(path));
    out.replaceChildren(...renderMd(r.ok ? await r.text() : "Could not load " + path));
  }
  function inline(text) {
    const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
    return parts.map((p) => p.startsWith("`") && p.endsWith("`") && p.length > 1 ? h("code", { text: p.slice(1, -1) }) :
      p.startsWith("**") && p.endsWith("**") && p.length > 3 ? h("b", { text: p.slice(2, -2) }) : p);
  }
  function renderMd(src) {
    const out = [], lines = src.replace(/\r/g, "").split("\n");
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (l.startsWith("```")) { const buf = []; i++; while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]); out.push(h("pre", { text: buf.join("\n") })); continue; }
      const hd = l.match(/^(#{1,3})\s+(.*)/);
      if (hd) { out.push(h("h" + hd[1].length, {}, inline(hd[2]))); continue; }
      if (l.trim().startsWith("|")) {
        const rows = [];
        while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
        i--;
        const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const body = rows.filter((r, k) => !(k === 1 && /^[\s|:-]+$/.test(r)));
        out.push(h("div", { class: "tbl-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, cells(body[0]).map((c) => h("th", {}, inline(c))))),
          h("tbody", {}, body.slice(1).map((r) => h("tr", {}, cells(r).map((c) => h("td", {}, inline(c)))))))));
        continue;
      }
      if (/^\s*[-*]\s+/.test(l)) {
        const items = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*]\s+/, ""));
        i--;
        out.push(h("ul", {}, items.map((x) => h("li", {}, inline(x)))));
        continue;
      }
      if (l.trim()) out.push(h("p", {}, inline(l)));
    }
    return out;
  }

  // ------------------------------------------------------------------ jobs
  function jobsTable(jobs) {
    return h("div", { class: "tbl-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Job", "Status", "Result", "Time", "Started", ""].map((x) => h("th", { text: x })))),
      h("tbody", {}, jobs.map((j) => h("tr", { class: "click", onclick: () => openDock(j.id) },
        h("td", {}, h("div", { text: j.title }), h("div", { class: "mono faint", style: { fontSize: "11px" }, text: j.task_id + (j.group ? "  ·  pipeline" : "") })),
        h("td", {}, statusChip(j)),
        h("td", { class: "mono", style: { fontSize: "12px", color: j.tone === "bad" ? "var(--bad)" : j.tone === "ok" ? "var(--ok)" : "var(--muted)" }, text: j.verdict || "" }),
        h("td", { class: "num muted", text: j.started ? dur(j.started, j.ended) : "" }),
        h("td", { class: "muted", text: ago(j.started || j.created) }),
        h("td", {}, (j.status === "running" || j.status === "queued") ? h("button", { class: "btn danger sm", type: "button", text: "Cancel",
          onclick: async (e) => { e.stopPropagation(); await api("/api/cancel", { job: j.id }).catch((er) => toast(er.message, "bad")); refreshShell(); route(); } }) : null))))));
  }
  async function renderJobs() {
    crumbs("Tools", "Jobs");
    const d = await api("/api/jobs");
    view.replaceChildren(h("div", { class: "phase-head" }, h("span", { class: "eyebrow", text: "This session" }), h("h1", { text: "Jobs" }),
      h("p", { class: "muted", text: "Jobs run one at a time, in order. Logs are also saved in .pqctl/logs/ inside the project." })),
      d.jobs.length ? jobsTable(d.jobs) : h("div", { class: "empty", text: "No jobs yet." }));
  }

  // ------------------------------------------------------------------ environment
  async function renderEnv(fresh) {
    crumbs("Tools", "Environment");
    view.replaceChildren(h("div", { class: "empty", text: "Checking your Python environment… (importing PyTorch can take a few seconds)" }));
    const d = await api("/api/doctor" + (fresh ? "?fresh=1" : ""));
    const bad = d.checks.filter((c) => c.state === "bad").length;
    $("#nav-env-dot").className = "dot " + (bad ? "bad" : d.checks.some((c) => c.state === "warn") ? "warn" : "ok");
    const cifar = h("input", { type: "text", id: "set-cifar", spellcheck: "false" }); cifar.value = d.settings.cifar_root;
    const py = h("input", { type: "text", id: "set-py", spellcheck: "false" }); py.value = d.settings.python;
    view.replaceChildren(
      h("div", { class: "phase-head" }, h("span", { class: "eyebrow", text: "Setup" }),
        h("div", { class: "row" }, h("h1", { text: "Environment" }), h("span", { class: "chip " + (bad ? "bad" : "ok"), text: bad ? bad + " to fix" : "ready" })),
        h("p", { class: "muted", text: "What the task interpreter has installed, which keys and data are present, and how to fix what is missing." })),
      h("div", { class: "envlist" }, d.checks.map((c) => h("div", { class: "envrow" },
        h("span", { class: "s " + c.state, text: c.state === "ok" ? "OK" : c.state === "warn" ? "WARN" : "FAIL" }),
        h("span", { text: c.label }),
        h("div", {}, h("div", { class: "d", text: c.detail }), c.fix ? h("div", { class: "fix" }, h("code", { text: c.fix }),
          /pip |python /.test(c.fix) ? h("button", { class: "btn ghost sm", type: "button", text: "copy", onclick: () => copy(c.fix) }) : null) : null)))),
      h("div", { class: "card" }, h("h2", { text: "Settings" }),
        h("div", { class: "form" },
          h("div", { class: "field" }, h("label", { for: "set-cifar", text: "CIFAR-10 folder (contains cifar-10-batches-py)" }), cifar),
          h("div", { class: "field", style: { gridColumn: "span 2" } }, h("label", { for: "set-py", text: "Python used to run tasks (your venv's python)" }), py)),
        h("div", { class: "task-foot" }, h("span", { class: "last" }),
          h("button", { class: "btn ghost", type: "button", text: "Re-check", onclick: () => renderEnv(true) }),
          h("button", { class: "btn primary", type: "button", text: "Save", onclick: async () => {
            try { await api("/api/settings", { cifar_root: cifar.value, python: py.value }); toast("Saved", "ok"); S.tasks = null; renderEnv(true); }
            catch (e) { toast(e.message, "bad"); } } }))));
  }

  // ------------------------------------------------------------------ test model: every live check with its expected result
  const M = {
    ours: "runs/wm_v1/lam20_n256_rs32/seed0/model.pt",
    base: "runs/baseline/seed0/model.pt",
    mallory: "mallory/runs/lam20_n256_rs32/seed3/model.pt",
    ft: "runs/attacks/wm/seed0/finetune_e10_lr0.05_full/rep0/model.pt",
    q4: "runs/attacks/wm/seed0/quant_pt_4/rep0/model.pt",
    prune: "runs/attacks/wm/seed0/prune_global_0.5/rep0/model.pt",
    perm: "runs/attacks/wm/seed0/permute_in_carrier/rep0/model.pt",
    over: "runs/attacks/wm/seed0/overwrite_128bit/rep0/model.pt",
  };
  const TESTS = [
    { group: "Signature", items: [
      { label: "Signed release is valid", task: "p2.verify_release", params: {}, expect: "VERIFIED", note: "verify.verify_release with keys/public_key.bin" },
      { label: "Tampered releases are rejected", task: "p2.tamper", params: {}, expect: "PASSED", note: "6 edited copies of the release must all fail" },
      { label: "Renamed developer is rejected", task: "lab.tamper", params: { developer_id: "Mallory", model: M.ours }, expect: "REJECTED", note: "temporary copy, developer_id changed" },
    ] },
    { group: "Ownership", items: [
      { label: "Our signed model", task: "p5.verify", params: { model: M.ours }, expect: "VERIFIED", note: M.ours },
      { label: "Unsigned baseline model", task: "p5.verify", params: { model: M.base }, expect: "REJECTED", note: M.base },
      { label: "Mallory's model with our files", task: "p5.verify", params: { model: M.mallory }, expect: "REJECTED", note: M.mallory },
    ] },
    { group: "Survives changes (Phase 6)", items: [
      { label: "Retrained 10 epochs on all data", task: "p5.verify", params: { model: M.ft }, expect: "VERIFIED", note: "finetune_e10_lr0.05_full" },
      { label: "Weights compressed to 4 bits", task: "p5.verify", params: { model: M.q4 }, expect: "VERIFIED", note: "quant_pt_4" },
      { label: "Half of the weights deleted", task: "p5.verify", params: { model: M.prune }, expect: "VERIFIED", note: "prune_global_0.5" },
    ] },
    { group: "Known weaknesses (Phase 6)", items: [
      { label: "Channels shuffled", task: "p5.verify", params: { model: M.perm }, expect: "REJECTED", note: "permute_in_carrier: accuracy unchanged, mark scrambled" },
      { label: "Overwritten with a second watermark", task: "p5.verify", params: { model: M.over }, expect: "REJECTED", note: "overwrite_128bit" },
    ] },
  ];

  async function renderTest() {
    crumbs("Test model");
    const [D, T2] = await Promise.all([api("/api/doctor"), api("/api/tasks")]);
    S.history = T2.history;
    const byId = Object.fromEntries(D.checks.map((x) => [x.id, x]));
    const st = (id) => (byId[id] ? byId[id].state : "bad");
    const prepRow = (state, text) => h("div", {}, h("span", { class: "s " + state, text: state === "ok" ? "OK" : state === "warn" ? "WARN" : "FAIL" }), h("span", { text }), h("span"));
    const prep = h("div", { class: "card" }, h("h2", { text: "Ready to test" }),
      h("div", { class: "prep" },
        prepRow(st("pkg-torch") === "ok" && st("pkg-oqs") === "ok" ? "ok" : "bad", "PyTorch and liboqs installed in the Python running this dashboard"),
        prepRow(st("pubkey") === "ok" && st("wmkey") === "ok" ? "ok" : "bad", "keys/ folder in place (public key and the right watermark key)"),
        prepRow(st("mallory"), "Mallory's keys in place (needed for the Mallory test)")),
      h("div", { class: "task-foot" }, h("span", { class: "last" }), h("a", { class: "btn ghost sm", href: "#env", text: "Environment" })));

    const rows = [];
    const summary = h("span", { class: "muted" });
    const counts = () => {
      const done = rows.filter((r) => r.word && r.word !== "SETUP"), pass = done.filter((r) => r.word === r.t.expect);
      const blocked = rows.filter((r) => r.word === "SETUP").length;
      summary.textContent = (done.length ? pass.length + " of " + done.length + " tests gave the expected result" : rows.length + " tests")
        + (blocked ? ", " + blocked + " could not run (see Environment)" : "");
    };
    const makeRow = (t) => {
      const res = h("div", { class: "res" });
      const row = { t, word: null };
      const btn = h("button", { class: "btn primary sm", type: "button", text: "Run" });
      row.run = async () => {
        btn.disabled = true;
        try { row.word = await runMini(t.task, t.params, res, t.expect); }
        finally { btn.disabled = false; counts(); }
      };
      btn.onclick = row.run;
      rows.push(row);
      return h("div", { class: "action" },
        h("div", { class: "lbl" }, h("b", { text: t.label }), h("small", { text: t.note }),
          h("span", { class: "expect", style: { color: t.expect === "REJECTED" ? "var(--bad)" : "var(--ok)" }, text: "expected: " + t.expect })),
        btn, res);
    };
    const runAll = h("button", { class: "btn primary", type: "button", text: "Run all tests", onclick: async () => {
      runAll.disabled = true;
      try { for (const r of rows) await r.run(); } finally { runAll.disabled = false; }
    } });
    view.replaceChildren(
      h("div", { class: "phase-head" }, h("span", { class: "eyebrow", text: "Live checks" }), h("h1", { text: "Test model" }),
        h("p", { class: "muted", text: "Each test runs the real verifier or tool on a real file in this project and compares the answer with the expected one. To test any other model, use Labs, Verify a model." }),
        h("div", { class: "demo-intro" }, runAll, summary,
          h("button", { class: "btn", type: "button", text: "Run every check (all phases)", onclick: () => runPipeline({ id: "check-all", title: "Run every check" }) }),
          h("a", { class: "btn ghost", href: "#labs/verify", text: "Verify another model" }))),
      prep,
      TESTS.map((g) => h("section", { class: "section" }, h("h2", { text: g.group }), h("div", { class: "actions" }, g.items.map(makeRow)))));
    counts();
  }

  async function runMini(task, params, box, expect) {
    box.replaceChildren(h("div", { class: "mini" }, h("span", { class: "chip acc running", text: "running" }), h("span", { class: "faint", text: "the real command is running..." })));
    let r;
    try { r = await api("/api/run", { task, params, priority: true }); }
    catch (e) { box.replaceChildren(h("div", { class: "mini" }, h("span", { class: "big bad", text: "could not start" }), h("span", { class: "why", text: e.message }))); return "ERROR"; }
    const id = r.job.id;
    let lines = [], since = 0, j;
    try {
      for (;;) {
        j = await api("/api/jobs/" + id + "?since=" + since);
        lines = lines.concat(j.new); since = j.since + j.new.length;
        if (j.status !== "running" && j.status !== "queued") break;
        await new Promise((res) => setTimeout(res, 400));
      }
    } catch (e) { box.replaceChildren(h("div", { class: "mini" }, h("span", { class: "big bad", text: "lost contact" }), h("span", { class: "why", text: e.message }))); return "ERROR"; }
    const vline = lines.find((l) => /^(VERIFIED|REJECTED)\s*$/.test(l.trim()));
    const word = (j.result && j.result.verdict) || (vline ? vline.trim() : (j.verdict && /PASSED|FAILED/.test(j.verdict) ? j.verdict.replace(/.*(PASSED|FAILED).*/, "$1") : (j.verdict || j.status.toUpperCase())));
    const fail = lines.find((l) => l.startsWith("FAIL"));
    const missing = j.verdict && j.verdict.startsWith("missing") ? j.verdict : null;
    // a REJECTED caused by missing keys or packages is not a real answer: say so instead of counting it
    const setup = missing || (j.result && j.result.error) || (fail && /load release files|No such file|No module named/.test(fail));
    if (setup) {
      const reason = missing ? "This computer's Python is " + missing + "." : fail ? fail.replace(/^FAIL\s+/, "") : j.result.error;
      box.replaceChildren(h("div", { class: "mini" }, h("span", { class: "big warnc", text: "CANNOT RUN" }),
        h("button", { class: "btn ghost sm", type: "button", text: "Full output", onclick: () => openDock(id) }),
        h("span", { class: "why", text: reason + " Fix it in Environment, then run again." })));
      return "SETUP";
    }
    const good = word === "VERIFIED" || word === "PASSED";
    const why = good ? "All checks passed." : (fail ? "Stopped at: " + fail.replace(/^FAIL\s+/, "") : (j.verdict ? "Result: " + j.verdict : "Finished with status " + j.status + "."));
    box.replaceChildren(h("div", { class: "mini" },
      h("span", { class: "big " + (good ? "ok" : "bad"), text: word }),
      expect ? h("span", { class: word === expect ? "match" : "nomatch", text: word === expect ? "as expected" : "expected " + expect }) : null,
      h("button", { class: "btn ghost sm", type: "button", text: "Full output", onclick: () => openDock(id) }),
      h("span", { class: "why", text: why })));
    return word;
  }

  // ------------------------------------------------------------------ shared with labs.js
  window.PQ = { h, api, toast, pct, fix, ago, dur, copy, modal, crumbs, view, S, ROUTES, openDock, loadModels, runPipeline,
                statusChip, stat, renderMd, fillLast, verdictBox, outcome, drawTab, renderVerify, route };

  // ------------------------------------------------------------------ boot
  $("#run-all").onclick = () => runPipeline({ id: "check-all", title: "Run every check" });
  $("#term-toggle").onclick = () => { if ($("#dock").hidden) { if (S.dockJob) showDock(); else idleDock(); } else closeDock(); };
  window.addEventListener("DOMContentLoaded", () => {
    let closed = false;
    try { closed = localStorage.getItem("pqctl.dockClosed") === "1"; } catch (e) { /* ignore */ }
    if (!closed && window.innerWidth >= 1100) idleDock();         // terminal open on the side by default
  });
  $("#menu-btn").onclick = () => document.body.classList.toggle("rail-open");
  window.addEventListener("hashchange", route);
  window.addEventListener("DOMContentLoaded", () => { refreshShell(); setInterval(refreshShell, 2500); });
  api("/api/doctor").then((d) => {
    const bad = d.checks.filter((c) => c.state === "bad").length;
    $("#nav-env-dot").className = "dot " + (bad ? "bad" : d.checks.some((c) => c.state === "warn") ? "warn" : "ok");
  }).catch(() => {});
})();

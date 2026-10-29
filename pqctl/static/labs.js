/* pqctl dashboard v2: one Labs page with every interactive tool (verify, X-ray, attacks, tampering, signing, hashing, release
   inspector) plus results, charts and plots.
   Uses the helpers app.js exposes on window.PQ. DOM is built with textContent only. */
(() => {
  "use strict";
  const P = window.PQ;
  const { h, api, toast, pct, fix, crumbs, view, S, ROUTES, openDock } = P;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const MODELS = {
    ours: "runs/wm_v1/lam20_n256_rs32/seed0/model.pt",
    ours1: "runs/wm_v1/lam20_n256_rs32/seed1/model.pt",
    base: "runs/baseline/seed0/model.pt",
    mallory: "mallory/runs/lam20_n256_rs32/seed3/model.pt",
    perm: "runs/attacks/wm/seed0/permute_in_carrier/rep0/model.pt",
    over: "runs/attacks/wm/seed0/overwrite_128bit/rep0/model.pt",
    ft: "runs/attacks/wm/seed0/finetune_e10_lr0.05_full/rep0/model.pt",
    q4: "runs/attacks/wm/seed0/quant_pt_4/rep0/model.pt",
  };

  // ================================================================== shared pieces
  /** Run one task (front of the queue) and wait. Returns the finished job with .lines and .result. */
  async function runJob(task, params, onTick) {
    const r = await api("/api/run", { task, params: params || {}, priority: true });
    const id = r.job.id;
    let since = 0, lines = [], j;
    for (;;) {
      j = await api("/api/jobs/" + id + "?since=" + since);
      lines = lines.concat(j.new); since = j.since + j.new.length;
      if (onTick) onTick(j, lines);
      if (j.status !== "running" && j.status !== "queued") break;
      await sleep(350);
    }
    j.lines = lines; j.id = id;
    return j;
  }
  const verdictLine = (j) => { const v = (j.lines || []).find((l) => /^(VERIFIED|REJECTED)\s*$/.test(l.trim())); return v ? v.trim() : null; };
  function wordOf(j) {
    if (j.result && j.result.error) return "ERROR";
    const v = (j.result && j.result.verdict) || verdictLine(j);
    if (v) return v;
    if (j.verdict && /PASSED|FAILED/.test(j.verdict)) return j.verdict.match(/PASSED|FAILED/)[0];
    return j.status === "passed" ? "PASSED" : j.status.toUpperCase();
  }
  function busy(box, text) {
    box.replaceChildren(h("div", { class: "lab-busy" }, h("span", { class: "spin" }), h("span", { text: text || "running the real command…" })));
  }
  /** The standard result card: big word, expected-vs-actual, reason, PASS/FAIL checks, link to the full log. */
  function resultCard(j, opts = {}) {
    const word = wordOf(j);
    const good = word === "VERIFIED" || word === "PASSED";
    const missing = j.verdict && j.verdict.startsWith("missing") && (!j.result || j.result.error) ? j.verdict : null;
    const checks = (j.result && j.result.checks) ? j.result.checks.map((c) => [c[1] ? "PASS" : "FAIL", c[0], c[2]])
      : (j.lines || []).filter((l) => /^(PASS|FAIL|WARNING)\s/.test(l)).map((l) => {
        const m = l.match(/^(PASS|FAIL|WARNING)\s+(.*?)(?:\s+\((.*)\))?$/); return m ? [m[1], m[2], m[3] || ""] : ["PASS", l, ""]; });
    const firstFail = checks.find((c) => c[0] === "FAIL");
    let why = opts.why || "";
    if (missing) why = "This computer's Python is " + missing + ". Open Environment to fix it, then try again.";
    else if (j.result && j.result.error) why = j.result.error;
    else if (!why) why = good ? "Every check passed." : firstFail ? "Stopped at: " + firstFail[1] + (firstFail[2] ? " (" + firstFail[2] + ")" : "") : "";
    return h("div", { class: "rcard " + (good ? "ok" : "bad") },
      h("div", { class: "rtop" },
        h("span", { class: "rword", text: word }),
        opts.expect ? h("span", { class: word === opts.expect ? "match" : "nomatch", text: word === opts.expect ? "as expected" : "expected " + opts.expect }) : null,
        h("span", { class: "rgrow" }),
        h("button", { class: "btn ghost sm", type: "button", text: "Full output", onclick: () => openDock(j.id) })),
      why ? h("p", { class: "rwhy", text: why }) : null,
      opts.showChecks !== false && checks.length ? h("div", { class: "rchecks" }, checks.map((c) => h("div", { class: c[0].toLowerCase() },
        h("b", { text: c[0] }), h("span", {}, c[1], c[2] ? h("small", { text: c[2] }) : null)))) : null);
  }
  /** Run + show in one go, with a busy state. */
  async function runInto(box, task, params, opts = {}) {
    busy(box, opts.busy);
    try {
      const j = await runJob(task, params);
      box.replaceChildren(resultCard(j, opts));
      if (opts.after) opts.after(j, box);
      return j;
    } catch (e) { box.replaceChildren(h("div", { class: "rcard bad" }, h("p", { class: "rwhy", text: e.message }))); return null; }
  }

  /** A grid of small squares. cells: array of {tone: "ok"|"bad"|"warn"|"dim"|"acc", a: 0..1, t: tooltip}. */
  function bitGrid(cells, cols = 32, label) {
    const g = h("div", { class: "bits", style: { gridTemplateColumns: "repeat(" + cols + ", minmax(0, 1fr))" }, role: "img", "aria-label": label || "bit grid" });
    const frag = document.createDocumentFragment();
    for (const c of cells) {
      const i = document.createElement("i");
      i.className = c.tone || "dim";
      if (c.a !== undefined) i.style.opacity = String(0.28 + 0.72 * Math.max(0, Math.min(1, c.a)));
      if (c.t) i.title = c.t;
      frag.append(i);
    }
    g.append(frag);
    return g;
  }
  function legend(items) {
    return h("div", { class: "legend2" }, items.map(([tone, text]) => h("span", {}, h("i", { class: "lg " + tone }), text)));
  }

  /** Histogram of scores with the decision line at 0. */
  function histogram(values, { bins = 40, height = 150, label = "score" } = {}) {
    const W = 560, H = height, m = { l: 34, r: 10, t: 10, b: 26 };
    const lim = Math.max(1e-6, ...values.map((v) => Math.abs(v)));
    const lo = -lim, hi = lim, bw = (hi - lo) / bins;
    const counts = new Array(bins).fill(0);
    for (const v of values) counts[Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / bw)))]++;
    const ymax = Math.max(1, ...counts);
    const x = (v) => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r);
    const y = (c) => H - m.b - c / ymax * (H - m.t - m.b);
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("width", "100%"); svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Histogram of " + label + "s");
    const add = (tag, attrs, text) => { const e = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (text !== undefined) e.textContent = text; svg.append(e); return e; };
    counts.forEach((c, i) => {
      if (!c) return;
      const x0 = x(lo + i * bw), x1 = x(lo + (i + 1) * bw);
      add("rect", { x: x0 + 0.5, y: y(c), width: Math.max(1, x1 - x0 - 1), height: H - m.b - y(c), rx: 1.5, class: (lo + (i + 0.5) * bw) >= 0 ? "hb pos" : "hb neg" });
    });
    add("line", { x1: x(0), x2: x(0), y1: m.t, y2: H - m.b, class: "hz" });
    add("text", { x: x(0), y: H - 8, "text-anchor": "middle", class: "ht" }, "0");
    add("text", { x: m.l, y: H - 8, "text-anchor": "start", class: "ht" }, fix(lo, 1));
    add("text", { x: W - m.r, y: H - 8, "text-anchor": "end", class: "ht" }, fix(hi, 1));
    add("text", { x: x(0) - 6, y: m.t + 10, "text-anchor": "end", class: "ht" }, "bit 0 ←");
    add("text", { x: x(0) + 6, y: m.t + 10, "text-anchor": "start", class: "ht" }, "→ bit 1");
    return svg;
  }

  /** Heatmap of the carrier vector (e.g. 576 numbers as 24 x 24) on a canvas. Blue = positive, amber = negative. */
  function heatmap(values, cols) {
    cols = cols || Math.ceil(Math.sqrt(values.length));
    const rows = Math.ceil(values.length / cols), s = 10;
    const c = h("canvas", { width: cols * s, height: rows * s, class: "heat", role: "img", "aria-label": values.length + " carrier numbers" });
    const ctx = c.getContext("2d");
    const lim = Math.max(1e-9, ...values.map(Math.abs));
    values.forEach((v, i) => {
      const t = Math.min(1, Math.abs(v) / lim);
      ctx.fillStyle = v >= 0 ? "rgba(138,180,255," + (0.12 + 0.88 * t) + ")" : "rgba(255,181,71," + (0.12 + 0.88 * t) + ")";
      ctx.fillRect((i % cols) * s, Math.floor(i / cols) * s, s - 1, s - 1);
    });
    return c;
  }

  /** Simple line chart: series [{name, pts:[{x,y,ok}], }], with optional y reference line. */
  function lineChart({ series, xLabel, yLabel, yMin = 0, yMax = 1, ref, xFmt = (v) => String(v), yFmt = (v) => Math.round(v * 100) + "%", height = 210, xLog = false }) {
    const W = 460, H = height, m = { l: 40, r: 12, t: 12, b: 34 };
    series = series.map((s) => ({ ...s, pts: s.pts.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)) }));
    const xs = series.flatMap((s) => s.pts.map((p) => p.x));
    if (!xs.length) return h("div", { class: "empty", text: "No results for this attack yet." });
    let x0 = Math.min(...xs), x1 = Math.max(...xs);
    if (x0 === x1) { x0 -= 1; x1 += 1; }
    const tx = (v) => xLog ? Math.log10(v) : v;
    const X = (v) => m.l + (tx(v) - tx(x0)) / (tx(x1) - tx(x0)) * (W - m.l - m.r);
    const Y = (v) => H - m.b - (v - yMin) / (yMax - yMin) * (H - m.t - m.b);
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("width", "100%"); svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", yLabel + " against " + xLabel);
    const add = (tag, attrs, text, parent = svg) => { const e = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (text !== undefined) e.textContent = text; parent.append(e); return e; };
    for (let i = 0; i <= 4; i++) {
      const v = yMin + (yMax - yMin) * i / 4;
      add("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: "cg" });
      add("text", { x: m.l - 6, y: Y(v) + 3.5, "text-anchor": "end", class: "ct" }, yFmt(v));
    }
    const ticks = [...new Set(xs)].sort((a, b) => a - b);
    const step = Math.max(1, Math.ceil(ticks.length / 7));
    ticks.forEach((v, i) => { if (i % step === 0 || i === ticks.length - 1) add("text", { x: X(v), y: H - m.b + 15, "text-anchor": "middle", class: "ct" }, xFmt(v)); });
    add("text", { x: (m.l + W - m.r) / 2, y: H - 4, "text-anchor": "middle", class: "ct lab" }, xLabel);
    if (ref !== undefined) {
      add("line", { x1: m.l, x2: W - m.r, y1: Y(ref.y), y2: Y(ref.y), class: "cref" });
      add("text", { x: W - m.r, y: Y(ref.y) + 13, "text-anchor": "end", class: "ct" }, ref.label);
    }
    series.forEach((s, si) => {
      const pts = s.pts.slice().sort((a, b) => a.x - b.x);
      add("path", { d: pts.map((p, i) => (i ? "L" : "M") + X(p.x).toFixed(1) + "," + Y(p.y).toFixed(1)).join(" "), class: "cl s" + si });
      for (const p of pts) {
        const c = add("circle", { cx: X(p.x), cy: Y(p.y), r: 4.5, class: p.ok ? "cp ok" : "cp bad" });
        add("title", {}, (s.name ? s.name + ": " : "") + xFmt(p.x) + " → " + yFmt(p.y) + (p.ok ? " · watermark VERIFIED" : " · watermark lost"), c);
      }
    });
    return svg;
  }

  /** A model dropdown grouped by folder. */
  async function modelSelect(id, value, { attacks = true, extra = [] } = {}) {
    const models = await P.loadModels();
    const sel = h("select", { id, class: "msel" });
    const groups = {};
    for (const m of models) if (attacks || !m.attack) (groups[m.attack ? "Phase 6 attacked copies" : m.group] = groups[m.attack ? "Phase 6 attacked copies" : m.group] || []).push(m);
    if (extra.length) sel.append(h("optgroup", { label: "Made in the attack lab (this session)" }, extra.map((p) => h("option", { value: p, text: p.replace(".pqctl/lab/", "lab: ") }))));
    for (const [g, ms] of Object.entries(groups)) sel.append(h("optgroup", { label: g }, ms.map((m) => h("option", { value: m.path,
      text: m.path.replace(/^runs\/attacks\/wm\//, "").replace(/\/model\.pt$/, "") + (m.acc ? "  ·  " + pct(m.acc) : "") }))));
    sel.value = value;
    return sel;
  }
  const labModels = [];
  function pageHead(eyebrow, title, text, extra) {
    return h("div", { class: "phase-head" }, h("span", { class: "eyebrow", text: eyebrow }), h("div", { class: "row" }, h("h1", { text: title }), extra || null),
      text ? h("p", { class: "muted lede2", text }) : null);
  }
  function explain(title, items) {
    return h("details", { class: "explain" }, h("summary", { text: title }), h("div", { class: "explain-body" }, items.map((x) => typeof x === "string" ? h("p", { text: x }) : x)));
  }

  // ================================================================== crypto helpers in the browser (hash playground, tamper preview)
  const enc = new TextEncoder();
  async function sha256Hex(data) {
    if (!(window.crypto && crypto.subtle)) throw new Error("this browser cannot hash here; open the dashboard at http://127.0.0.1");
    const buf = await crypto.subtle.digest("SHA-256", typeof data === "string" ? enc.encode(data) : data);
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  const hexBits = (hex) => hex.split("").flatMap((c) => parseInt(c, 16).toString(2).padStart(4, "0").split("").map(Number));
  /** Same bytes as Python json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=True). */
  function canonical(v) {
    if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
    if (v && typeof v === "object") return "{" + Object.keys(v).sort().map((k) => ascii(JSON.stringify(k)) + ":" + canonical(v[k])).join(",") + "}";
    return ascii(JSON.stringify(v));
  }
  const ascii = (s) => s.replace(/[\u0080-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));

  window.PQLAB = { runJob, resultCard, runInto, bitGrid, histogram, heatmap, lineChart, sha256Hex, canonical, hexBits, MODELS };

  // ================================================================== Watermark X-ray
  function xrayView(res) {
    const n = res.n_code, k = res.n_payload;
    const conf = Math.max(1e-6, ...res.logits.map(Math.abs));
    const code = res.logits.map((z, i) => {
      const bit = z > 0 ? 1 : 0, want = res.expected_code[i];
      return { tone: bit === want ? "ok" : "bad", a: Math.abs(z) / conf,
               t: "value " + i + (i < k ? " (payload)" : " (repair)") + ": score " + z.toFixed(3) + ", read " + bit + ", should be " + want };
    });
    const pay = res.expected_payload.map((b, i) => {
      const got = res.decoded_ok ? res.decoded[i] : null;
      return { tone: got === null ? "dim" : got === b ? "ok" : "bad", t: "payload bit " + i + ": signed record says " + b + (got === null ? ", could not be repaired" : ", model says " + got) };
    });
    const good = res.verdict === "VERIFIED";
    return h("div", { class: "xray" },
      h("div", { class: "xsteps" },
        xstep("1", "Carrier", res.carrier.length + " numbers", "The " + res.settings.layer + " weights, averaged over its output filters."),
        xstep("2", "Secret projection", n + " scores", "Each score = the 576 numbers × one row of the secret ±1 matrix made from the watermark key."),
        xstep("3", "Raw bits", (n - res.raw_wrong) + " / " + n + " right", "Score above 0 → 1, below 0 → 0. Red squares are wrong before repair."),
        xstep("4", "Repair (" + res.settings.ecc + ")", res.decoded_ok ? res.corrected + " bytes fixed" : "failed", "Reed-Solomon fixes damaged bytes using the repair values."),
        xstep("5", "Compare", res.decoded_ok ? res.payload_match + " / " + k + " match" : "nothing to compare", "The 256 bits must equal SHA-256 of the signed manifest.", good ? "ok" : "bad")),
      h("div", { class: "grid wide" },
        h("div", { class: "card" }, h("h3", { text: "1 · The carrier: what the watermark lives in" }),
          h("p", { class: "cap2", text: "The " + res.carrier.length + " numbers the watermark is written into, as a " + Math.ceil(Math.sqrt(res.carrier.length)) + "×" + Math.ceil(Math.sqrt(res.carrier.length)) + " picture. Blue is positive, amber is negative. To the eye it looks like ordinary weights: the code is invisible without the key." }),
          heatmap(res.carrier)),
        h("div", { class: "card" }, h("h3", { text: "2 · The " + n + " scores and how safe they are" }),
          h("p", { class: "cap2", text: "Each bar counts scores in a range. Scores far from the 0 line are safe; a score near 0 could flip. Weakest score (margin): " + res.margin.toFixed(2) + ". With the right key the scores split into two clear groups; with a wrong key they pile up around 0." }),
          histogram(res.logits))),
      h("div", { class: "card" }, h("h3", { text: "3 · All " + n + " code values, before repair" }),
        h("p", { class: "cap2", text: "One square per value: the first " + k + " carry the payload, the rest are repair values (for rs32). Green means the value reads as it should, red means it is wrong. Brighter means a more confident score. Hover a square for its number." }),
        bitGrid(code, 32, "code values"),
        legend([["ok", "reads correctly"], ["bad", "wrong before repair"], ["dim", "fainter = less confident"]])),
      h("div", { class: "card" }, h("h3", { text: "4 · The 256-bit payload after repair, against the signed record" }),
        h("p", { class: "cap2", text: res.decoded_ok ? "After error correction " + res.payload_match + " of " + k + " bits equal SHA-256 of the signed manifest" + (res.payload_match === k ? ": this model carries this release's fingerprint." : ": it carries a different fingerprint.") : "The repair step gave up: the code was too damaged, or no watermark made with this key exists in this model. That is what an unsigned model or a wrong key looks like." }),
        bitGrid(pay, 32, "payload bits"),
        h("div", { class: "kv" }, kv("Key used", res.key), kv("Key fingerprint", res.fingerprint), kv("Error correction", res.settings.ecc + " (" + k + " → " + n + " values)"),
          kv("Wrong before repair", res.raw_wrong + " of " + n), kv("Bytes repaired", res.decoded_ok ? String(res.corrected) : "—"), kv("Margin", res.margin.toFixed(3)))));
  }
  const xstep = (n, t, v, d, tone) => h("div", { class: "xstep " + (tone || "") }, h("span", { class: "xn", text: n }), h("b", { text: t }), h("span", { class: "xv", text: v }), h("small", { text: d }));
  const kv = (k, v) => h("div", {}, h("span", { text: k }), h("b", { text: v }));

  async function renderXray() {
    const sel = await modelSelect("xr-model", S.xrayModel || MODELS.ours, { extra: labModels });
    const key = h("select", { id: "xr-key" }, [["ours", "Our watermark key"], ["mallory", "Mallory's key"], ["random", "A random key"]].map(([v, t]) => h("option", { value: v, text: t })));
    key.value = S.xrayKey || "ours";
    const out = h("div", { class: "section" });
    const go = async () => {
      S.xrayModel = sel.value; S.xrayKey = key.value;
      busy(out, "reading the hidden code…");
      try {
        const j = await runJob("lab.xray", { model: sel.value, key: key.value });
        if (!j.result || j.result.error) { out.replaceChildren(resultCard(j)); return; }
        out.replaceChildren(resultCard(j, { showChecks: false, why: j.result.verdict === "VERIFIED" ? "The hidden 256 bits equal the signed record's fingerprint." : "The hidden code does not match the signed record." }), xrayView(j.result));
      } catch (e) { out.replaceChildren(h("div", { class: "rcard bad" }, h("p", { class: "rwhy", text: e.message }))); }
    };
    const preset = (label, model, k) => h("button", { class: "btn sm", type: "button", text: label, onclick: () => { sel.value = model; key.value = k; go(); } });
    target().replaceChildren(
      labHead("Watermark X-ray", "See the hidden watermark inside a model, step by step: the numbers it lives in, the scores the secret key produces, every code value, the repair, and the final 256-bit fingerprint."),
      h("div", { class: "card" },
        h("div", { class: "form" }, h("div", { class: "field", style: { gridColumn: "1 / -1" } }, h("label", { for: "xr-model", text: "Model" }), sel),
          h("div", { class: "field" }, h("label", { for: "xr-key", text: "Read it with" }), key)),
        h("div", { class: "presets" }, h("span", { class: "faint", text: "Try:" }),
          preset("Our model", MODELS.ours, "ours"), preset("Unsigned model", MODELS.base, "ours"), preset("Mallory's model", MODELS.mallory, "ours"),
          preset("Our model, wrong key", MODELS.ours, "random"), preset("After 4-bit compression", MODELS.q4, "ours"), preset("After channel shuffling", MODELS.perm, "ours")),
        h("div", { class: "task-foot" }, h("span", { class: "last" }), h("button", { class: "btn primary", type: "button", text: "X-ray this model", onclick: go }))),
      out,
      explain("How to explain this screen", [
        "The watermark is not a file or a label. It is a pattern spread across 576 numbers inside one layer of the network.",
        "Only the secret watermark key tells you how to combine those numbers into 512 scores. Without it the numbers look like any other weights.",
        "Each score's sign is one bit. Reed-Solomon error correction then repairs damaged bytes, giving 256 bits.",
        "Those 256 bits must equal SHA-256 of the signed manifest. If they do, the model is bound to that signed record.",
        "Try the presets: our model is all green; an unsigned model or a wrong key gives scores around 0 and roughly half the squares red; compression leaves it green; channel shuffling scrambles it."]));
    if (S.xrayAuto) { S.xrayAuto = false; go(); }
  }

  // ================================================================== Attack lab
  const ATTACKS = [
    { id: "noise_all", group: "Everyday changes", name: "Random noise", sub: "every weight", min: 0.01, max: 1, step: 0.01, def: 0.1, unit: "× spread", p6: (s) => "noise_all_s" + s },
    { id: "noise_carrier", group: "Everyday changes", name: "Noise on the watermark layer", sub: "aimed attack", min: 0.1, max: 2, step: 0.05, def: 0.5, unit: "× spread", p6: (s) => "noise_carrier_s" + s },
    { id: "prune_global", group: "Everyday changes", name: "Delete small weights", sub: "pruning, whole model", min: 0.1, max: 0.95, step: 0.05, def: 0.5, unit: "deleted", pctUnit: true, p6: (s) => "prune_global_" + s },
    { id: "prune_layer", group: "Everyday changes", name: "Delete small weights per layer", sub: "pruning, each layer", min: 0.1, max: 0.9, step: 0.05, def: 0.3, unit: "deleted", pctUnit: true, p6: (s) => "prune_layer_" + s },
    { id: "quantize", group: "Everyday changes", name: "Compress weights", sub: "quantization, per tensor", min: 2, max: 8, step: 1, def: 4, unit: "bits", p6: (s) => "quant_pt_" + s },
    { id: "quantize_pc", group: "Everyday changes", name: "Compress per channel", sub: "quantization, per channel", min: 2, max: 8, step: 1, def: 4, unit: "bits", p6: (s) => "quant_pc_" + s },
    { id: "half", group: "Everyday changes", name: "16-bit floats", sub: "half precision", p6: () => "half" },
    { id: "rescale", group: "Everyday changes", name: "Rescale channels", sub: "same answers", min: 1.5, max: 20, step: 0.5, def: 10, unit: "× max", p6: (s) => "rescale_all_x" + s },
    { id: "finetune", group: "Training (slow on CPU)", name: "Retrain", sub: "20% of the data", min: 1, max: 5, step: 1, def: 1, unit: "epochs", slow: true, p6: (s) => "finetune_e" + s + "_lr0.01" },
    { id: "permute_out", group: "Deliberate tricks", name: "Shuffle layer outputs", sub: "same answers", p6: () => "permute_out_carrier" },
    { id: "permute_in", group: "Deliberate tricks", name: "Shuffle layer inputs", sub: "same answers", p6: () => "permute_in_carrier" },
    { id: "permute_all", group: "Deliberate tricks", name: "Shuffle every layer", sub: "same answers", p6: () => "permute_all" },
    { id: "overwrite", group: "Deliberate tricks", name: "Overwrite with a fake mark", sub: "retrain, slow on CPU", min: 1, max: 10, step: 1, def: 2, unit: "epochs", slow: true, p6: () => "overwrite_128bit" },
  ];

  async function renderAttack() {
    const R = S.results || (S.results = await api("/api/results"));
    const summary = Object.fromEntries(R.phase6.summary.map((r) => [r.attack_id, r]));
    let cur = ATTACKS.find((a) => a.id === (S.attackId || "noise_all"));
    const model = await modelSelect("al-model", S.attackModel || MODELS.ours, { attacks: false });
    const acc = h("input", { type: "checkbox", id: "al-acc" });
    acc.checked = !!S.attackAcc;
    const slider = h("input", { type: "range", id: "al-strength" });
    const sval = h("b", { class: "sval mono" });
    const sbox = h("div", { class: "field" }, h("label", { for: "al-strength", text: "Strength" }), h("div", { class: "srow" }, slider, sval));
    const prior = h("div", { class: "prior" });
    const out = h("div", { class: "section" });
    const hist = h("div", { class: "section" });
    const fmtS = (a, v) => a.pctUnit ? Math.round(v * 100) + "% " + a.unit : (a.unit ? (Number.isInteger(v) ? v : v.toFixed(2)) + " " + a.unit : "");
    const setAttack = (a) => {
      cur = a; S.attackId = a.id;
      cards.querySelectorAll(".acard").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.id === a.id)));
      sbox.hidden = a.min === undefined;
      const saved = (S.attackStrengths || {})[a.id];   // remembered per attack: 4 bits must not become 4 for pruning
      if (a.min !== undefined) { slider.min = a.min; slider.max = a.max; slider.step = a.step; slider.value = saved !== undefined ? saved : a.def; }
      showStrength();
    };
    const showStrength = () => {
      const v = Number(slider.value);
      sval.textContent = cur.min === undefined ? "" : fmtS(cur, v);
      // what the Phase 6 suite measured for the closest setting
      const id = cur.p6(cur.min === undefined ? null : (Number.isInteger(v) ? v : Number(v.toFixed(2))));
      const r = summary[id];
      prior.replaceChildren(r ? h("span", {}, h("span", { class: "faint", text: "Phase 6 measured this exact setting: " }),
        h("b", { class: r.verified_rate === 1 ? "okc" : "badc", text: pct(r.verified_rate, 0) + " verified" }), " · accuracy after " + pct(r.mean_acc) + " · " + fix(r.runs, 0) + " runs")
        : h("span", { class: "faint", text: "Phase 6 did not run this exact setting; run it here to find out." }));
    };
    slider.addEventListener("input", showStrength);
    const groups = [...new Set(ATTACKS.map((a) => a.group))];
    const cards = h("div", { class: "acards" }, groups.map((g) => h("div", { class: "agroup" }, h("div", { class: "eyebrow", text: g }),
      h("div", { class: "arow" }, ATTACKS.filter((a) => a.group === g).map((a) => h("button", { type: "button", class: "acard", "data-id": a.id, "aria-pressed": "false",
        onclick: () => setAttack(a) }, h("b", { text: a.name }), h("small", { text: a.sub })))))));
    const run = async () => {
      S.attackModel = model.value; S.attackAcc = acc.checked;
      if (cur.min !== undefined) S.attackStrengths = Object.assign(S.attackStrengths || {}, { [cur.id]: slider.value });
      if (cur.slow && !(await P.modal({ title: "This attack retrains the model", ok: "Run it", body: h("p", { text: "On a laptop CPU each epoch takes a few minutes. The rest of the dashboard keeps working while it runs." }) }))) return;
      busy(out, "attacking a copy of the model, then verifying it…");
      try {
        const j = await runJob("lab.attack", { model: model.value, attack: cur.id, strength: cur.min === undefined ? 0 : slider.value, accuracy: acc.checked });
        if (!j.result || j.result.error) { out.replaceChildren(resultCard(j)); return; }
        const res = j.result;
        if (!labModels.includes(res.lab_model)) labModels.unshift(res.lab_model);
        out.replaceChildren(resultCard(j, { why: res.verdict === "VERIFIED" ? "The watermark survived: the attacked copy still proves it is ours." : "The watermark was removed or damaged beyond repair." }), attackView(res));
        hist.prepend(h("div", { class: "hrow" }, h("span", { class: "chip " + (res.verdict === "VERIFIED" ? "ok" : "bad"), text: res.verdict }),
          h("span", { text: res.label + (cur.min === undefined ? "" : " · " + fmtS(cur, Number(res.strength))) }),
          h("span", { class: "faint mono", text: res.n_flipped + "/" + res.n_code + " flipped" + (res.acc_after !== null ? " · acc " + pct(res.acc_after) : "") }),
          h("button", { class: "btn ghost sm", type: "button", text: "X-ray", onclick: () => { S.xrayModel = res.lab_model; S.xrayKey = "ours"; S.xrayAuto = true; location.hash = "#labs/xray"; } })));
      } catch (e) { out.replaceChildren(h("div", { class: "rcard bad" }, h("p", { class: "rwhy", text: e.message }))); }
    };
    target().replaceChildren(
      labHead("Attack lab", "Play the thief. Pick an attack and how hard to push it; the lab damages a copy of a signed model (your real models are never changed), then runs the real verifier on it and shows which code bits flipped."),
      h("div", { class: "card" }, cards,
        h("div", { class: "form" }, sbox,
          h("div", { class: "field", style: { gridColumn: "span 2" } }, h("label", { for: "al-model", text: "Signed model to attack" }), model),
          h("div", { class: "field check" }, acc, h("label", { for: "al-acc", text: "Also measure accuracy (needs CIFAR-10, ~30 s)" }))),
        prior,
        h("div", { class: "task-foot" }, h("span", { class: "last" }), h("button", { class: "btn primary", type: "button", text: "Attack and verify", onclick: run }))),
      out,
      h("section", { class: "section" }, h("h2", { text: "This session's attacks" }), hist),
      explain("How to explain this screen", [
        "A thief who copies a model may change it to erase the proof. These are the same attacks as the Phase 6 suite.",
        "Everyday changes (noise, pruning, compression, rescaling) are what happens when people shrink or tweak a model. The watermark should survive them while the model is still useful.",
        "Retraining slowly rewrites the weights; in Phase 6 even 10 epochs on all the data did not remove it.",
        "Deliberate tricks: shuffling the channels feeding the watermark layer keeps the model's answers identical but scrambles the code, which is the main weakness and the next thing to fix. Overwriting with a second watermark also works, at an accuracy cost.",
        "The grey line under the controls shows what the full Phase 6 suite measured for the same setting, across 3 models."]));
    setAttack(cur);
    if (hist.childElementCount === 0) hist.append(h("p", { class: "faint", text: "Attacks you run appear here, with a link to X-ray each attacked copy." }));
  }

  function attackView(res) {
    const conf = Math.max(1e-6, ...res.logits.map(Math.abs));
    const cells = res.flipped.map((f, i) => ({ tone: f ? "bad" : "ok", a: Math.abs(res.logits[i]) / conf,
      t: "value " + i + ": score " + res.clean_logits[i].toFixed(2) + " → " + res.logits[i].toFixed(2) + (f ? " (flipped)" : "") }));
    const drop = res.acc_after !== null && res.acc_clean ? (res.acc_clean - res.acc_after) * 100 : null;
    return h("div", { class: "grid wide" },
      h("div", { class: "card" }, h("h3", { text: "Code values flipped by the attack" }),
        h("p", { class: "cap2", text: res.n_flipped + " of " + res.n_code + " values changed sign compared with the clean model (" + pct(res.n_flipped / res.n_code) + "). Error correction can repair a limited number of damaged bytes; " + (res.decoded_ok ? res.corrected + " bytes were repaired here." : "here the damage was too much.") }),
        bitGrid(cells, 32, "flipped values"), legend([["ok", "unchanged"], ["bad", "flipped"]])),
      h("div", { class: "card" }, h("h3", { text: "What the attack cost" }),
        h("div", { class: "meters" },
          meter("Model accuracy", res.acc_clean, res.acc_after, (v) => pct(v), "measure accuracy to see this"),
          meter("Weakest score (margin)", res.clean_margin, res.margin, (v) => v.toFixed(2), "", Math.max(res.clean_margin, res.margin))),
        h("p", { class: "cap2", text: drop === null ? "Tick “Also measure accuracy” to see whether the attacked model is still useful." :
          drop <= 5 ? "Accuracy dropped " + drop.toFixed(1) + " points, so the model is still useful. " + (res.verdict === "VERIFIED" ? "And the watermark survived." : "And the watermark is gone: this counts as a successful removal.")
            : "Accuracy dropped " + drop.toFixed(1) + " points: the model is ruined, so " + (res.verdict === "VERIFIED" ? "the watermark even outlived the model." : "losing the watermark here does not help a thief.") }),
        h("div", { class: "kv" }, kv("Attack", res.label), kv("Parameters", JSON.stringify(res.params)), kv("Attacked copy", res.lab_model), kv("Time", res.seconds + " s"))));
  }
  function meter(label, before, after, fmt, empty, max) {
    max = max || 1;
    const row = (name, v, cls) => h("div", { class: "mrow" }, h("span", { text: name }), h("div", { class: "mbar" }, h("i", { class: cls, style: { width: (v === null || v === undefined ? 0 : Math.max(0, Math.min(1, v / max)) * 100) + "%" } })),
      h("b", { class: "mono", text: v === null || v === undefined ? "—" : fmt(v) }));
    return h("div", { class: "meter" }, h("div", { class: "mlabel", text: label }), row("before", before, "b"), row("after", after, "a"),
      (after === null || after === undefined) && empty ? h("small", { class: "faint", text: empty }) : null);
  }

  // ================================================================== Tamper lab
  async function renderTamper() {
    const I = await api("/api/inspect");
    if (!I.ours) { target().replaceChildren(h("div", { class: "empty", text: "No release/signed_manifest.json in this project yet (Phase 2)." })); return; }
    const M = I.ours.manifest;
    const f = {
      dev: h("input", { type: "text", id: "tp-dev", spellcheck: "false" }), width: h("input", { type: "text", id: "tp-width" }),
      n: h("input", { type: "text", id: "tp-n" }), root: h("input", { type: "checkbox", id: "tp-root" }), sig: h("input", { type: "checkbox", id: "tp-sig" }),
      pay: h("input", { type: "checkbox", id: "tp-pay" }), key: h("input", { type: "checkbox", id: "tp-key" }), model: h("input", { type: "checkbox", id: "tp-model" }),
    };
    const reset = () => { f.dev.value = M.developer_id; f.width.value = M.model.width; f.n.value = M.dataset.num_samples; f.root.checked = f.sig.checked = f.pay.checked = f.key.checked = false; f.model.checked = true; preview(); };
    const live = h("div", { class: "section" });
    const out = h("div", { class: "section" });
    const edited = () => {
      const m = JSON.parse(JSON.stringify(M));
      m.developer_id = f.dev.value;
      if (/^\d+$/.test(f.width.value)) m.model.width = Number(f.width.value);
      if (/^\d+$/.test(f.n.value)) m.dataset.num_samples = Number(f.n.value);
      if (f.root.checked) { const r = m.dataset.merkle_root_sha256; m.dataset.merkle_root_sha256 = (r[0] !== "0" ? "0" : "1") + r.slice(1); }
      return m;
    };
    let tok = 0;
    const preview = async () => {
      const my = ++tok;
      try {
        const [a, b] = await Promise.all([sha256Hex(canonical(M)), sha256Hex(canonical(edited()))]);
        if (my !== tok) return;
        const ba = hexBits(a), bb = hexBits(b), diff = ba.filter((x, i) => x !== bb[i]).length;
        const same = a === b;
        live.replaceChildren(h("div", { class: "card" },
          h("h3", { text: "What your edit does to the fingerprint (computed live in your browser)" }),
          h("div", { class: "hashpair" }, h("div", {}, h("span", { class: "faint", text: "signed record" }), h("code", { text: a })),
            h("div", {}, h("span", { class: "faint", text: "edited record" }), h("code", { class: same ? "" : "changed", text: b }))),
          h("p", { class: "cap2", text: same ? "No change to the record yet. Edit a field above." + (f.sig.checked || f.pay.checked || f.key.checked ? " (The signature, payload file and key options change files next to the record, not the record itself.)" : "")
            : diff + " of 256 bits changed (" + Math.round(diff / 2.56) + "%). One small edit changes about half the fingerprint, so the old signature and the watermark inside every model no longer match." }),
          bitGrid(ba.map((x, i) => ({ tone: x === bb[i] ? "dim" : "bad", t: "bit " + i + ": " + x + " → " + bb[i] })), 32, "fingerprint bits"),
          a === I.ours.sha256 ? h("p", { class: "cap2 okc", text: "Check: the browser's SHA-256 of the signed record equals payload.hex, exactly what the Python code computes." }) : null));
      } catch (e) { live.replaceChildren(h("p", { class: "faint", text: e.message })); }
    };
    Object.values(f).forEach((el) => { el.addEventListener("input", preview); el.addEventListener("change", preview); });
    const run = async () => {
      const params = { developer_id: f.dev.value !== M.developer_id ? f.dev.value : "", width: String(f.width.value) !== String(M.model.width) ? f.width.value : "",
        num_samples: String(f.n.value) !== String(M.dataset.num_samples) ? f.n.value : "", flip_root: f.root.checked, flip_signature: f.sig.checked,
        flip_payload: f.pay.checked, wrong_key: f.key.checked, model: f.model.checked ? MODELS.ours : "" };
      const any = params.developer_id || params.width || params.num_samples || params.flip_root || params.flip_signature || params.flip_payload || params.wrong_key;
      await runInto(out, "lab.tamper", params, { expect: any ? "REJECTED" : "VERIFIED", busy: "editing a temporary copy of the release, then verifying…",
        after: (j, box) => { if (j.result && j.result.changes) box.append(h("div", { class: "card" }, h("h3", { text: "What was changed in the copy" }),
          j.result.changes.length ? h("ul", { class: "plain" }, j.result.changes.map((c) => h("li", {}, h("b", { text: c.what }), ": ", h("code", { text: c.old }), " → ", h("code", { text: c.new }))))
            : h("p", { class: "faint", text: "Nothing: this was the untouched release." }))); } });
    };
    const preset = (label, fn) => h("button", { class: "btn sm", type: "button", text: label, onclick: () => { reset(); fn(); preview(); run(); } });
    const field = (id, label, el, span) => h("div", { class: "field", style: span ? { gridColumn: "span " + span } : null }, h("label", { for: id, text: label }), el);
    const check = (el, label) => h("div", { class: "field check" }, el, h("label", { for: el.id, text: label }));
    target().replaceChildren(
      labHead("Tamper lab", "Play the forger. Change anything in the signed birth certificate and see that verification catches it. The edits are made to a temporary copy: your real release/ folder is never touched."),
      h("div", { class: "card" },
        h("div", { class: "presets" }, h("span", { class: "faint", text: "Try:" }),
          preset("Untouched release", () => {}), preset("Steal the credit (rename developer)", () => { f.dev.value = "Mallory"; }),
          preset("Claim a bigger model", () => { f.width.value = "64"; }), preset("Change the dataset", () => { f.root.checked = true; }),
          preset("Forge one signature character", () => { f.sig.checked = true; }), preset("Use someone else's public key", () => { f.key.checked = true; })),
        h("div", { class: "form" }, field("tp-dev", "Developer id", f.dev), field("tp-width", "Model width", f.width), field("tp-n", "Number of training images", f.n),
          check(f.root, "Change 1 character of the dataset fingerprint (Merkle root)"), check(f.sig, "Change 1 character of the ML-DSA signature"),
          check(f.pay, "Change 1 character of payload.hex"), check(f.key, "Check with an unrelated public key"),
          check(f.model, "Also verify our signed model against the edited release")),
        h("div", { class: "task-foot" }, h("span", { class: "last" }), h("button", { class: "btn ghost", type: "button", text: "Reset", onclick: reset }),
          h("button", { class: "btn primary", type: "button", text: "Verify the edited copy", onclick: run }))),
      live, out,
      explain("How to explain this screen", [
        "The birth certificate (manifest) is signed with ML-DSA. A signature only matches the exact bytes that were signed.",
        "Change one letter of the developer name, the model size or the dataset fingerprint, and the record's SHA-256 changes in about half its bits (shown live above). The old signature no longer fits, so the release is REJECTED.",
        "Editing the signature itself fails too: you cannot make a valid ML-DSA signature without the secret key, not even with a quantum computer.",
        "Swapping in someone else's public key fails at the key-id check: the record names which key signed it.",
        "With “also verify our model” ticked, the model check stops at the same place: a tampered certificate can never vouch for a model."]));
    reset();
  }

  // ================================================================== Signing lab
  const SIZES = [{ n: "RSA-2048", pk: 256, sig: 256, q: false }, { n: "ECDSA P-256", pk: 64, sig: 64, q: false }, { n: "Ed25519", pk: 32, sig: 64, q: false }];
  async function renderSign() {
    const msg = h("textarea", { id: "sg-msg", rows: "3", spellcheck: "false" }), chk = h("textarea", { id: "sg-chk", rows: "3", spellcheck: "false" });
    msg.value = chk.value = "Model SmallCNN, trained by our team on CIFAR-10 (50,000 images).";
    const out = h("div", { class: "section" });
    const run = async () => {
      busy(out, "making a throwaway ML-DSA-65 key pair, signing, verifying…");
      try {
        const j = await runJob("lab.sign", { message: msg.value, check: chk.value });
        if (!j.result || j.result.error) { out.replaceChildren(resultCard(j)); return; }
        const r = j.result, all = SIZES.concat([{ n: "ML-DSA-65 (ours)", pk: r.pk_bytes, sig: r.sig_bytes, q: true }]);
        const mx = Math.max(...all.map((x) => x.sig));
        out.replaceChildren(resultCard(j, { showChecks: false, why: r.ok ? "The signature matches the text exactly." : "The text the verifier received is not the text that was signed, so the signature does not match." }),
          h("div", { class: "grid wide" },
            h("div", { class: "card" }, h("h3", { text: "This signature" }),
              h("div", { class: "kv" }, kv("Algorithm", r.alg + " (NIST FIPS 204)"), kv("Public key", r.pk_bytes + " bytes, key id " + r.key_id.slice(0, 16) + "…"),
                kv("Secret key", r.sk_bytes + " bytes (never leaves this computer)"), kv("Signature", r.sig_bytes + " bytes"),
                kv("Time", "keys " + r.ms.keygen + " ms · sign " + r.ms.sign + " ms · verify " + r.ms.verify + " ms")),
              h("div", { class: "hexbox" }, h("span", { class: "faint", text: "first bytes of the signature" }), h("code", { text: r.sig_hex + "…" })),
              h("div", { class: "hashpair" }, h("div", {}, h("span", { class: "faint", text: "SHA-256 of the signed text" }), h("code", { text: r.sha_message })),
                h("div", {}, h("span", { class: "faint", text: "SHA-256 of the checked text" }), h("code", { class: r.sha_message === r.sha_check ? "" : "changed", text: r.sha_check })))),
            h("div", { class: "card" }, h("h3", { text: "Signature size compared with today's methods" }),
              h("p", { class: "cap2", text: "Post-quantum signatures are much bigger. That is why the project hides a 256-bit fingerprint in the model and ships the " + r.sig_bytes + "-byte signature next to it." }),
              h("div", { class: "sizes" }, all.map((x) => h("div", { class: "srow2" }, h("span", { text: x.n }),
                h("div", { class: "mbar" }, h("i", { class: x.q ? "a" : "b", style: { width: Math.max(1.5, x.sig / mx * 100) + "%" } })),
                h("b", { class: "mono", text: x.sig + " B" }), h("small", { class: x.q ? "okc" : "badc", text: x.q ? "quantum-safe" : "breakable by a large quantum computer" })))))));
      } catch (e) { out.replaceChildren(h("div", { class: "rcard bad" }, h("p", { class: "rwhy", text: e.message }))); }
    };
    const field = (id, label, el) => h("div", { class: "field", style: { gridColumn: "1 / -1" } }, h("label", { for: id, text: label }), el);
    target().replaceChildren(
      labHead("Signing lab", "What a post-quantum signature does, on any text you type. A throwaway key pair is made each time; the project's real keys are never used here."),
      h("div", { class: "card" }, h("div", { class: "form" }, field("sg-msg", "Text the developer signs", msg), field("sg-chk", "Text the verifier receives", chk)),
        h("div", { class: "presets" }, h("span", { class: "faint", text: "Try:" }),
          h("button", { class: "btn sm", type: "button", text: "Same text", onclick: () => { chk.value = msg.value; run(); } }),
          h("button", { class: "btn sm", type: "button", text: "Change one letter", onclick: () => { const t = msg.value; const i = Math.max(0, t.search(/[a-z]/i)); chk.value = t.slice(0, i) + (t[i] === "X" ? "Y" : "X") + t.slice(i + 1); run(); } }),
          h("button", { class: "btn sm", type: "button", text: "Change 50,000 to 50,001", onclick: () => { chk.value = msg.value.replace("50,000", "50,001"); run(); } })),
        h("div", { class: "task-foot" }, h("span", { class: "last" }), h("button", { class: "btn primary", type: "button", text: "Sign and verify", onclick: run }))),
      out,
      explain("How to explain this screen", [
        "A digital signature proves who wrote something and that it was not changed. The secret key signs; the public key, which anyone can have, checks.",
        "Change even one character and the check fails.",
        "RSA and elliptic-curve signatures, used almost everywhere today, could be forged by a large quantum computer running Shor's algorithm. ML-DSA (NIST FIPS 204, 2024) is designed to resist that, so a model signed today stays trustworthy for years.",
        "The cost is size: an ML-DSA-65 signature is about 3.3 KB. That is why the project signs a manifest and hides only its 256-bit fingerprint inside the model."]));
  }

  // ================================================================== Hash and Merkle playground (all in the browser)
  async function renderHash() {
    const a = h("input", { type: "text", id: "hs-a", spellcheck: "false" }), b = h("input", { type: "text", id: "hs-b", spellcheck: "false" });
    a.value = "cat"; b.value = "cats";
    const hashOut = h("div", { class: "section" });
    const drawHash = async () => {
      try {
        const [x, y] = await Promise.all([sha256Hex(a.value), sha256Hex(b.value)]);
        const bx = hexBits(x), by = hexBits(y), d = bx.filter((v, i) => v !== by[i]).length;
        hashOut.replaceChildren(h("div", { class: "hashpair" }, h("div", {}, h("span", { class: "faint", text: "SHA-256 of A" }), h("code", { text: x })),
          h("div", {}, h("span", { class: "faint", text: "SHA-256 of B" }), h("code", { class: x === y ? "" : "changed", text: y }))),
          h("p", { class: "cap2", text: x === y ? "Same input, same fingerprint, every time." : d + " of 256 bits differ (" + Math.round(d / 2.56) + "%). A tiny change in the input changes about half the fingerprint." }),
          bitGrid(bx.map((v, i) => ({ tone: v === by[i] ? "dim" : "bad", t: "bit " + i })), 32, "differing bits"));
      } catch (e) { hashOut.replaceChildren(h("p", { class: "faint", text: e.message })); }
    };
    [a, b].forEach((el) => el.addEventListener("input", drawHash));
    const names = ["airplane", "car", "bird", "cat", "deer", "dog", "frog", "horse"];
    const leaves = names.map((n, i) => { const el = h("input", { type: "text", id: "mk-" + i, spellcheck: "false", "aria-label": "image " + i }); el.value = "image " + i + ": " + n; return el; });
    const orig = leaves.map((l) => l.value);
    const tree = h("div", { class: "mtree" });
    let original = null;
    const drawTree = async () => {
      const level0 = await Promise.all(leaves.map((l, i) => sha256Hex("leaf|" + i + "|" + l.value)));
      const levels = [level0];
      while (levels[levels.length - 1].length > 1) {
        const prev = levels[levels.length - 1], next = [];
        for (let i = 0; i < prev.length; i += 2) next.push(await sha256Hex("node|" + prev[i] + prev[i + 1]));
        levels.push(next);
      }
      if (!original) original = levels.map((l) => l.slice());
      const changed = levels.map((l, li) => l.map((v, i) => v !== original[li][i]));
      tree.replaceChildren(...levels.slice().reverse().map((l, ri) => {
        const li = levels.length - 1 - ri;
        return h("div", { class: "mlevel" }, h("span", { class: "mlab", text: li === levels.length - 1 ? "root" : li === 0 ? "leaves" : "level " + li }),
          h("div", { class: "mnodes", style: { gridTemplateColumns: "repeat(" + l.length + ", minmax(0, 1fr))" } },
            l.map((v, i) => h("div", { class: "mnode" + (changed[li][i] ? " changed" : "") + (li === levels.length - 1 ? " root" : ""), title: v }, v.slice(0, 8)))));
      }));
      const rootChanged = changed[changed.length - 1][0];
      treeNote.textContent = rootChanged ? "One edited image changed every box on its path up to the root (red). The root is the dataset's single fingerprint, so any change to any image is caught."
        : "Edit any image below: watch which boxes change.";
    };
    const treeNote = h("p", { class: "cap2" });
    leaves.forEach((l) => l.addEventListener("input", drawTree));
    const I = await api("/api/inspect").catch(() => null);
    const ds = I && I.ours ? I.ours.manifest.dataset : null;
    target().replaceChildren(
      labHead("Hash and Merkle", "The two ideas behind the dataset fingerprint, computed live in your browser. Type anything."),
      h("div", { class: "card" }, h("h2", { text: "1 · A hash is a fingerprint" }),
        h("div", { class: "form" }, h("div", { class: "field" }, h("label", { for: "hs-a", text: "Input A" }), a), h("div", { class: "field" }, h("label", { for: "hs-b", text: "Input B" }), b)),
        hashOut),
      h("div", { class: "card" }, h("h2", { text: "2 · A Merkle tree turns many fingerprints into one" }),
        h("p", { class: "cap2", text: "8 pretend images are hashed one by one (the leaves), then hashed together in pairs until one hash is left: the root. The project does the same with all 50,000 CIFAR-10 training images." }),
        tree, treeNote,
        h("div", { class: "mleaves" }, leaves.map((l) => h("div", { class: "field" }, l))),
        h("div", { class: "task-foot" }, h("span", { class: "last" }), h("button", { class: "btn ghost", type: "button", text: "Reset images", onclick: () => { leaves.forEach((l, i) => { l.value = orig[i]; }); drawTree(); } }))),
      ds ? h("div", { class: "card" }, h("h2", { text: "3 · The real one in this project" }),
        h("div", { class: "kv" }, kv("Dataset", ds.name + ", " + ds.split + " split"), kv("Images", ds.num_samples.toLocaleString()),
          kv("Leaf", ds.leaf_format), kv("Node", ds.node_format)),
        h("div", { class: "hexbox" }, h("span", { class: "faint", text: "Merkle root (signed in the manifest)" }), h("code", { text: ds.merkle_root_sha256 })),
        h("p", { class: "cap2", text: "The playground above uses a simplified leaf (\"leaf|index|text\"). The project's leaf hashes the image's position, its label and every pixel, so re-labelling, re-ordering or editing any image changes the root. Run “Verify the signed release” with “Also re-hash CIFAR-10” in Phase 2 to recompute it from the real images." })) : null);
    drawHash(); drawTree();
  }

  // ================================================================== Release and keys inspector
  async function renderInspect() {
    const I = await api("/api/inspect");
    const o = I.ours;
    if (!o) { target().replaceChildren(h("div", { class: "empty", text: "No signed release found (release/signed_manifest.json)." })); return; }
    const mark = (ok) => h("span", { class: "mono " + (ok ? "okc" : "badc"), text: ok ? "OK" : "NO" });
    const tick = (label, ok, detail) => h("div", { class: "trow" }, mark(ok), h("span", { text: label }), detail ? h("small", { class: "faint mono", text: detail }) : null);
    const m = o.manifest;
    const fields = [["Developer", m.developer_id], ["Created", m.created_utc], ["Signature algorithm", m.signature_algorithm], ["Key id", m.key_id],
      ["Model", m.model.architecture + ", width " + m.model.width + ", " + m.model.num_params.toLocaleString() + " parameters"],
      ["Dataset", m.dataset.name + " " + m.dataset.split + ", " + m.dataset.num_samples.toLocaleString() + " images"], ["Merkle root", m.dataset.merkle_root_sha256],
      ["Watermark", m.watermark.scheme + ", " + m.watermark.payload_bits + " payload bits"], ["Format version", String(m.format_version)]];
    const vbox = h("div", { class: "section" });
    const mo = I.mallory;
    target().replaceChildren(
      labHead("Release and keys", "The signed birth certificate as it is stored in release/, what is inside it, and the checks that can be done just by reading files. The signature itself is checked by the button below."),
      h("div", { class: "grid wide" },
        h("div", { class: "card" }, h("h3", { text: "The manifest (what is signed)" }),
          h("div", { class: "mtable" }, fields.map(([k, v]) => h("div", {}, h("span", { text: k }), h("code", { text: v })))),
          h("div", { class: "hexbox" }, h("span", { class: "faint", text: "the exact " + o.canonical_bytes + " bytes that are signed (canonical JSON, first part)" }), h("code", { class: "wrap", text: o.canonical_preview }))),
        h("div", { class: "card" }, h("h3", { text: "Checks from the files" }),
          h("div", { class: "trows" },
            tick("SHA-256 of the manifest equals payload.hex", o.payload_matches, o.sha256.slice(0, 24) + "…"),
            tick("Key id in the manifest equals SHA-256 of release/public_key.bin", o.key_id_matches, o.key_id_of_release_key),
            tick("Your trusted keys/public_key.bin is present", o.trusted_key_present),
            tick("Trusted key equals the key shipped in release/", o.trusted_key_matches_release),
            tick("Our watermark key is present and matches the models", I.keys.ours.fingerprint && I.keys.ours.fingerprint === I.keys.ours.expected, (I.keys.ours.fingerprint || "missing") + " (models expect " + I.keys.ours.expected + ")"),
            tick("Every frozen Phase 4/5 model is unchanged since before the attacks", I.frozen_hashes.length > 0 && I.frozen_hashes.every((x) => x.same), I.frozen_hashes.filter((x) => x.same).length + " of " + I.frozen_hashes.length + " hashes match")),
          h("div", { class: "kv" }, kv("Signature", o.signature_bytes.toLocaleString() + " bytes"), kv("Public key", (o.public_key_bytes || "—") + " bytes"),
            kv("Canonical manifest", o.canonical_bytes + " bytes")),
          h("div", { class: "hexbox" }, h("span", { class: "faint", text: "signature (start … end)" }), h("code", { text: o.signature_head + " … " + o.signature_tail })),
          h("div", { class: "task-foot" }, h("span", { class: "last" }), h("button", { class: "btn primary", type: "button", text: "Verify the signature now", onclick: () => runInto(vbox, "p2.verify_release", {}, { expect: "VERIFIED" }) })),
          vbox)),
      h("div", { class: "card" }, h("h3", { text: "The 256-bit payload hidden in every signed model" }),
        h("p", { class: "cap2", text: "payload = SHA-256(canonical manifest). These are the bits the watermark carries. Blue squares are 1, dark squares are 0." }),
        bitGrid(o.payload_bits.split("").map((b, i) => ({ tone: b === "1" ? "acc" : "dim", t: "bit " + i + " = " + b })), 32, "payload bits"),
        h("div", { class: "hexbox" }, h("code", { text: o.sha256 }))),
      mo ? h("div", { class: "card" }, h("h3", { text: "Mallory's release, for comparison" }),
        h("p", { class: "cap2", text: "A second developer with her own key and her own signed record. Same dataset, different signer, so a completely different payload: her models can never pass as ours." }),
        h("div", { class: "cmp" }, ["Developer", "Key id", "Payload"].map((k, i) => h("div", { class: "cmprow" }, h("span", { text: k }),
          h("code", { text: [m.developer_id, m.key_id, o.sha256][i] }), h("code", { class: "changed", text: [mo.manifest.developer_id, mo.manifest.key_id, mo.sha256][i] }))))) : null,
      I.frozen_hashes.length ? h("details", { class: "explain" }, h("summary", { text: "Frozen model hashes (" + I.frozen_hashes.length + ")" }),
        h("div", { class: "tbl-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", { text: "Model" }), h("th", { text: "SHA-256 (frozen)" }), h("th", { text: "Now" }))),
          h("tbody", {}, I.frozen_hashes.map((x) => h("tr", {}, h("td", { class: "mono", text: x.path }), h("td", { class: "mono faint", text: x.frozen.slice(0, 16) + "…" }), h("td", {}, mark(x.same)))))))) : null);
  }

  // ================================================================== Home
  async function renderHome() {
    crumbs("Home");
    const [o, R] = await Promise.all([api("/api/overview"), api("/api/results")]);
    S.results = R;
    const t = R.phase6.totals;
    const base = R.baseline.map((b) => b.acc).filter(Boolean);
    const p4 = R.phase4.find((x) => x.config === "rs32/features.6.0/lam20");
    const done = o.phases.filter((p) => p.state === "done").length;
    const stats = h("div", { class: "stats" },
      P.stat(done + "/" + o.phases.length, "phases with results"),
      P.stat(base.length ? pct(base.reduce((a, b) => a + b, 0) / base.length) : "-", "accuracy without watermark"),
      P.stat(p4 ? fix(p4.diff_pts) + " pts" : "-", "cost of the watermark"),
      P.stat(t ? t.wm_verified + "/" + t.wm_runs : "-", "attacked copies still verified", "ok"),
      P.stat(t ? t.base_false_accepts + "/" + t.base_runs : "-", "unsigned models accepted", t && !t.base_false_accepts ? "ok" : "bad"),
      P.stat(t ? String(t.removed_types) : "-", "attack types that removed it", t && t.removed_types ? "bad" : "ok"));
    const track = h("div", { class: "track" },
      o.phases.map((p) => h("a", { class: "phase " + p.state, href: "#phase/" + p.n },
        h("div", { class: "n" }, h("span", { class: "sdot " + p.state }), "PHASE " + p.n), h("div", { class: "t", text: p.title }),
        p.metric ? [h("div", { class: "m", text: p.metric.value }), h("div", { class: "ml", text: p.metric.label })] : h("div", { class: "ml", text: p.plain }))),
      o.future.map((p) => h("div", { class: "phase future" }, h("div", { class: "n", text: "PHASE " + p.n }), h("div", { class: "t", text: p.title }), h("div", { class: "ml", text: p.plain }))));
    const chartBody = h("div", { class: "section" });
    const charts = h("section", { class: "section" }, h("div", { class: "section-head" }, h("h2", { text: "Results" }),
      h("a", { href: "#labs/results", class: "muted", text: "all results, tables and plots" })), chartBody);
    try { drawCharts(chartBody); } catch (e) { chartBody.replaceChildren(h("div", { class: "empty", text: "No Phase 6 results yet." })); }
    view.replaceChildren(
      h("div", { class: "hero" }, h("span", { class: "eyebrow", text: "Post-Quantum AI Provenance Watermarking" }),
        h("h1", { text: "Project control centre" }),
        h("p", { text: "An ML-DSA signed manifest bound to a CIFAR-10 CNN by a 256-bit watermark in its weights. Run any phase, use the interactive labs, and read the results. Everything runs this project's own code on this computer." }),
        h("div", { class: "hero2-btns" }, h("a", { class: "btn primary", href: "#labs", text: "Open the labs" }),
          h("button", { class: "btn", type: "button", text: "Run every check", onclick: () => P.runPipeline({ id: "check-all", title: "Run every check" }) }),
          h("a", { class: "btn ghost", href: "#labs/results", text: "Results and charts" }))),
      stats,
      charts,
      h("section", { class: "section" }, h("div", { class: "section-head" }, h("h2", { text: "Phases" }), h("span", { class: "muted", text: "open a phase to run its steps" })), track),
      h("section", { class: "section" }, h("div", { class: "section-head" }, h("h2", { text: "Run many steps at once" })),
        h("div", { class: "grid" }, o.pipelines.map((p) => h("div", { class: "card pipe" },
          h("div", { class: "section-head" }, h("h3", { text: p.title }), p.id === "rebuild" ? h("span", { class: "chip warn", text: "GPU recommended" }) : null),
          h("p", { class: "what", text: p.what }), h("div", { class: "flow" }, p.steps.map((s) => h("span", { text: s }))),
          h("div", { class: "foot" }, h("span", { class: "est", text: p.est }), h("button", { class: "btn " + (p.id === "check-all" ? "primary" : ""), type: "button", text: "Run", onclick: () => P.runPipeline(p) })))))));
  }

  // ================================================================== Labs: one page, one tab per tool
  const LAB_TABS = [
    ["verify", "Verify a model", "The auditor's check on any model: signature, model, hidden watermark, payload.", (root) => P.renderVerify(root)],
    ["xray", "Watermark X-ray", "Every value of the hidden code, the repair and the 256 payload bits.", (root) => renderXray()],
    ["attack", "Attack lab", "Attack a copy of a signed model at any strength, then verify it.", () => renderAttack()],
    ["tamper", "Tamper lab", "Edit a copy of the signed certificate and verify it.", () => renderTamper()],
    ["sign", "Signing lab", "ML-DSA-65 signatures on any text.", () => renderSign()],
    ["hash", "Hash and Merkle", "SHA-256 and the dataset fingerprint, live in the browser.", () => renderHash()],
    ["inspect", "Release and keys", "The signed certificate, keys and integrity checks.", () => renderInspect()],
    ["results", "Results and charts", "Charts, plots and every measured number.", (root) => renderResults2(root)],
  ];
  let labRoot = null;
  const target = () => labRoot || view;
  function labHead(title, text) {
    return h("div", { class: "lab-head" }, h("h2", { text: title }), text ? h("p", { class: "muted lede2", text }) : null);
  }
  async function renderLabs(tab) {
    const cur = LAB_TABS.find((x) => x[0] === tab) || LAB_TABS[0];
    crumbs("Labs", cur[1]);
    labRoot = h("div", { class: "section lab-body" });
    const bar = h("div", { class: "tabs labtabs", role: "tablist" }, LAB_TABS.map(([k, label]) => h("a", { role: "tab", href: "#labs/" + k,
      class: "tablink", "aria-selected": String(k === cur[0]), text: label })));
    view.replaceChildren(
      h("div", { class: "phase-head" }, h("span", { class: "eyebrow", text: "Interactive labs" }), h("h1", { text: "Labs" }),
        h("p", { class: "muted lede2", text: "All interactive tools in one place. Each tab runs this project's own code (verify/, embedding/, attacks/, crypto/) on this computer." })),
      bar, labRoot);
    try { await cur[3](labRoot); }
    catch (e) { labRoot.replaceChildren(h("div", { class: "empty", text: "Could not load this tool: " + e.message })); }
  }

  // ================================================================== Results with charts
  async function renderResults2(root) {
    const out = root || view;
    if (!root) crumbs("Labs", "Results and charts");
    S.results = await api("/api/results");
    const tabs = [["charts", "Charts"], ["phase7", "Phase 7"], ["attacks", "Phase 6 table"], ["plots", "Phase 6 plots"], ["phase4", "Phase 4"], ["baseline", "Phase 1"], ["docs", "Documents"]];
    if (!tabs.some(([k]) => k === S.resultsTab)) S.resultsTab = "charts";
    const body = h("div", { class: "section" });
    const bar = h("div", { class: "tabs", role: "tablist" }, tabs.map(([k, l]) => h("button", { type: "button", role: "tab", "aria-selected": String(S.resultsTab === k), text: l,
      onclick: (e) => { S.resultsTab = k; bar.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b === e.target))); draw(); } })));
    const draw = () => {
      if (S.resultsTab === "charts") return drawCharts(body);
      if (S.resultsTab === "phase7") return drawPhase7(body);
      return P.drawTab(body);
    };
    out.replaceChildren(labHead("Results and charts", "Every number the project has measured, read straight from the results files in this folder."), bar, body);
    draw();
  }
  function drawCharts(body) {
    const R = S.results, sum = R.phase6.summary;
    if (!sum.length) { body.replaceChildren(h("div", { class: "empty", text: "No Phase 6 results yet. Run the Phase 6 pipeline, then come back." })); return; }
    const clean = (sum.find((r) => r.family === "control") || {}).mean_acc;
    const fam = (prefix, re, name) => ({ name, pts: sum.filter((r) => re.test(r.attack_id)).map((r) => ({ x: Number(r.attack_id.match(re)[1]), y: r.mean_acc, ok: r.verified_rate === 1 })) });
    const ref = clean ? { y: clean - 0.05, label: "still useful above this line" } : undefined;
    const chart = (title, note, cfg) => h("div", { class: "card" }, h("h3", { text: title }), h("p", { class: "cap2", text: note }), lineChart(cfg));
    const charts = [
      chart("Random noise on every weight", "Accuracy after the attack. Green dots: watermark still VERIFIED on every copy; red: lost.", { series: [fam("", /^noise_all_s([\d.]+)$/, "noise")], xLabel: "noise strength (× each weight's spread)", yLabel: "accuracy", ref }),
      chart("Deleting the smallest weights (pruning)", "The watermark only disappears once the model is already useless.", { series: [fam("", /^prune_global_([\d.]+)$/, "global")], xLabel: "share of weights deleted", yLabel: "accuracy", ref, xFmt: (v) => Math.round(v * 100) + "%" }),
      chart("Compressing weights to fewer bits", "From 8 bits down to 2. Error correction repairs the damage down to 3 bits.", { series: [fam("", /^quant_pt_(\d+)$/, "per tensor")], xLabel: "bits per weight", yLabel: "accuracy", ref }),
      chart("Noise aimed at the watermark layer", "Even noise aimed straight at the watermark layer does not remove it.", { series: [fam("", /^noise_carrier_s([\d.]+)$/, "carrier")], xLabel: "noise strength", yLabel: "accuracy", ref }),
    ];
    const base = R.baseline.filter((b) => Number.isFinite(b.acc)), wm = R.phase4.find((x) => x.config === "rs32/features.6.0/lam20");
    const bars = h("div", { class: "card" }, h("h3", { text: "Accuracy with and without the watermark" }),
      h("p", { class: "cap2", text: "Average test accuracy over 3 seeds for each setting. The chosen design is rs32, layer features.6.0, λ = 20." }),
      h("div", { class: "sizes" },
        base.length ? barRow("No watermark (baseline)", base.reduce((a, b) => a + b.acc, 0) / base.length, "b") : null,
        R.phase4.slice().sort((a, b) => b.mean_wm_acc - a.mean_wm_acc).map((c) => barRow(c.config + (c === wm ? "  ← chosen" : ""), c.mean_wm_acc, c === wm ? "a" : "b"))));
    const t = R.phase6.totals;
    const fams = {};
    for (const r of sum.filter((r) => r.family !== "control")) { const f = (fams[r.family] = fams[r.family] || { held: 0, removed: 0, ruined: 0 }); f[P.outcome(r)[1] === "held" ? "held" : P.outcome(r)[1] === "removed" ? "removed" : "ruined"]++; }
    const stack = h("div", { class: "card" }, h("h3", { text: "Every attack type, by outcome" }),
      h("p", { class: "cap2", text: (t ? t.wm_verified + " of " + t.wm_runs + " attacked copies verified. " : "") + "Each square is one attack type: green = watermark held, red = removed while the model still worked, amber = lost only by ruining the model." }),
      h("div", { class: "famrows" }, Object.entries(fams).map(([k, v]) => h("div", { class: "famrow" }, h("span", { class: "mono", text: k }),
        bitGrid([].concat(Array(v.held).fill({ tone: "ok", t: "held" }), Array(v.removed).fill({ tone: "bad", t: "removed" }), Array(v.ruined).fill({ tone: "warn", t: "model ruined" })), 12, k)))),
      legend([["ok", "held"], ["bad", "removed (model still useful)"], ["warn", "lost only with a ruined model"]]));
    body.replaceChildren(h("div", { class: "grid wide" }, charts), h("div", { class: "grid wide" }, bars, stack));
  }
  const barRow = (name, v, cls) => h("div", { class: "srow2" }, h("span", { text: name }), h("div", { class: "mbar" }, h("i", { class: cls, style: { width: (v * 100) + "%" } })), h("b", { class: "mono", text: pct(v) }), h("small"));
  function drawPhase7(body) {
    const p7 = S.results.phase7;
    const has = p7.configs.length || p7.plots.length;
    const regen = (task) => async () => {   // run, then redraw the tables and plots with the result card kept on top
      const box = h("div"); body.prepend(box);
      const j = await runInto(box, task, {}, { expect: "PASSED" });
      if (j && j.status === "passed") { S.results = await api("/api/results").catch(() => S.results); drawPhase7(body); body.prepend(box); }
    };
    const runBtns = h("div", { class: "presets" }, h("span", { class: "faint", text: "Regenerate from your runs:" }),
      h("button", { class: "btn sm", type: "button", text: "Collect runs (P7.1)", onclick: regen("p7.collect") }),
      h("button", { class: "btn sm", type: "button", text: "Make plots", onclick: regen("p7.plots") }));
    if (!has) { body.replaceChildren(runBtns, h("div", { class: "empty", text: "No Phase 7 results yet. Click “Collect runs”, then “Make plots”." })); return; }
    const cols = ["ecc", "layer", "lam", "n_runs", "mean_acc", "mean_diff", "min_margin", "decoded_errors_total"];
    const nice = { ecc: "ECC", layer: "Layer", lam: "λ", n_runs: "Runs", mean_acc: "Accuracy", mean_diff: "Cost (pts)", min_margin: "Min margin", decoded_errors_total: "Decoded errors" };
    const fmt = (k, v) => k === "mean_acc" ? pct(v) : k === "mean_diff" ? fix(100 * v) : k === "min_margin" ? fix(v, 2) : String(v);
    body.replaceChildren(runBtns,
      p7.configs.length ? h("div", { class: "tbl-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, cols.map((c) => h("th", { class: ["ecc", "layer"].includes(c) ? "" : "num", text: nice[c] })))),
        h("tbody", {}, p7.configs.map((r) => h("tr", {}, cols.map((c) => h("td", { class: ["ecc", "layer"].includes(c) ? "mono" : "num", text: fmt(c, r[c]) }))))))) : null,
      p7.plots.length ? h("div", { class: "plots" }, p7.plots.map((p) => h("figure", {}, h("img", { src: "/api/file?path=" + encodeURIComponent(p), alt: p, loading: "lazy" }), h("figcaption", { text: p.split("/").pop() })))) : null);
  }

  // ================================================================== register
  const toLab = (k) => () => { location.replace("#labs/" + k); };
  Object.assign(ROUTES, { overview: renderHome, labs: renderLabs,
                          results: toLab("results"), verify: toLab("verify"), xray: toLab("xray"), attack: toLab("attack"), tamper: toLab("tamper"),
                          sign: toLab("sign"), hash: toLab("hash"), inspect: toLab("inspect") });
})();

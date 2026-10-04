// Evals view, shared by the product UI and the static Space. The product UI reads the separate eval server
// (evals/server.py), never the product API (decision log I3); the Space page sets window.EVALS_SOURCE to its
// exported files (evals/export_space.py). The page owns its tabs and calls Evals.show().
(() => {
  const $ = (id) => document.getElementById(id);
  const SRC = window.EVALS_SOURCE || { base: `${location.protocol}//${location.hostname}:8001`, suffix: "" };
  // Sequential blue, light to dark. Step 450 is skipped: neither ink nor white text reaches 4.5:1 on it.
  const RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"];
  const INK_STEPS = 7; // the first 7 steps take dark text, the rest white
  const LABEL = { pass: "pass", rescued: "rescued", silent_wrong: "silent wrong", unscored: "unscored" };
  const MAX_ROWS = 200;
  const body = $("ev_body"), runSel = $("ev_run"), tip = $("tip");
  let run = null, pool = "heldout", loaded = false, selected = null;

  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  // Tiles keep one decimal under 10% (3.2% of discards, not 3%); heatmap cells stay whole percents.
  const pct = (n, d, fine) => { if (!d) return "—"; const x = (100 * n) / d; return fine && x > 0 && x < 10 ? `${x.toFixed(1)}%` : `${Math.round(x)}%`; };
  const fmt = (v) => (v == null ? "—" : Object.entries(v).map(([k, x]) => `${k}=${Array.isArray(x) ? x.join(",") : x}`).join(" "));

  window.Evals = { show() { if (!loaded) load(); } };
  for (const b of document.querySelectorAll("#ev_pool button")) {
    b.addEventListener("click", () => {
      pool = b.dataset.pool;
      for (const x of document.querySelectorAll("#ev_pool button")) x.classList.toggle("on", x === b);
      selected = null;
      render();
    });
  }
  runSel.addEventListener("change", () => loadRun(runSel.value));

  async function getJSON(path) {
    const r = await fetch(SRC.base + path + SRC.suffix);
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  }

  function down(e) {
    if (window.EVALS_SOURCE) { body.replaceChildren(el("p", "empty", `Could not load the exported eval data (${e.message}).`)); return; }
    body.replaceChildren(el("p", "empty", `Eval server not reachable at ${SRC.base} (${e.message}).`),
      el("p", "note", "Start it from the repo root: uv run uvicorn evals.server:app --port 8001, then switch tabs again."));
  }

  async function load() {
    try {
      const runs = await getJSON("/evals/runs");
      loaded = true;
      runSel.replaceChildren(...runs.map((r) => new Option(`${r.prompt_version} · ${r.model_id} · set ${r.eval_set_version}`, r.run_id)));
      if (!runs.length) { body.replaceChildren(el("p", "empty", "No results files in evals/results/.")); return; }
      await loadRun(runs[0].run_id);
    } catch (e) { down(e); }
  }

  async function loadRun(id) {
    try {
      run = await getJSON("/evals/runs/" + encodeURIComponent(id));
      $("ev_meta").textContent = `${run.run_id} · validators ${(run.validator_versions || []).join(", ")}`;
      selected = null;
      render();
    } catch (e) { down(e); }
  }

  // --- rendering -------------------------------------------------------------
  function tile(k, v, s) {
    const t = el("div", "tile");
    t.append(el("div", "k", k), el("div", "v", v), el("div", "s", s));
    return t;
  }

  function render() {
    const v = run.pools[pool];
    const parts = [];
    if (pool === "dev") parts.push(el("div", "devnote", "Dev pool: for diagnosis only. Reported numbers come from held-out."));
    const tiles = el("div", "tiles");
    const j = run.judge;
    tiles.append(
      tile("Sessions passed", `${v.sessions.passed} / ${v.sessions.n}`, `${pct(v.sessions.passed, v.sessions.n)} · booking matched the card`),
      tile("Discarded by fidelity gate", `${v.discard.discarded} / ${v.discard.runs}`, `${pct(v.discard.discarded, v.discard.runs, true)} of generated runs · regenerated`),
      tile("Judge agreement", j.matched ? `${j.agree} / ${j.matched}` : "—", j.matched ? `${pct(j.agree, j.matched)} with human labels (dev) · floor ${Math.round(100 * j.floor)}%` : "no judge data"),
      tile("Replies judged not fitting", `${v.coherence.fits_no} / ${v.coherence.replies}`, `${pct(v.coherence.fits_no, v.coherence.replies)} of bot replies · ${j.model || "no judge"}`),
    );
    parts.push(tiles);
    parts.push(heatmap(v));
    const drill = el("div", "panel");
    drill.id = "ev_drill";
    drill.append(el("p", "empty", "Click a cell to list the calls in it."));
    parts.push(drill);
    body.replaceChildren(...parts);
  }

  function heatmap(v) {
    const p = el("div", "panel");
    p.append(el("h2", "", "Where calls land: prompt × outcome"),
      el("div", "note", "Each cell is the share of that prompt's calls with that outcome. Hover for counts, click to list the calls."));
    const t = el("table", "heat");
    const hr = el("tr");
    hr.append(el("th", "", ""), el("th", "", "calls"), ...run.outcomes.map((o) => el("th", "", LABEL[o])));
    const th0 = el("thead"); th0.append(hr); t.append(th0);
    const tb = el("tbody");
    for (const row of v.heatmap) {
      const tr = el("tr");
      const th = el("th", "p", row.prompt);
      th.append(el("small", "", row.kind));
      const n = el("td", "n", String(row.calls));
      tr.append(th, n);
      for (const o of run.outcomes) tr.append(cell(row, o));
      tb.append(tr);
    }
    t.append(tb);
    const ramp = el("div", "ramp");
    const z = el("span", "sw"); z.style.boxShadow = "inset 0 0 0 1px var(--line)";
    ramp.append(z, el("span", "", "none ·"), el("span", "", "1%"));
    for (const c of RAMP) { const s = el("span", "sw"); s.style.background = c; ramp.append(s); }
    ramp.append(el("span", "", "100% of the prompt's calls"));
    p.append(t, ramp);
    return p;
  }

  function cell(row, o) {
    const n = row.counts[o];
    const td = el("td", "cell");
    if (!row.calls) { td.classList.add("none"); td.textContent = "—"; return td; }
    if (!n) { td.classList.add("zero"); td.textContent = "0"; return td; }
    const r = n / row.calls;
    const step = Math.min(RAMP.length - 1, Math.floor(r * RAMP.length));
    td.style.background = RAMP[step];
    td.style.color = step < INK_STEPS ? "#1c2024" : "#fff";
    td.textContent = pct(n, row.calls);
    td.tabIndex = 0;
    const show = (x, y) => {
      tip.replaceChildren(el("b", "", `${n} of ${row.calls} calls (${pct(n, row.calls)})`), el("span", "", `${row.prompt} · ${LABEL[o]}`));
      tip.hidden = false;
      tip.style.left = `${Math.min(x + 12, innerWidth - 300)}px`;
      tip.style.top = `${y + 12}px`;
    };
    td.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    td.addEventListener("focus", () => { const b = td.getBoundingClientRect(); show(b.left, b.bottom); });
    for (const ev of ["pointerleave", "blur"]) td.addEventListener(ev, () => { tip.hidden = true; });
    const open = () => { if (selected) selected.classList.remove("sel"); selected = td; td.classList.add("sel"); drill(row.prompt, o); };
    td.addEventListener("click", open);
    td.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    return td;
  }

  function drill(prompt, outcome) {
    const v = run.pools[pool];
    const calls = v.calls.filter((c) => c.prompt === prompt && c.outcome === outcome);
    const p = $("ev_drill");
    p.replaceChildren(el("h2", "", `${prompt} · ${LABEL[outcome]} · ${calls.length} calls`));
    p.append(el("div", "note", pool === "heldout"
      ? "Held-out: structured fields only. Patient and bot text are never sent for held-out (decision log I1)."
      : "Dev: click a row for the patient message, the bot reply and the product's log lines for that turn."));
    const t = el("table");
    const hr = el("tr");
    hr.append(...["card", "turn", "state", "expected", "actual", "validator"].map((h) => el("th", "", h)));
    const th0 = el("thead"); th0.append(hr); t.append(th0);
    const tb = el("tbody");
    for (const c of calls.slice(0, MAX_ROWS)) {
      const tr = el("tr");
      const vtag = el("span", "tag " + (c.ok ? "ok" : "bad"), c.ok ? "ok" : c.reason_code);
      const vtd = el("td"); vtd.append(vtag);
      tr.append(el("td", "mono", c.card_id), el("td", "", String(c.turn)), el("td", "mono", c.state), el("td", "mono", fmt(c.gold)), el("td", "mono", fmt(c.actual)), vtd);
      tb.append(tr);
      if (pool === "dev") { tr.style.cursor = "pointer"; tr.addEventListener("click", () => toggleTurn(tr, c)); }
    }
    t.append(tb);
    p.append(t);
    if (calls.length > MAX_ROWS) p.append(el("p", "note", `Showing the first ${MAX_ROWS} of ${calls.length}.`));
  }

  function toggleTurn(tr, c) {
    if (tr.nextSibling && tr.nextSibling.classList.contains("detail")) { tr.nextSibling.remove(); tr.classList.remove("open"); return; }
    const turn = (run.pools.dev.turns[c.card_id] || {})[c.turn];
    const d = el("tr", "detail open");
    const td = el("td");
    td.colSpan = 6;
    if (!turn) { td.append(el("span", "empty", "no transcript turn found")); }
    else {
      td.append(el("div", "", `patient: ${turn.user}`), el("div", "", `bot: ${turn.reply}`));
      const lt = el("table");
      const h = el("tr"); h.append(...["state", "call", "validator", "ms", "raw output"].map((x) => el("th", "", x)));
      const lh = el("thead"); lh.append(h); lt.append(lh);
      const lb = el("tbody");
      for (const l of turn.log) {
        const r = el("tr");
        r.append(el("td", "mono", l.state), el("td", "mono", l.prompt_name), el("td", "", l.ok ? "ok" : l.reason_code), el("td", "", String(l.latency_ms ?? "")), el("td", "mono", l.raw_output || ""));
        lb.append(r);
      }
      lt.append(lb);
      td.append(lt);
    }
    d.append(td);
    tr.classList.add("open");
    tr.after(d);
  }
})();

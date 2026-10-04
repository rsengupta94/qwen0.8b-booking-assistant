// Conversation replay for the static Space: the recorded dev conversations with the same per-turn debug panel
// as the local UI (clients/ui/index.html). Reads data/conversations.json written by evals/export_space.py.
(() => {
  const $ = (id) => document.getElementById(id);
  const list = $("convlist"), replay = $("replay"), debug = $("replaydebug");
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const PERSONA = { prof: "proficient", noprof: "not proficient", patient: "patient", agitated: "agitated", inattentive: "inattentive", someidea: "some idea", noidea: "no idea" };
  const ENDED = { booking_confirmed: "booked", handoff: "hand-off", gave_up: "gave up", turn_cap: "turn cap" };
  let current = null;

  const persona = (id) => id.split("_").map((p) => PERSONA[p] || p).join(" · ");
  const outcome = (s) => (s.pass ? "pass" : `fail${s.reason && s.reason !== "ok" ? ": " + s.reason.replaceAll("_", " ") : ""}`);

  function show(c, button) {
    if (current) current.classList.remove("on");
    current = button; button.classList.add("on");
    replay.replaceChildren();
    debug.replaceChildren(el("h2", "", "Debug"));
    for (const t of c.turns) {
      replay.append(el("div", "msg you", t.user));
      replay.append(el("div", "msg bot" + (t.fallback_used ? " template" : ""), t.reply));
      const calls = t.log.map((l) => l.prompt_name + (l.ok ? "" : " FALLBACK:" + l.reason_code));
      replay.append(el("div", "state", `[${t.state}] ${t.kind || ""} | ${calls.join(", ") || "no model calls"}`));

      const card = el("div", "turn");
      const head = el("div", "head");
      head.append(el("b", "", `turn ${t.turn}`), el("span", "", `you: ${t.user}`), el("span", "tag", t.state), el("span", "tag", t.kind || ""),
        el("span", "tag " + (t.fallback_used ? "bad" : "ok"), t.fallback_used ? "fallback used" : "all ok"));
      card.append(head);
      if (t.log.length) {
        const table = el("table");
        const hr = el("tr");
        hr.append(...["call", "validator", "ms", "raw output"].map((h) => el("th", "", h)));
        const thead = el("thead"); thead.append(hr); table.append(thead);
        const tb = el("tbody");
        for (const l of t.log) {
          const tr = el("tr");
          const v = el("td"); v.append(el("span", "tag " + (l.ok ? "ok" : "bad"), l.ok ? "ok" : l.reason_code));
          tr.append(el("td", "mono", l.prompt_name), v, el("td", "", String(l.latency_ms ?? "")), el("td", "mono", l.raw_output || ""));
          tb.append(tr);
        }
        table.append(tb);
        card.append(table);
      } else {
        card.append(el("div", "empty", "no model calls this turn"));
      }
      debug.append(card);
    }
    const s = c.session || {};
    replay.append(el("div", "state", `session ended: ${ENDED[s.ended] || s.ended || "?"} · ${outcome(s)}`));
  }

  fetch("data/conversations.json")
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((convs) => {
      for (const c of convs) {
        const b = el("button", "conv");
        b.type = "button";
        const s = c.session || {};
        b.append(el("b", "", `${c.scenario_id} · ${c.scenario_title}`), el("span", "", `${persona(c.persona_id)} · ${ENDED[s.ended] || s.ended || "?"} · ${outcome(s)}`));
        b.addEventListener("click", () => show(c, b));
        list.append(b);
      }
    })
    .catch((e) => { replay.replaceChildren(el("p", "empty", `Could not load the conversations (${e.message}).`)); });
})();

// Plexus UI. Vanilla JS: sections, polling, the shell dock, demo hooks.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
  return r.json();
};

const loaded = {};
// In a recording the verdict chip would show whatever the previous take
// left behind, so it stays hidden until this page has seen a run finish.
const demoMode = new URLSearchParams(location.search).has("demo");
let demoRunDone = false;
document.addEventListener("plexus:run-finished", () => (demoRunDone = true));
let lastExecution = null;

// ---------------------------------------------------------------- sections
function goto(sec) {
  $$(".rail a").forEach((a) => a.classList.toggle("on", a.dataset.sec === sec));
  $$(".sec").forEach((s) => s.classList.toggle("on", s.id === `sec-${sec}`));
  $("#main").scrollTop = 0;
  const load = { stack: loadStack, policy: loadPolicy, harness: loadHarness, run: loadRun, trajectory: loadTrajectory, tuner: loadTuner }[sec];
  history.replaceState(null, "", `${location.pathname}${location.search}#${sec}`);
  return load ? load() : Promise.resolve();
}
$$(".rail a").forEach((a) => a.addEventListener("click", () => goto(a.dataset.sec)));

// ---------------------------------------------------------------- header
async function refreshHeader(st) {
  st = st || (await api("/ui/state"));
  const llm = st.llm || {};
  $("#chip-model").textContent = `model ${llm.model || "?"}`;
  $("#chip-ext").textContent = `pg_synapse ${st.extensions.pg_synapse_pgrx || "?"} · vector ${st.extensions.vector || "?"}`;
  const ok = st.conditions.filter((c) => c.ok).length;
  const v = $("#chip-verdict");
  v.textContent = `${ok}/${st.conditions.length} conditions · ${st.passed ? "PASS" : "FAIL"}`;
  v.className = `chip verdict ${st.passed ? "pass" : "fail"}${demoMode && !demoRunDone ? " hidden" : ""}`;
  return st;
}

// ---------------------------------------------------------------- 1 stack
async function loadStack() {
  const st = await refreshHeader();
  const llm = st.llm || {};
  $("#llm-detail").innerHTML = `<code>${esc(llm.model)}</code><br>${esc(llm.base_url)}<br>OpenAI-compatible, outside the database. Swap it with one <code>llm_profile_set</code>.`;
}

// ---------------------------------------------------------------- 2 policy
async function loadPolicy() {
  const st = await api("/ui/state");
  const day = (d) => new Date(d + "T00:00:00Z").getTime();
  const lo = day("2026-05-01"), hi = day("2026-08-15");
  const x = (d) => 3 + ((day(d) - lo) / (hi - lo)) * 94;
  const cut = x("2026-07-01");
  let h = `<div class="tl-axis"></div>`;
  h += `<div class="tl-zone v1" style="left:3%">refund-v1: 14-day window</div>`;
  h += `<div class="tl-zone v2" style="left:${cut + 1}%">refund-v2: 30-day window</div>`;
  h += `<div class="tl-cut" style="left:${cut}%"><span>1 July: v2 supersedes v1</span></div>`;
  // tickets a few days apart share one marker so their labels stay readable
  const groups = [];
  for (const t of st.tickets.slice().sort((a, b) => a.created.localeCompare(b.created))) {
    const g = groups[groups.length - 1];
    if (g && day(t.created) - day(g[g.length - 1].created) <= 5 * 864e5 && !t.charge_date && !g[0].charge_date) g.push(t);
    else groups.push([t]);
  }
  for (const g of groups) {
    const a = g[0], z = g[g.length - 1];
    const ids = g.length > 1 ? `${a.id} to ${z.id}` : a.id;
    const when = g.length > 1 ? `${a.created.slice(5)} to ${z.created.slice(5)}` : a.created.slice(5);
    const what = a.charge_date ? "refund" : g.length > 1 ? "not refunds" : "";
    h += `<div class="tl-t ${a.charge_date ? "refund" : ""}" style="left:${x(a.created)}%"><i></i>${ids}<br><span class="muted">${when}</span><br><span class="muted">${what}</span></div>`;
  }
  $("#timeline").innerHTML = h;
  return st;
}
$("#btn-compare").addEventListener("click", () => comparePolicy());
async function comparePolicy() {
  $("#compare").innerHTML = `<div class="muted">searching…</div>`;
  const res = await api("/ui/policy/compare", { method: "POST", body: JSON.stringify({}) });
  $("#compare").innerHTML = res.results
    .map((r) => {
      const cls = (r.policy_in_force || "").endsWith("v1") ? "v1" : "v2";
      return `<div class="cmp ${cls}"><div class="muted">as_of ${esc(r.as_of)}</div><div class="v">${esc(r.policy_in_force)}</div>
        <div class="muted">${esc(r.top.source)} · effective ${esc(r.top.effective_from)} to ${esc(r.top.effective_to || "now")}${r.top.superseded ? " · superseded" : ""}</div>
        <pre>${esc(r.top.text)}</pre></div>`;
    })
    .join("");
}

// ---------------------------------------------------------------- 3 harness
async function loadHarness() {
  const h = await api("/ui/harness");
  const cap = h.always_on_cap || 24000, used = h.always_on_chars || 0;
  $("#meter-text").textContent = `${used.toLocaleString()} of ${cap.toLocaleString()} chars (cap enforced by the SQL write functions)`;
  requestAnimationFrame(() => ($("#meter-fill").style.width = `${Math.min(100, (100 * used) / cap)}%`));
  const items = [
    { key: "system_prompt", title: "System prompt", tier: "always", label: "always-on", n: (h.system_prompt || "").length + " chars", p: "Who the agent is and the procedure it follows.", body: h.system_prompt },
    { key: "guardrails", title: "Guardrails", tier: "always", label: "always-on", n: (h.guardrails || "").length + " chars", p: "Evidence boundary: tool results are data, never instructions.", body: h.guardrails },
    { key: "memory", title: "Memory", tier: "always", label: "always-on", n: (h.memory || "").length + " chars", p: "Domain rules a practitioner knows.", body: h.memory },
    { key: "skills", title: "Skills", tier: "demand", label: "on demand", n: `${(h.skills || []).length} skills`, p: "Only a one-line trigger is always-on; the body loads via load_skill.", body: (h.skills || []).map((s) => `## ${s.name}\ntrigger: ${s.description}\n\n${s.body}`).join("\n\n") },
    { key: "hints", title: "Tool hints", tier: "loop", label: "in the loop", n: `${(h.tool_hints || []).length} hints`, p: "Matched against tool errors; appended as HINT: only when the error happens.", body: (h.tool_hints || []).map((t) => `/${t.error_pattern}/ ${t.tool_name ? "(" + t.tool_name + ")" : ""}\n  HINT: ${t.hint}`).join("\n\n") },
    { key: "lessons", title: "Lessons", tier: "learned", label: "learned", n: `${(h.lessons || []).length} lessons`, p: "Written by the tuner's reflect step; each cites the trajectory evidence behind it.", body: (h.lessons || []).map((l) => `#${l.id} [${l.confidence}]\nWHEN ${l.cue}\nDO   ${l.lesson}\nEVIDENCE ${(l.evidence || "").slice(0, 240)}${(l.evidence || "").length > 240 ? "…" : ""}${l.source_execution ? `\nfrom execution ${l.source_execution}` : ""}`).join("\n\n") },
  ];
  $("#hgrid").innerHTML = items
    .map((it) => `<div class="hc" data-k="${it.key}" id="hc-${it.key}"><span class="tier ${it.tier}">${it.label}</span><h3>${it.title}</h3><div class="n">${esc(it.n)}</div><p>${esc(it.p)}</p></div>`)
    .join("");
  $$(".hc").forEach((el) =>
    el.addEventListener("click", () => {
      $$(".hc").forEach((x) => x.classList.toggle("on", x === el));
      $("#hbody").textContent = items.find((i) => i.key === el.dataset.k).body || "(empty)";
    })
  );
  $("#hbody").textContent = "";
}
function openComponent(key) {
  const el = $(`#hc-${key}`);
  if (el) el.click();
}

// ---------------------------------------------------------------- 4 run
function cell(v, cls = "") {
  return v === null || v === undefined ? `<td class="null">null</td>` : `<td class="${cls}">${v}</td>`;
}
function renderTickets(st, fresh = false) {
  let h = `<tr><th>id</th><th>tier</th><th>created</th><th>charge</th><th>subject</th><th>category</th><th>priority</th><th>esc</th><th>refund</th><th>policy</th><th>audit</th></tr>`;
  for (const t of st.tickets) {
    const pv = t.policy_version ? `<span class="pill ${t.policy_version.endsWith("v1") ? "v1" : "v2"}">${esc(t.policy_version)}</span>` : null;
    const esc_ = t.escalated === null ? null : t.escalated ? `<span class="pill esc">yes</span>` : "no";
    h += `<tr class="${fresh && t.category ? "fresh" : ""}"><td>${t.id}</td><td>${esc(t.tier)}</td><td>${esc(t.created.slice(5))}</td>${cell(t.charge_date && esc(t.charge_date.slice(5)))}<td class="subj">${esc(t.subject)}</td>${cell(t.category && esc(t.category))}${cell(t.priority && esc(t.priority))}${cell(esc_)}${cell(t.refund_decision && esc(t.refund_decision))}${cell(pv)}${cell(t.audit_rows || (t.category ? 0 : null))}</tr>`;
  }
  $("#tickets").innerHTML = h;
  $("#conds").innerHTML = st.conditions.map((c) => `<li class="${c.ok ? "ok" : "no"}"><span>${esc(c.name)}</span><b>${c.ok ? "PASS" : "FAIL"}</b></li>`).join("");
}
let pollTimer = null;
async function loadRun() {
  const st = await refreshHeader();
  renderTickets(st);
  const r = await api("/ui/run");
  renderRun(r);
  if (r.status === "running") startPolling();
}
function renderRun(r) {
  const s = $("#runstat");
  s.className = `runstat ${r.status}`;
  s.textContent = r.status === "running" ? `running… ${r.elapsed_s}s` : r.status === "done" ? `done in ${r.elapsed_s}s` : r.status === "failed" ? `failed: ${r.error}` : "idle";
  $("#btn-run").disabled = $("#btn-reset").disabled = r.status === "running";
  const feed = r.feed || [];
  $("#feed").innerHTML = feed.length
    ? feed.map((f) => `<li>http_post /policy/search as_of <b>${esc(f.as_of)}</b> → <span class="pill ${(f.policy_in_force || "").endsWith("v1") ? "v1" : "v2"}">${esc(f.policy_in_force)}</span></li>`).join("")
    : `<li class="muted">no calls yet</li>`;
  $("#feed").scrollTop = 1e9;
  const o = r.outcome;
  if (o) {
    lastExecution = o.execution_id;
    $("#outcome").textContent = `status ${o.status} · ${o.iterations} iterations · ${o.tool_calls} tool calls\ntokens ${o.tokens_in?.toLocaleString()} in / ${o.tokens_out?.toLocaleString()} out · ${(o.duration_ms / 1000).toFixed(1)} s\nexecution ${o.execution_id}`;
  } else {
    $("#outcome").textContent = r.status === "running" ? "" : $("#outcome").textContent;
  }
  if (r.last_execution) lastExecution = lastExecution || r.last_execution;
}
function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const r = await api("/ui/run");
    renderRun(r);
    if (r.status !== "running") {
      clearInterval(pollTimer);
      demoRunDone = true;
      const st = await refreshHeader();
      renderTickets(st, true);
      document.dispatchEvent(new CustomEvent("plexus:run-finished", { detail: r }));
    }
  }, 700);
}
async function resetTickets() {
  await api("/ui/reset", { method: "POST" });
  lastExecution = null;
  await loadRun();
}
async function runAgent() {
  $("#outcome").textContent = "";
  await api("/ui/run", { method: "POST" });
  const r = await api("/ui/run");
  renderRun(r);
  startPolling();
}
$("#btn-reset").addEventListener("click", resetTickets);
$("#btn-run").addEventListener("click", runAgent);

// ---------------------------------------------------------------- 5 trajectory
async function loadTrajectory() {
  if (!lastExecution) {
    const r = await api("/ui/run");
    lastExecution = r.outcome?.execution_id || r.last_execution;
  }
  if (!lastExecution) {
    $("#traj").innerHTML = `<li>no run yet</li>`;
    return;
  }
  $("#traj-id").textContent = `execution ${lastExecution}`;
  const t = await api(`/ui/trajectory/${lastExecution}`);
  renderTrajectory(t.steps);
}
function renderTrajectory(steps) {
  const only = $("#only-actions").checked;
  const keep = only ? steps.filter((s) => ["action", "error", "assistant"].includes(s.kind) || s.hint) : steps.filter((s) => !["system", "user"].includes(s.kind));
  $("#traj").innerHTML = keep
    .map((s, i) => {
      const head = s.kind === "action" ? s.head.replace(/^(\S+)\s/, "<b>$1</b> ") : esc(s.head);
      const body = !only && s.body ? `<div class="b">${esc(s.body.slice(0, 600))}</div>` : s.kind === "error" && s.body ? `<div class="b">${esc(s.body.slice(0, 300))}</div>` : s.kind === "assistant" && s.body ? `<div class="b">${esc(s.body.slice(0, 400))}</div>` : "";
      return `<li class="${s.kind}" id="ts-${i}"><span class="k">${s.kind}</span><span class="h">${s.kind === "action" ? head : esc(s.head)}</span>${body}${s.hint ? `<div class="hint">HINT: ${esc(s.hint)}</div>` : ""}</li>`;
    })
    .join("");
  window.__trajSteps = steps;
}
$("#only-actions").addEventListener("change", () => window.__trajSteps && renderTrajectory(window.__trajSteps));

// ---------------------------------------------------------------- 6 tuner
async function loadTuner() {
  const t = await api("/ui/tune");
  const base = t.rollouts.filter((r) => r.stage === "base");
  const baseAvg = base.reduce((a, r) => a + r.tokens_in, 0) / base.length;
  const adopted = t.rollouts.find((r) => r.label === t.adopted);
  const cut = adopted ? Math.round(100 * (1 - adopted.tokens_in / baseAvg)) : 0;
  $("#tune-lede").innerHTML = `harness2's outer loop, run by <code>bench/tune.py</code> on <code>${esc(t.model)}</code> with k=${t.k}: roll the base harness, let an improver <b>propose</b> edits on two axes (INV: how the agent works, DOM: what a practitioner knows), <b>probe</b> each once, <b>compose</b> finals, select, then <b>reflect</b> into a lesson. Adopted <code>${esc(t.adopted)}</code>: ${cut}% fewer input tokens than the base average.`;
  const max = Math.max(...t.rollouts.map((r) => r.tokens_in));
  $("#chart").innerHTML =
    `<h4 style="margin-top:0">input tokens per rollout (every one passed 5/5)</h4>` +
    t.rollouts
      .map((r) => `<div class="bar ${r.label === t.adopted ? "adopted" : ""}" id="bar-${r.label}"><span>${esc(r.label)}</span><div class="track"><div class="fill ${r.stage}" data-w="${(100 * r.tokens_in) / max}"></div></div><span class="lab">${(r.tokens_in / 1000).toFixed(0)}k ${r.passed ? "✓" : "✗"} ${r.label === t.adopted ? "adopted" : ""}</span></div>`)
      .join("") +
    `<div class="legend">grey = base · blue = INV proposals · purple = DOM proposals · green = composed finals</div>`;
  requestAnimationFrame(() => $$(".fill").forEach((f) => (f.style.width = f.dataset.w + "%")));
  $("#lesson").innerHTML = `<h3>Lesson ${esc(t.lesson_id)} <span class="muted">(${esc(t.lesson.confidence)})</span></h3><div class="cue"><b>When</b> ${esc(t.lesson.cue)}</div><div class="txt"><b>Do</b> ${esc(t.lesson.lesson)}</div>`;
  const d = t.diffs.find((x) => x.file === "system_prompt.md") || t.diffs[0];
  $("#diff").innerHTML = d
    ? d.diff
        .split("\n")
        .map((l) => (l.startsWith("+") && !l.startsWith("+++") ? `<span class="add">${esc(l)}</span>` : l.startsWith("-") && !l.startsWith("---") ? `<span class="del">${esc(l)}</span>` : l.startsWith("@@") ? `<span class="hdr">${esc(l)}</span>` : esc(l) + "\n"))
        .join("")
    : "(no changes)";
}

// ---------------------------------------------------------------- shell dock
let term, fit, ws;
function sendToShell(cmd, enter = true) {
  if (!ws || ws.readyState !== 1) return false;
  ws.send(JSON.stringify({ type: "input", data: cmd + (enter ? "\r" : "") }));
  term.focus();
  return true;
}
async function typeInShell(cmd, cps = 28) {
  for (const ch of cmd) {
    sendToShell(ch, false);
    await new Promise((r) => setTimeout(r, 1000 / cps));
  }
  sendToShell("", true);
}
async function startShell() {
  term = new Terminal({ fontFamily: '"JetBrains Mono", ui-monospace, Menlo, monospace', fontSize: 13.5, lineHeight: 1.2, cursorBlink: true, convertEol: false, theme: { background: "#0a0e14", foreground: "#d6dee7" }, scrollback: 5000 });
  fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open($("#term"));
  fit.fit();
  const tok = await api("/ui/shell-token");
  if (!tok.enabled) {
    $("#shell-state").textContent = "disabled (start the API with PLEXUS_SHELL=1)";
    term.write("Shell is off. Start the API with PLEXUS_SHELL=1 to enable it.\r\n");
    return;
  }
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ui/shell?token=${encodeURIComponent(tok.token)}`);
  ws.onopen = () => {
    $("#shell-state").textContent = "connected";
    ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
  };
  ws.onmessage = (e) => term.write(e.data);
  ws.onclose = () => ($("#shell-state").textContent = "disconnected");
  term.onData((d) => ws.readyState === 1 && ws.send(JSON.stringify({ type: "input", data: d })));
  window.addEventListener("resize", () => {
    fit.fit();
    ws.readyState === 1 && ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
  });
}
$$("#quick button").forEach((b) => b.addEventListener("click", () => typeInShell(b.dataset.cmd, 60)));

// ---------------------------------------------------------------- demo hooks
function spotlight(selector, caption, pad = 8) {
  const el = typeof selector === "string" ? $(selector) : selector;
  if (!el) return false;
  el.scrollIntoView({ block: "nearest", behavior: "instant" });
  const r = el.getBoundingClientRect();
  const s = $("#spot");
  Object.assign(s.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + 2 * pad}px`, height: `${r.height + 2 * pad}px` });
  s.classList.remove("hidden");
  const c = $("#spot-cap");
  if (caption) {
    c.textContent = caption;
    c.classList.remove("hidden");
    const below = r.bottom + pad + 14;
    const top = below + 60 < innerHeight ? below : Math.max(10, r.top - pad - 64);
    Object.assign(c.style, { left: `${Math.min(Math.max(10, r.left), innerWidth - 540)}px`, top: `${top}px` });
  } else c.classList.add("hidden");
  return true;
}
function clearSpot() {
  $("#spot").classList.add("hidden");
  $("#spot-cap").classList.add("hidden");
}
function caption(text) {
  const c = $("#caption");
  if (!text) return c.classList.add("hidden");
  c.textContent = text;
  c.classList.remove("hidden");
}
function waitRun() {
  return new Promise((res) => document.addEventListener("plexus:run-finished", (e) => res(e.detail), { once: true }));
}
window.plexusDemo = { goto, spotlight, clearSpot, caption, comparePolicy, openComponent, resetTickets, runAgent, waitRun, typeInShell, sendToShell, scrollTraj: (i) => $(`#ts-${i}`)?.scrollIntoView({ block: "center", behavior: "smooth" }) };

// ---------------------------------------------------------------- boot
startShell();
refreshHeader();
goto((location.hash || "#stack").slice(1).split("?")[0] || "stack");

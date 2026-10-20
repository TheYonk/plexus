// Plexus executive cut. Slides 3 to 5 read live data from /exec/*;
// window.execDemo is what demo/record.py drives.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = async (path, opts) => {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
  return r.json();
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fmt$ = (n) => (n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n)}`);

const slides = $$(".slide");
let current = 1;

function goto(n) {
  current = Math.max(1, Math.min(slides.length, n));
  slides.forEach((s) => s.classList.toggle("on", +s.dataset.n === current));
  $$("#dots a").forEach((a) => a.classList.toggle("on", +a.dataset.n === current));
  clearSpot();
  history.replaceState(null, "", `${location.search}#${current}`);
}
$("#dots").innerHTML = slides.map((s) => `<a data-n="${s.dataset.n}">${s.dataset.n}</a>`).join("");
$("#dots").addEventListener("click", (e) => e.target.dataset.n && goto(+e.target.dataset.n));
addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "ArrowRight" || e.key === " ") goto(current + 1);
  if (e.key === "ArrowLeft") goto(current - 1);
});

// --- proof 1: the veto -------------------------------------------------------
const VETO = [
  { id: 104, amount: 49, why: "charged 1 June, ticket 1 August: 61 days. The policy in force that day allows 30." },
  { id: 103, amount: 29, why: "charged 28 June, ticket 20 July: 22 days. Inside the 30-day window." },
];
function drawVeto(state = {}) {
  VETO.forEach((c, i) => {
    const r = state.cases?.[i];
    const el = $(`#vcase-${i}`);
    el.className = "vcase" + (state.pending ? " pending" : r ? (r.landed ? " landed" : " rejected") : "");
    el.innerHTML = `<div class="t">Refund $${c.amount} on ticket ${c.id}</div><div class="w">${c.why}</div>
      <div class="sql">INSERT INTO support.refunds (ticket_id, amount_usd, note)<br>VALUES (${c.id}, ${c.amount}.00, 'customer changed their mind')</div>
      <div class="res">${state.pending ? "agent checking the policy…" : r ? (r.landed ? "✓ COMMITTED" : "✕ REJECTED, ROLLED BACK") : ""}</div>
      ${r && !r.landed ? `<div class="err">ERROR: ${esc(r.error)}</div>` : ""}`;
  });
  $("#vafter").textContent = state.rows ? `support.refunds now holds ${state.rows.length} row${state.rows.length === 1 ? "" : "s"}: ${state.rows.map((r) => `ticket ${r.ticket_id}, $${r.amount_usd}`).join("; ") || "none"}` : "";
}
let vetoDone = null;
async function runVeto() {
  $("#btn-veto").disabled = true;
  drawVeto({ pending: true });
  try {
    vetoDone = await api("/exec/veto", { method: "POST" });
    drawVeto(vetoDone);
  } catch (e) {
    vetoDone = { error: String(e) };
    $("#vafter").textContent = String(e);
  }
  $("#btn-veto").disabled = false;
  return vetoDone;
}
$("#btn-veto").addEventListener("click", runVeto);

// --- proof 2: the auditor's question -----------------------------------------
async function loadAudit(id = 104) {
  const t = await api(`/exec/audit/${id}`);
  $("#aud-id").textContent = t.id;
  const decided = t.refund_decision ? `<span class="pill ${t.refund_decision === "approve" ? "yes" : t.refund_decision === "deny" ? "esc" : "v1"}">${esc(t.refund_decision)}</span> under <span class="pill ${esc(t.policy_version || "").includes("v1") ? "v1" : "v2"}">${esc(t.policy_version)}</span>` : `<span class="muted">not decided yet</span>`;
  const items = [
    ["The ticket", `${esc(t.subject)}`, `${esc(t.tier)} tier · charged ${esc(t.charge_date)} · opened ${esc(t.created)} · ${t.days} days apart`],
    ["Policy in force that day", `<span class="pill ${String(t.policy.in_force).includes("v1") ? "v1" : "v2"}">${esc(t.policy.in_force)}</span> as of ${esc(t.policy.as_of)}`, esc(t.policy.text.split(/\n(?=\d\. )/).slice(0, 3).map((c) => c.replace(/\s+/g, " ").trim()).join("\n"))],
    ["The agent looked it up", t.step ? `step ${t.step.n} of the run's trajectory` : `<span class="muted">no lookup in the latest run</span>`, t.step ? esc(t.step.action.slice(0, 300)) : ""],
    ["What it decided", decided, ""],
    ["The audit line it wrote", esc(t.audit[0] || "none"), t.execution_id ? `execution ${esc(t.execution_id)}` : ""],
  ];
  $("#chain").innerHTML = items.map(([k, v, m], i) => `<li id="ch-${i}" style="animation-delay:${i * 0.12}s"><b>${k}</b><div><div class="v">${v}</div>${m ? `<div class="m">${m}</div>` : ""}</div></li>`).join("");
  return t;
}

// --- proof 3: measured numbers -----------------------------------------------
let numbers = null;
async function loadNumbers() {
  numbers = await api("/exec/numbers");
  $("#n-base").textContent = numbers.base_per_ticket.toLocaleString();
  $("#n-after").textContent = numbers.adopted_per_ticket.toLocaleString();
  $("#n-pct").textContent = `${Math.round(numbers.saving * 100)}%`;
  const l = numbers.lesson || {};
  $("#x-lesson").innerHTML = `<h3>The lesson it wrote down for next time</h3><div class="cue">${esc(l.cue)}</div><div class="txt">${esc(l.lesson)}</div>`;
  setupMath();
  return numbers;
}

// --- the math ------------------------------------------------------------------
const INPUTS = [
  { key: "tickets", label: "Tickets per month", min: 100000, max: 5000000, step: 100000, v: 2000000, tag: "assumption", f: (v) => v.toLocaleString() },
  { key: "share", label: "Share needing a refund decision", min: 0.05, max: 0.5, step: 0.01, v: 0.2, tag: "assumption", f: (v) => `${Math.round(v * 100)}%` },
  { key: "wrong", label: "Wrong-policy rate without an as-of check", min: 0, max: 0.1, step: 0.005, v: 0.02, tag: "assumption", f: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "refund", label: "Average refund", min: 5, max: 300, step: 5, v: 45, tag: "assumption", f: (v) => `$${v}` },
  { key: "price", label: "Model price per million input tokens", min: 0.1, max: 15, step: 0.1, v: 3, tag: "assumption", f: (v) => `$${v.toFixed(2)}` },
];
const vals = {};
function setupMath() {
  if ($("#inputs").children.length) return compute();
  $("#inputs").innerHTML = INPUTS.map((i) => `<div class="slider" id="sl-${i.key}"><label>${i.label} <span class="illus">${i.tag}</span></label><output id="ov-${i.key}"></output>
    <input type="range" id="in-${i.key}" min="${i.min}" max="${i.max}" step="${i.step}" value="${i.v}"></div>`).join("") +
    `<div class="slider"><label>Input tokens saved per ticket <span class="measured">measured</span></label><output id="ov-saved"></output></div>`;
  INPUTS.forEach((i) => $(`#in-${i.key}`).addEventListener("input", compute));
  compute();
}
function compute() {
  INPUTS.forEach((i) => { vals[i.key] = +$(`#in-${i.key}`).value; $(`#ov-${i.key}`).textContent = i.f(vals[i.key]); });
  const saved = numbers ? numbers.base_per_ticket - numbers.adopted_per_ticket : 0;
  $("#ov-saved").textContent = saved.toLocaleString();
  const exposure = vals.tickets * 12 * vals.share * vals.wrong * vals.refund;
  const tokens = (vals.tickets * 12 * saved * vals.price) / 1e6;
  $("#o-exposure").textContent = fmt$(exposure);
  $("#o-tokens").textContent = fmt$(tokens);
}
function setSlider(key, value, ms = 1200) {
  const el = $(`#in-${key}`);
  const from = +el.value, t0 = performance.now();
  return new Promise((res) => {
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / ms);
      el.value = from + (value - from) * (1 - (1 - k) ** 3);
      compute();
      k < 1 ? requestAnimationFrame(tick) : res();
    };
    requestAnimationFrame(tick);
  });
}

// --- spotlight (same as the main app) -------------------------------------------
function spotlight(selector, caption, pad = 10) {
  const el = typeof selector === "string" ? $(selector) : selector;
  if (!el) return false;
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

window.execDemo = { goto, spotlight, clearSpot, runVeto, loadAudit, loadNumbers, setSlider, vetoResult: () => vetoDone };

drawVeto();
loadAudit().catch((e) => ($("#chain").innerHTML = `<li><b>error</b><div>${esc(e)}</div></li>`));
loadNumbers().catch((e) => ($("#x-lesson").textContent = String(e)));
goto(+(location.hash.slice(1)) || 1);

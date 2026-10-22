// Plexus deck. A 1920x1080 stage scaled to the window; arrows / space /
// click to move; S opens a presenter window kept in step over a
// BroadcastChannel; F toggles fullscreen. ?print=1 is the export view.
// window.deckDemo is what demo/record.py drives. With window.DECK_SNAPSHOT
// set (the static site, see site/build.py) there is no API: answers come
// from a recorded run, and the live slide replays it.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const SNAP = window.DECK_SNAPSHOT;
const api = async (path, opts) => {
  if (SNAP) return replay(path, opts);
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
  return r.json();
};
// The recorded answers. The policy change keeps its state here, and each
// refund takes a second or two instead of its recorded 4 to 10.
const sim = { v3: false, results: {}, publish: null };
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
async function replay(path, opts) {
  const body = opts?.body ? JSON.parse(opts.body) : {};
  if (path === "/ui/harness") return SNAP.harness;
  if (path === "/exec/numbers") return SNAP.numbers;
  if (path.startsWith("/exec/audit/")) return SNAP.audit;
  if (path === "/deck/policy/state") return structuredClone(sim);
  if (path === "/deck/policy/reset") return Object.assign(sim, { v3: false, results: {}, publish: null });
  if (path === "/deck/policy/publish") {
    await pause(500);
    return Object.assign(sim, { v3: true, publish: SNAP.policy.publish }).publish;
  }
  if (path === "/deck/policy/try") {
    const r = body.case === "jul" ? SNAP.policy.jul : SNAP.policy[sim.v3 ? "after" : "before"];
    await pause(Math.min(2000, 300 * r.seconds));
    return (sim.results[body.label] = r);
  }
  throw new Error(`${path}: not in the recording`);
}
const post = (path, body) => api(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body ?? {}) });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const params = new URLSearchParams(location.search);
const PRESENTER = params.has("presenter");
if (params.has("print")) document.body.classList.add("print");
if (params.has("demo")) document.body.classList.add("demo");
if (PRESENTER) { document.body.classList.add("presenter-mode"); $("#presenter").classList.remove("hidden"); }

const slides = $$(".slide");
const chan = "BroadcastChannel" in window ? new BroadcastChannel("plexus-deck") : null;
let current = 1;

function fit() {
  const vp = $("#viewport").getBoundingClientRect();
  $("#stage").style.transform = `translate(-50%, -50%) scale(${Math.min(vp.width / 1920, vp.height / 1080)})`;
}
addEventListener("resize", fit);
fit();

function goto(n, from = "local") {
  current = Math.max(1, Math.min(slides.length, n));
  slides.forEach((s, i) => s.classList.toggle("on", i + 1 === current));
  $("#pageno").textContent = `${current} / ${slides.length}`;
  clearSpot();
  history.replaceState(null, "", `${location.search}#${current}`);
  const s = slides[current - 1];
  if (PRESENTER) {
    $("#p-title").textContent = `${current}. ${s.dataset.title}`;
    $("#p-notes").textContent = $(".notes", s)?.textContent.trim() || "";
    $("#p-next").textContent = slides[current] ? slides[current].dataset.title : "end";
  }
  if (from === "local") chan?.postMessage({ type: "goto", n: current });
  if (s.dataset.title === "The harness is data") loadHarness();
}
chan && (chan.onmessage = (e) => {
  if (e.data.type === "goto" && e.data.n !== current) goto(e.data.n, "remote");
  if (e.data.type === "policy") drawPolicy(e.data.state, false);
});
addEventListener("keydown", (e) => {
  if (["ArrowRight", "PageDown", " "].includes(e.key)) { e.preventDefault(); goto(current + 1); }
  if (["ArrowLeft", "PageUp"].includes(e.key)) goto(current - 1);
  if (e.key === "Home") goto(1);
  if (e.key === "End") goto(slides.length);
  if (e.key === "s" || e.key === "S") window.open(`${location.pathname}?presenter=1#${current}`, "plexus-presenter", "width=1500,height=800");
  if (e.key === "f" || e.key === "F") document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
});
$("#stage").addEventListener("click", (e) => {
  if (e.target.closest("button, a, input")) return;
  goto(current + 1);
});
const t0 = Date.now();
if (PRESENTER) setInterval(() => { const s = Math.floor((Date.now() - t0) / 1000); $("#p-timer").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }, 1000);

// --- 5: the harness, live -----------------------------------------------------
async function loadHarness() {
  const h = await api("/ui/harness");
  $("#h-always").textContent = `${h.always_on_chars.toLocaleString()} chars`;
  $("#h-skills").textContent = `${h.skills.length} skills`;
  $("#h-hints").textContent = `${h.tool_hints.length} hints`;
  $("#h-lessons").textContent = `${h.lessons.length} lessons`;
  $("#h-meter").textContent = `${h.always_on_chars.toLocaleString()} of ${h.always_on_cap.toLocaleString()} always-on characters used`;
  requestAnimationFrame(() => ($("#h-bar").style.width = `${(100 * h.always_on_chars) / h.always_on_cap}%`));
  return h;
}

// --- 6: the live policy change ------------------------------------------------
// The server keeps the state (v3 published or not, last results), so the
// presenter window, a reload and the .pptx export all show the same thing.
let policy = { v3: false, results: {}, publish: null, pending: null };

function result(r, pendingText) {
  if (!r) return pendingText ? { cls: "wait", html: `<span class="out">${pendingText}</span>` } : { cls: "", html: "" };
  const ver = esc(r.in_force);
  return r.landed
    ? { cls: "ok", html: `<span class="out">Committed</span><span class="why">ticket ${r.ticket_id}, ${r.days} days, ${ver} in force · ${r.seconds}s</span>` }
    : { cls: "no", html: `<span class="out">Rejected, rolled back</span><span class="why">ticket ${r.ticket_id}, ${r.days} days, ${ver} in force · ${r.seconds}s</span><span class="err">${esc(r.error)}</span>` };
}
function put(id, r) {
  const el = $(id);
  el.className = `st-r ${r.cls}`;
  el.innerHTML = r.html;
}
function drawPolicy(state, broadcast = true) {
  policy = { ...policy, ...state };
  const p = policy.pending;
  $("#tl").classList.toggle("published", !!policy.v3);
  put("#r-before", result(policy.results.before, p === "before" && "The agent is checking the policy…"));
  const pub = policy.publish;
  put("#r-publish", pub ? { cls: "ok", html: `<span class="out">Published</span><span class="why">in force on 10 Oct: ${esc(pub.in_force["2026-10-10"])}, on 20 Jul: ${esc(pub.in_force["2026-07-20"])} · ${pub.seconds}s</span>` }
    : p === "publish" ? { cls: "wait", html: `<span class="out">Publishing…</span>` } : { cls: "", html: "" });
  put("#r-after", result(policy.results.after, p === "after" && "The agent is checking the policy…"));
  put("#r-jul", result(policy.results.jul, p === "jul" && "Now ticket 103, from July…"));
  const next = !policy.results.before ? "before" : !policy.v3 ? "publish" : "after";
  $$("#steps li").forEach((li) => li.classList.toggle("active", li.id === `st-${next}`));
  $$("#steps button").forEach((b) => (b.disabled = !!p));
  if (broadcast) chan?.postMessage({ type: "policy", state: policy });
}
async function step(label, fn) {
  drawPolicy({ pending: label });
  try {
    await fn();
  } finally {
    const s = await api("/deck/policy/state");
    drawPolicy({ ...s, pending: null });
  }
  return policy;
}
const tryRefund = (label) => step(label, () => post("/deck/policy/try", { case: label === "jul" ? "jul" : "oct", label }));
const publish = () => step("publish", () => post("/deck/policy/publish"));
async function resetPolicy() {
  await post("/deck/policy/reset");
  drawPolicy({ v3: false, results: {}, publish: null, pending: null });
}
async function runAfter() {
  await tryRefund("after");
  return tryRefund("jul");
}
$("#steps").addEventListener("click", (e) => {
  const a = e.target.dataset.act;
  if (a === "before") tryRefund("before");
  if (a === "publish") publish();
  if (a === "after") runAfter();
});
$("#btn-policy-reset").addEventListener("click", resetPolicy);

// --- 7: the auditor's chain ---------------------------------------------------
const pillFor = (v) => (String(v).includes("v1") ? "v1" : "v2");
async function loadAudit(id = 104) {
  const t = await api(`/exec/audit/${id}`);
  $("#aud-id").textContent = t.id;
  const decided = t.refund_decision
    ? `<span class="pill ${t.refund_decision === "approve" ? "yes" : t.refund_decision === "deny" ? "esc" : "v1"}">${esc(t.refund_decision)}</span> under <span class="pill ${pillFor(t.policy_version)}">${esc(t.policy_version)}</span>`
    : `<span class="muted">not decided yet</span>`;
  const items = [
    ["The ticket", esc(t.subject), `${esc(t.tier)} tier, charged ${esc(t.charge_date)}, opened ${esc(t.created)}: ${t.days} days apart`],
    ["Policy in force that day", `<span class="pill ${pillFor(t.policy.in_force)}">${esc(t.policy.in_force)}</span> as of ${esc(t.policy.as_of)}`, esc(t.policy.text.split(/\n(?=\d\. )/).slice(0, 3).map((c) => c.replace(/\s+/g, " ").trim()).join("\n"))],
    ["Where the agent looked it up", t.step ? `step ${t.step.n} of the run's trajectory` : `<span class="muted">no lookup in the latest run</span>`, t.step ? esc(t.step.action.slice(0, 200)) : ""],
    ["What it decided", decided, ""],
    ["The audit line it wrote", esc(t.audit[0] || "none"), ""],
  ];
  $("#chain").innerHTML = items.map(([k, v, m], i) => `<li id="ch-${i}"><b>${k}</b><div><div class="v">${v}</div>${m ? `<div class="m">${m}</div>` : ""}</div></li>`).join("");
  return t;
}

// --- 8: measured numbers ------------------------------------------------------
async function loadNumbers() {
  const n = await api("/exec/numbers");
  $("#n-base").textContent = n.base_per_ticket.toLocaleString();
  $("#n-after").textContent = n.adopted_per_ticket.toLocaleString();
  $("#n-pass").textContent = n.all_passed ? `${n.rollouts}/${n.rollouts}` : "not all";
  const l = n.lesson || {};
  $("#x-lesson").innerHTML = `<h3>The lesson it wrote down for next time</h3><div class="cue">${esc(l.cue)}</div><div class="txt">${esc(l.lesson)}</div>`;
  return n;
}

// --- spotlight (screen coordinates, so it works on the scaled stage) ----------
function spotlight(selector, caption, pad = 12) {
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

window.deckDemo = { goto, spotlight, clearSpot, tryRefund, publish, runAfter, resetPolicy, loadAudit, loadNumbers, loadHarness, policy: () => policy, ready: false };

if (SNAP) {
  document.body.classList.add("static");
  $(".s-live .live-tag").textContent = "Recorded";
  $("#recorded").textContent = `Replaying a real run recorded ${SNAP.recorded}. Clone the repo to run it live.`;
}

Promise.allSettled([
  api("/deck/policy/state").then((s) => drawPolicy(s, false)),
  loadAudit().catch((e) => ($("#chain").innerHTML = `<li><b>Could not load</b><div>${esc(e)}</div></li>`)),
  loadNumbers().catch((e) => ($("#x-lesson").textContent = String(e))),
  loadHarness().catch(() => {}),
]).then(() => (window.deckDemo.ready = true));
goto(+location.hash.slice(1) || 1, "init");

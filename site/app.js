/* Eventrrr Scout — review UI. One UI, two data providers:
   - Supabase (scout.eventrrr.com): Google login, events + decisions in scout_* tables.
   - Inline (artifact / mock built by scout/render.py): window.SCOUT_INLINE = {meta, events}; decisions in localStorage. */
(() => {
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const TZ = "America/Mexico_City";
const CHEV = `<svg class="chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3l5 5-5 5"/></svg>`;
const EXT = `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9 2h5v5M14 2L7 9M12 9v4H3V4h4"/></svg>`;
const GOOGLE = `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.7-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.8z"/><path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.1 0-5.8-2.1-6.7-5H1.3v3.1C3.3 21.3 7.3 24 12 24z"/><path fill="#FBBC05" d="M5.3 14.3c-.5-1.5-.5-3.1 0-4.6V6.6H1.3c-1.7 3.4-1.7 7.4 0 10.8l4-3.1z"/><path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4C17.9 1.2 15.2 0 12 0 7.3 0 3.3 2.7 1.3 6.6l4 3.1c.9-2.9 3.6-4.9 6.7-4.9z"/></svg>`;

const fmtTime = (iso) => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit", timeZone: TZ}); };
const fmtDate = (iso) => { const d = new Date(iso); return isNaN(d) ? "Date unknown" : d.toLocaleDateString("en-US", {month: "short", day: "numeric", year: "numeric", timeZone: TZ}); };
const fmtRange = (e) => e.all_day ? "All day" : fmtTime(e.starts_at) + (e.ends_at ? " – " + fmtTime(e.ends_at) : "");
const fmtLong = (e) => { const d = new Date(e.starts_at); if (isNaN(d)) return "Date unknown"; return d.toLocaleDateString("en-US", {weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: TZ}) + ", " + fmtRange(e); };
const price = (e) => e.price_text ? e.price_text : (e.price_min === 0 ? "Free" : (e.price_min != null ? `${e.price_min} ${e.currency || "MXN"}` : "Not listed"));
const srcName = (e) => (e.source_links && e.source_links[0] && e.source_links[0].name) || ((e.sources || [])[0] || "").split(":")[1] || "Unknown";
let toastT; const toast = (t) => { const el = $("#toast"); el.textContent = t; el.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove("show"), 2200); };
const setSync = (t) => { const el = $("#sync"); if (el) el.textContent = t; };

// ---------- state
let META = {run: "", categories: []}, EVENTS = [], byKey = {}, decisions = {}, selected = new Set(), current = null, provider = null;

// ---------- providers
function inlineProvider(inline) {
  const LS = () => "scout-decisions-" + META.run;
  return {
    name: "inline",
    async runs() { return [{run: inline.meta.run, umbrella: inline.meta.umbrella}]; },
    async load(run) { META = inline.meta; EVENTS = inline.events; let d = {}; try { d = JSON.parse(localStorage.getItem(LS()) || "{}"); } catch {} return d; },
    async save(run, key, row) { decisions[key] = row; try { localStorage.setItem(LS(), JSON.stringify(decisions)); } catch {} setSync("Saved on this device"); },
    user: null,
  };
}
function supabaseProvider(sb, user, cfg) {
  // Events come from the public repo (runs/index.json + runs/<run>/events.json); decisions live in Supabase.
  const base = (cfg.eventsBase || "").replace(/\/$/, "");
  const get = async (path) => { const r = await fetch(`${base}/${path}?t=${Date.now()}`, {cache: "no-store"}); if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json(); };
  return {
    name: "supabase", user,
    async runs() { const idx = await get("runs/index.json"); return (idx.runs || []).filter((r) => !r.hidden); },
    async load(run) {
      const idx = await get("runs/index.json"); const r = (idx.runs || []).find((x) => x.run === run) || {run};
      EVENTS = await get(`runs/${run}/events.json`);
      META = {run, umbrella: r.umbrella, window: r.window || "", categories: window.SCOUT_CATEGORIES || [...new Set(EVENTS.map((e) => e.category))]};
      const {data: ds, error} = await sb.from("scout_decisions").select("*").eq("run", run); if (error) throw error;
      const d = {}; (ds || []).forEach((x) => { d[x.key] = {decision: x.decision, note: x.note, at: x.updated_at}; });
      return d;
    },
    async save(run, key, row) {
      decisions[key] = row; setSync("Saving…");
      const {error} = await sb.from("scout_decisions").upsert({run, key, decision: row.decision || null, note: row.note || null, updated_at: new Date().toISOString(), updated_by: user.email}, {onConflict: "run,key"});
      setSync(error ? "Save failed: " + error.message : "Saved");
    },
  };
}

// ---------- helpers
const decisionOf = (e) => decisions[e.key]?.decision || null;
function statusOf(e) {
  const d = decisionOf(e);
  if (d === "keep") return {cls: "ready", text: "Kept"};
  if (d === "skip") return {cls: "", text: "Skipped"};
  if (e.confidence != null && e.confidence < 0.75) return {cls: "dup", text: "Check date"};
  return {cls: "review", text: "To review"};
}
function visible() {
  const q = $("#q").value.trim().toLowerCase(), cat = $("#cat").value, src = $("#src").value;
  return EVENTS.filter((e) =>
    (!cat || e.category === cat) && (!src || srcName(e) === src) &&
    (!$("#hi").checked || e.highlight) && (!$("#fam").checked || e.family_friendly) &&
    (!$("#hideskip").checked || decisionOf(e) !== "skip") &&
    (!q || `${e.title} ${e.venue} ${e.neighborhood} ${e.organizer}`.toLowerCase().includes(q))
  ).sort((a, b) => (a.starts_at || "").localeCompare(b.starts_at || ""));
}
function saveDecision(key, patch) {
  const row = Object.assign({}, decisions[key] || {}, patch, {at: new Date().toISOString()});
  provider.save(META.run, key, row);
}
const LS_SEL = () => "scout-selected-" + META.run;
function saveSel() { try { localStorage.setItem(LS_SEL(), JSON.stringify([...selected])); } catch {} }

// ---------- render
function fillSelects() {
  const cats = (META.categories || []).filter((c) => EVENTS.some((e) => e.category === c));
  $("#cat").innerHTML = `<option value="">All categories</option>` + cats.map((c) => `<option>${esc(c)}</option>`).join("");
  const srcs = [...new Set(EVENTS.map(srcName))].sort();
  $("#src").innerHTML = `<option value="">All sources</option>` + srcs.map((s) => `<option>${esc(s)}</option>`).join("");
}
function render() {
  const kept = EVENTS.filter((e) => decisionOf(e) === "keep").length, skipped = EVENTS.filter((e) => decisionOf(e) === "skip").length;
  $("#metrics").innerHTML = [[EVENTS.length, "found"], [EVENTS.filter((e) => e.highlight).length, "highlights"], [kept, "kept"], [EVENTS.length - kept - skipped, "to review"]]
    .map(([n, l]) => `<div class="metric"><b>${n}</b> ${l}</div>`).join("");
  const rows = visible();
  $("#rows").innerHTML = rows.length ? rows.map((e) => {
    const s = statusOf(e); const d = decisionOf(e);
    return `<tr data-k="${esc(e.key)}" data-current="${current === e.key}" data-skip="${d === "skip"}">
      <td class="c-check"><input class="cb" type="checkbox" data-sel="${esc(e.key)}" ${selected.has(e.key) ? "checked" : ""} aria-label="Select ${esc(e.title)} for export"></td>
      <td class="c-name"><button class="name-btn" data-open="${esc(e.key)}">${e.highlight ? `<span class="star" aria-label="Highlight">★</span>` : ""}${esc(e.title)}</button></td>
      <td class="c-cat"><span class="sub">${esc(e.category)}</span>${e.family_friendly ? `<div class="sub">Family-friendly</div>` : ""}</td>
      <td class="c-date"><div class="date-main">${esc(fmtDate(e.starts_at))}</div><div class="data">${esc(fmtRange(e))}</div></td>
      <td class="c-src"><span class="sub">${esc(srcName(e))}${(e.source_count || 1) > 1 ? ` +${e.source_count - 1}` : ""}</span></td>
      <td class="c-status"><span class="status"><span class="dot ${s.cls}"></span>${s.text}</span></td>
      <td class="c-chev"><button class="icon-btn name-btn" data-open="${esc(e.key)}" aria-label="Open ${esc(e.title)}">${CHEV}</button></td>
    </tr>`;
  }).join("") : `<tr><td colspan="7" class="empty">${EVENTS.length ? "No events match these filters." : "No events in this run yet."}</td></tr>`;
  const vis = rows.filter((e) => selected.has(e.key)).length;
  const all = $("#selall"); all.checked = rows.length > 0 && vis === rows.length; all.indeterminate = vis > 0 && vis < rows.length;
  $("#selcount").textContent = `${selected.size} event${selected.size === 1 ? "" : "s"} selected`;
  $("#exportlabel").textContent = selected.size ? `Export to Eventrrr (${selected.size})` : "Export to Eventrrr";
  $("#export").disabled = selected.size === 0;
  renderInspector();
}
function renderInspector() {
  const el = $("#insp"), e = byKey[current];
  if (!e) { el.hidden = true; el.innerHTML = ""; return; }
  const s = statusOf(e), d = decisions[e.key] || {};
  const links = (e.source_links || []).map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name || l.url)}${EXT}</a>`).join("<br>");
  el.hidden = false;
  el.innerHTML = `
    <div class="insp-head"><span class="label">Event details</span><button class="icon-btn btn btn-secondary close" id="closeinsp" aria-label="Close details"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13"/></svg></button></div>
    <h2 class="ev-title">${esc(e.title)}</h2>
    <span class="status"><span class="dot ${s.cls}"></span>${s.text}${e.highlight ? " · Highlight" : ""}</span>
    <dl class="fields">
      <dt>Date &amp; time</dt><dd class="data" style="color:var(--nv-ink)">${esc(fmtLong(e))}</dd>
      <dt>Category</dt><dd>${esc(e.category)}${e.category_alt ? ` <span class="sub">(or ${esc(e.category_alt)})</span>` : ""}${e.family_friendly ? `<div class="sub">Family-friendly</div>` : ""}</dd>
      ${e.umbrella ? `<dt>Part of</dt><dd>${esc(e.umbrella)}</dd>` : ""}
      <dt>Location</dt><dd>${esc(e.venue || "Not listed")}${(e.address || e.neighborhood) ? `<div class="sub">${esc([e.address, e.neighborhood].filter(Boolean).join(", "))}</div>` : ""}</dd>
      <dt>Price</dt><dd>${esc(price(e))}</dd>
      ${e.organizer ? `<dt>Organizer</dt><dd>${esc(e.organizer)}</dd>` : ""}
      <dt>Event link</dt><dd>${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url.replace(/^https?:\/\/(www\.)?/, "").slice(0, 48))}${EXT}</a>` : "None found"}</dd>
      <dt>Score</dt><dd>${e.score ?? 0}${e.highlight_why ? `<div class="sub">${esc(e.highlight_why)}</div>` : ""}</dd>
      <dt>Confidence</dt><dd>${e.confidence != null ? Math.round(e.confidence * 100) + "%" : "Unavailable"}</dd>
    </dl>
    ${e.description ? `<p class="sec" style="margin:24px 0 0">${esc(e.description)}</p>` : ""}
    <div class="sec">
      <div class="actions">
        <button class="btn btn-primary" data-act="keep" ${d.decision === "keep" ? 'aria-pressed="true"' : ""}>${d.decision === "keep" ? "Kept" : "Keep"}<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
        <button class="btn btn-secondary" data-act="skip" aria-pressed="${d.decision === "skip"}">${d.decision === "skip" ? "Skipped" : "Skip"}</button>
      </div>
      <label class="sr" for="note">Public note</label>
      <textarea class="input" id="note" maxlength="140" placeholder="Public note (shows on the curated calendar)">${esc(d.note || "")}</textarea>
      <div class="counter"><span id="notecount">${(d.note || "").length}</span> / 140</div>
    </div>
    <div class="sec">
      <div class="label" style="margin-bottom:16px">Source information</div>
      <dl class="fields" style="border:0;padding:0">
        <dt>Seen in</dt><dd>${links || esc((e.sources || []).join(", ")) || "Unknown"}</dd>
        <dt>Mentions</dt><dd>${e.source_count || (e.sources || []).length}</dd>
      </dl>
      ${e.thumb ? `<img class="thumb" src="${e.thumb}" alt="Flyer">` : ""}
      ${e.source_excerpt ? `<div class="excerpt">${esc(e.source_excerpt)}</div>` : ""}
    </div>`;
  const c = $("#closeinsp"); if (c) c.onclick = () => { current = null; render(); };
}

// ---------- export (contract: docs/eventrrr-import-prompt.md)
function exportJson(list) {
  return JSON.stringify({eventrrr_import: 1, source: "eventrrr-scout", run: META.run, events: list.map((e) => ({
    title: e.title, starts_at: e.starts_at, ends_at: e.ends_at || null, all_day: !!e.all_day, timezone: e.timezone || TZ,
    venue: e.venue || null, address: e.address || null, neighborhood: e.neighborhood || null,
    price_text: e.price_text || (e.price_min === 0 ? "Free" : null), price_min: e.price_min ?? null, currency: e.currency || "MXN",
    url: e.url && /^https?:\/\//.test(e.url) ? e.url : null, category: e.category, description: e.description || null,
    public_note: (decisions[e.key]?.note || "").slice(0, 140) || null,
  }))}, null, 1);
}
function copyText(t, ok) {
  navigator.clipboard.writeText(t).then(() => toast(ok), () => { const r = document.createElement("textarea"); r.value = t; document.body.appendChild(r); r.select(); try { document.execCommand("copy"); toast(ok); } catch { toast("Copy failed"); } r.remove(); });
}

// ---------- events
function wire() {
  document.addEventListener("click", (ev) => {
    const open = ev.target.closest("[data-open]"); if (open) { current = open.dataset.open; render(); return; }
    const act = ev.target.closest("[data-act]"); if (act && current) {
      const cur = decisionOf(byKey[current]); const next = cur === act.dataset.act ? null : act.dataset.act;
      saveDecision(current, {decision: next});
      if (next === "keep") selected.add(current); if (next === "skip") selected.delete(current); saveSel();
      render();
    }
  });
  document.addEventListener("change", (ev) => {
    const sel = ev.target.closest("[data-sel]"); if (sel) { sel.checked ? selected.add(sel.dataset.sel) : selected.delete(sel.dataset.sel); saveSel(); render(); return; }
    if (ev.target.id === "selall") { visible().forEach((e) => ev.target.checked ? selected.add(e.key) : selected.delete(e.key)); saveSel(); render(); return; }
    if (ev.target.id === "note" && current) saveDecision(current, {note: ev.target.value});
    if (ev.target.id === "runsel") loadRun(ev.target.value);
  });
  document.addEventListener("input", (ev) => { if (ev.target.id === "note") $("#notecount").textContent = ev.target.value.length; });
  ["#q", "#cat", "#src", "#hi", "#fam", "#hideskip"].forEach((s) => $(s).addEventListener("input", render));
  $("#selkept").onclick = () => { EVENTS.forEach((e) => { if (decisionOf(e) === "keep") selected.add(e.key); }); saveSel(); render(); };
  const dx = $("#exportdecisions"); if (dx) dx.onclick = () => copyText(JSON.stringify({run: META.run, exported_at: new Date().toISOString(), decisions}, null, 1), "Decisions copied; paste them to Claude for the learning loop");
  $("#export").onclick = () => {
    const list = EVENTS.filter((e) => selected.has(e.key));
    if (!list.length) return toast("Select events first");
    if (list.length > 100) return toast("Eventrrr imports up to 100 at a time; narrow the selection");
    copyText(exportJson(list), `${list.length} event${list.length === 1 ? "" : "s"} copied. Paste into Eventrrr → Paste text.`);
  };
}

// ---------- boot
async function loadRun(run) {
  current = null; selected = new Set();
  decisions = await provider.load(run);
  byKey = Object.fromEntries(EVENTS.map((e) => [e.key, e]));
  try { selected = new Set(JSON.parse(localStorage.getItem(LS_SEL()) || "[]").filter((k) => byKey[k])); } catch {}
  try { if (location.hash.slice(1) !== run) history.replaceState(null, "", "#" + run); } catch {}
  fillSelects(); render(); setSync(provider.name === "supabase" ? "Synced" : "");
}
function showApp(runs) {
  $("#app").hidden = false; $("#gate").hidden = true;
  const sel = $("#runsel");
  if (sel) sel.innerHTML = runs.map((r) => `<option value="${esc(r.run)}">${esc(r.run)}${r.umbrella ? " · " + esc(r.umbrella) : ""}</option>`).join("");
  const wanted = (() => { try { return location.hash.slice(1); } catch { return ""; } })();
  const run = runs.find((r) => r.run === wanted)?.run || (runs[0] && runs[0].run);
  if (sel && run) sel.value = run;
  if (run) loadRun(run); else render();
}
function showGate(html) { $("#app").hidden = true; const g = $("#gate"); g.hidden = false; g.innerHTML = html; }

async function boot() {
  wire();
  if (window.SCOUT_INLINE) { provider = inlineProvider(window.SCOUT_INLINE); showApp(await provider.runs()); return; }
  const cfg = window.SCOUT_CONFIG || {};
  if (!cfg.supabaseUrl || !cfg.supabaseAnonKey || !window.supabase) { showGate(`<div class="gate-card"><h2 class="title">Eventrrr Scout</h2><p>Not configured yet: site/config.js needs the Supabase URL and anon key.</p></div>`); return; }
  const sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
  const signIn = () => sb.auth.signInWithOAuth({provider: "google", options: {redirectTo: location.origin + location.pathname}});
  const gateSignIn = () => { showGate(`<div class="gate-card"><h2 class="title">Eventrrr Scout</h2><p>Event review for curated calendars. Sign in to continue.</p><button class="btn btn-secondary btn-google" id="signin">${GOOGLE} Continue with Google</button></div>`); $("#signin").onclick = signIn; };
  const {data: {session}} = await sb.auth.getSession();
  if (!session) { gateSignIn(); sb.auth.onAuthStateChange((_, s) => { if (s) location.reload(); }); return; }
  const user = session.user;
  const {data: rev} = await sb.from("scout_reviewers").select("email").limit(1);
  if (!rev || !rev.length) {
    showGate(`<div class="gate-card"><h2 class="title">Not on the list</h2><p>${esc(user.email)} isn't a reviewer for this scout.</p><button class="btn btn-secondary" id="signout">Sign out</button></div>`);
    $("#signout").onclick = async () => { await sb.auth.signOut(); location.reload(); }; return;
  }
  provider = supabaseProvider(sb, user, cfg);
  const acct = $("#account");
  if (acct) { acct.innerHTML = `${user.user_metadata?.avatar_url ? `<img class="avatar" src="${esc(user.user_metadata.avatar_url)}" alt="">` : ""}<button class="btn btn-secondary" id="signout">Sign out</button>`; $("#signout").onclick = async () => { await sb.auth.signOut(); location.reload(); }; }
  let runs = [];
  try { runs = await provider.runs(); } catch (e) { showGate(`<div class="gate-card"><h2 class="title">Couldn't load runs</h2><p>${esc(e.message || e)}</p></div>`); return; }
  showApp(runs);
}
boot();
})();

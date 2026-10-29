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
    async profiles() { try { return JSON.parse(localStorage.getItem("scout-profiles") || "null") || DEFAULT_PROFILES; } catch { return DEFAULT_PROFILES; } },
    async saveProfile(p) { const ps = (await this.profiles()).filter((x) => x.slug !== p.slug).concat([p]); try { localStorage.setItem("scout-profiles", JSON.stringify(ps)); } catch {} },
    async assignments() { try { return JSON.parse(localStorage.getItem("scout-assignments") || "[]"); } catch { return []; } },
    async assign(run, key, profile, on) { let as = await this.assignments(); as = as.filter((x) => !(x.run === run && x.key === key && x.profile === profile)); if (on) as.push({run, key, profile, source: "manual", updated_at: new Date().toISOString()}); try { localStorage.setItem("scout-assignments", JSON.stringify(as)); } catch {} },
    async allEvents() { return (inline.events || []).map((e) => Object.assign({run: inline.meta.run}, e)); },
  };
}
const DEFAULT_PROFILES = [
  {slug: "foodie", name: "Food & Drink", sort_order: 10, active: true}, {slug: "cultural", name: "Arts & Culture", sort_order: 20, active: true},
  {slug: "nightlife", name: "Nightlife & Bars", sort_order: 30, active: true}, {slug: "music", name: "Live Music", sort_order: 40, active: true}, {slug: "active", name: "Sports & Movement", sort_order: 50, active: true},
];
function supabaseProvider(sb, user, cfg) {
  // Events come from the public repo (runs/index.json + runs/<run>/events.json); decisions live in Supabase.
  const base = (cfg.eventsBase || "").replace(/\/$/, "");
  const get = async (path) => { const r = await fetch(`${base}/${path}?t=${Math.floor(Date.now() / 60000)}`, {cache: "no-store"}); if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json(); };
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
    async profiles() { const {data, error} = await sb.from("scout_profiles").select("*").order("sort_order"); if (error) throw error; return data || []; },
    async saveProfile(p) { const {error} = await sb.from("scout_profiles").upsert(Object.assign({}, p, {updated_at: new Date().toISOString()}), {onConflict: "slug"}); if (error) throw error; },
    async assignments() { const {data, error} = await sb.from("scout_assignments").select("*").limit(5000); if (error) throw error; return data || []; },
    async assign(run, key, profile, on) {
      if (on) { const {error} = await sb.from("scout_assignments").upsert({run, key, profile, source: "manual", updated_by: user.email, updated_at: new Date().toISOString()}, {onConflict: "run,key,profile"}); if (error) throw error; }
      else { const {error} = await sb.from("scout_assignments").delete().match({run, key, profile}); if (error) throw error; }
    },
    async allEvents() {
      const idx = await get("runs/index.json"); const out = [];
      for (const r of (idx.runs || []).filter((x) => !x.hidden && !x.run.startsWith("sample"))) {
        try { (await get(`runs/${r.run}/events.json`)).forEach((e) => out.push(Object.assign({run: r.run}, e))); } catch {}
      }
      return out;
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
function detailFields(e) {
  return `<dl class="fields">
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
    ${e.description ? `<p class="sec" style="margin:24px 0 0">${esc(e.description)}</p>` : ""}`;
}
function detailSources(e) {
  const links = (e.source_links || []).map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name || l.url)}${EXT}</a>`).join("<br>");
  return `    <div class="sec">
      <div class="label" style="margin-bottom:16px">Source information</div>
      <dl class="fields" style="border:0;padding:0">
        <dt>Seen in</dt><dd>${links || esc((e.sources || []).join(", ")) || "Unknown"}</dd>
        <dt>Mentions</dt><dd>${e.source_count || (e.sources || []).length}</dd>
      </dl>
      ${e.thumb ? `<img class="thumb" src="${e.thumb}" alt="Flyer">` : ""}
      ${e.source_excerpt ? `<div class="excerpt">${esc(e.source_excerpt)}</div>` : ""}
    </div>`;
}
function renderInspector() {
  const el = $("#insp"), e = byKey[current];
  if (!e) { el.hidden = true; el.innerHTML = ""; return; }
  const s = statusOf(e), d = decisions[e.key] || {};
  el.hidden = false;
  el.innerHTML = `
    <div class="insp-head"><span class="label">Event details</span><button class="icon-btn btn btn-secondary close" id="closeinsp" aria-label="Close details"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13"/></svg></button></div>
    <h2 class="ev-title">${esc(e.title)}</h2>
    <span class="status"><span class="dot ${s.cls}"></span>${s.text}${e.highlight ? " · Highlight" : ""}</span>
    ${detailFields(e)}
    <div class="sec">
      <div class="actions">
        <button class="btn btn-primary" data-act="keep" ${d.decision === "keep" ? 'aria-pressed="true"' : ""}>${d.decision === "keep" ? "Kept" : "Keep"}<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
        <button class="btn btn-secondary" data-act="skip" aria-pressed="${d.decision === "skip"}">${d.decision === "skip" ? "Skipped" : "Skip"}</button>
      </div>
      <label class="sr" for="note">Public note</label>
      <textarea class="input" id="note" maxlength="140" placeholder="Public note (shows on the curated calendar)">${esc(d.note || "")}</textarea>
      <div class="counter"><span id="notecount">${(d.note || "").length}</span> / 140</div>
    </div>
    ${detailSources(e)}
`;
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
  document.querySelectorAll(".nav a[data-tab]").forEach((a) => a.addEventListener("click", (ev) => { ev.preventDefault(); try { location.hash = a.dataset.tab; } catch {} showTab(a.dataset.tab); }));
  document.addEventListener("click", (ev) => { const r = ev.target.closest("[data-openrun]"); if (r) { ev.preventDefault(); const sel = $("#runsel"); if (sel) sel.value = r.dataset.openrun; showTab("events"); loadRun(r.dataset.openrun); } });
  $("#rf-weeks").addEventListener("change", rfDates); $("#rf-from").addEventListener("change", rfDates);
  $("#as-kind").addEventListener("change", () => { const ig = $("#as-kind").value === "instagram"; $("#as-valuelabel").textContent = ig ? "Handle" : "Address"; $("#as-value").placeholder = ig ? "@cdmxsecreta" : "https://local.mx/"; $("#as-namewrap").hidden = ig; });
  $("#as-value").addEventListener("keydown", (ev) => { if (ev.key === "Enter") $("#as-add").click(); });
  ["#q", "#cat", "#src", "#hi", "#fam", "#hideskip"].forEach((s) => $(s).addEventListener("input", render));
  ["#sq", "#sstate", "#sprofile", "#srun", "#shidepast"].forEach((s) => $(s).addEventListener("input", () => { if (s === "#sstate") touched.clear(); renderSort(); }));
  document.addEventListener("click", (ev) => {
    const o = ev.target.closest("[data-sopen]"); if (o) { scur = o.dataset.sopen; $("#pinsp").hidden = false; renderSort(); renderProfiles(); return; }
    const c = ev.target.closest("[data-pa]"); if (c) toggleAssign(c.closest("[data-ak]").dataset.ak, c.dataset.pa);
  });
  $("#copysession").onclick = copySession;
  $("#sprofiles-btn").onclick = () => { $("#pinsp").hidden = false; };
  $("#selkept").onclick = () => { EVENTS.forEach((e) => { if (decisionOf(e) === "keep") selected.add(e.key); }); saveSel(); render(); };
  const dx = $("#exportdecisions"); if (dx) dx.onclick = () => copyText(JSON.stringify({run: META.run, exported_at: new Date().toISOString(), decisions}, null, 1), "Decisions copied; paste them to Claude for the learning loop");
  $("#export").onclick = () => {
    const list = EVENTS.filter((e) => selected.has(e.key));
    if (!list.length) return toast("Select events first");
    if (list.length > 100) return toast("Eventrrr imports up to 100 at a time; narrow the selection");
    copyText(exportJson(list), `${list.length} event${list.length === 1 ? "" : "s"} copied. Paste into Eventrrr → Paste text.`);
  };
}

// ---------- sources panel
let SOURCES = null;
async function renderSources() {
  const el = $("#sources-body");
  if (!SOURCES) { try { const r = await fetch("sources.json?t=" + Math.floor(Date.now() / 60000)); SOURCES = await r.json(); } catch (e) { el.innerHTML = `<p class="sub">Couldn't load sources.json</p>`; return; } }
  const pill = (on) => `<span class="pill ${on ? "on" : ""}">${on ? "On" : "Off"}</span>`;
  const sites = SOURCES.sites.map((x) => `<tr><td><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a></td><td class="sub">tier ${x.tier}</td><td class="sub">${esc(x.notes || (x.added_by ? "added " + x.added_at : ""))}</td><td>${pill(x.enabled !== false)}</td></tr>`).join("");
  const ig = SOURCES.instagram.map((x) => `<tr><td><a href="https://www.instagram.com/${esc(x.handle)}/" target="_blank" rel="noopener">@${esc(x.handle)}</a></td><td class="sub">tier ${x.tier}</td><td class="sub">${x.added_by ? "added " + esc(x.added_at) : ""}</td><td>${pill(x.enabled !== false)}</td></tr>`).join("");
  const umb = SOURCES.umbrellas.map((u) => `<tr><td>${esc(u.name)}</td><td class="sub">${u.window ? esc(u.window.from + " → " + u.window.to) : ""}</td><td class="sub">${u.known_pages} known pages</td><td></td></tr>`).join("");
  const tbl = (title, rows) => `<div class="label" style="margin:24px 0 8px">${title}</div><div class="scroll"><table class="list-table"><thead><tr><th>Name</th><th>Tier</th><th>Notes</th><th>Status</th></tr></thead><tbody>${rows || `<tr><td colspan="4" class="sub">None</td></tr>`}</tbody></table></div>`;
  el.innerHTML = tbl(`Websites · ${SOURCES.sites.length}`, sites) + tbl(`Instagram · ${SOURCES.instagram.length}`, ig) + tbl("Umbrella events", umb) +
    `<p class="sub" style="margin-top:24px">Defaults: ${SOURCES.defaults.ig_posts_per_account} posts per Instagram account, newer than ${esc(SOURCES.defaults.ig_newer_than)}.</p>`;
}

// ---------- add source
async function addSource(sb, force) {
  const st = $("#as-status"), kind = $("#as-kind").value, value = $("#as-value").value.trim(), name = $("#as-name").value.trim();
  $("#as-force").hidden = true; st.className = "sub";
  if (!value) { st.textContent = kind === "web" ? "Enter a web address." : "Enter an Instagram handle."; st.className = "sub err"; return; }
  $("#as-add").disabled = true; st.textContent = force ? "Adding…" : (kind === "web" ? "Checking the site…" : "Checking Instagram…");
  const {data: {session}} = await sb.auth.getSession();
  try {
    const r = await fetch(`${window.SCOUT_CONFIG.supabaseUrl}/functions/v1/scout-trigger`, {method: "POST", headers: {"Content-Type": "application/json", Authorization: "Bearer " + session.access_token, apikey: window.SCOUT_CONFIG.supabaseAnonKey}, body: JSON.stringify({action: "add_source", kind, value, name, force: force ? "1" : "0"})});
    const j = await r.json().catch(() => ({}));
    if (r.status === 422) { st.textContent = j.error + " You can still add it unverified."; st.className = "sub err"; $("#as-force").hidden = false; return; }
    if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
    st.textContent = `Added ${j.added}.` + (j.warn ? " " + j.warn : "") + " It appears below after the next deploy (about a minute) and in the next sweep."; st.className = "sub okk";
    $("#as-value").value = ""; $("#as-name").value = ""; SOURCES = null; toast("Source added");
    setTimeout(() => { SOURCES = null; renderSources(); }, 90000);
  } catch (e) { st.textContent = "Couldn't add: " + (e.message || e); st.className = "sub err"; }
  finally { $("#as-add").disabled = false; }
}

// ---------- runs panel + start sweep
const GH = "https://api.github.com/repos/danisbuilding/eventrrr-scout";
let runsCache = [], statusCache = null, pollT = null;
function rfDates() {
  const weeks = parseInt($("#rf-weeks").value, 10);
  const from = new Date(); const to = new Date(from.getTime() + weeks * 7 * 86400000);
  const iso = (d) => d.toISOString().slice(0, 10);
  if (!$("#rf-from").value) $("#rf-from").value = iso(from);
  $("#rf-to").value = iso(new Date(new Date($("#rf-from").value).getTime() + weeks * 7 * 86400000));
}
async function fetchStatus() {
  try { const r = await fetch(`${(window.SCOUT_CONFIG.eventsBase || "").replace(/\/$/, "")}/runs/status.json?t=${Date.now()}`, {cache: "no-store"}); statusCache = r.ok ? await r.json() : null; } catch { statusCache = null; }
  try { const r = await fetch(`${GH}/actions/workflows/pipeline.yml/runs?per_page=5`, {headers: {Accept: "application/vnd.github+json"}}); if (r.ok) { const j = await r.json(); statusCache = Object.assign({}, statusCache || {}, {gh: (j.workflow_runs || []).map((w) => ({id: w.id, status: w.status, conclusion: w.conclusion, created_at: w.created_at, url: w.html_url}))}); } } catch {}
  return statusCache;
}
async function renderRuns() {
  rfDates();
  const st = await fetchStatus();
  const live = (st && st.gh || []).find((w) => w.status !== "completed");
  const rs = $("#rf-status");
  if (live) { rs.innerHTML = `<span class="pill run">Running</span> started ${esc(new Date(live.created_at).toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit"}))} · <a href="${esc(live.url)}" target="_blank" rel="noopener">log</a>`; $("#rf-start").disabled = true; clearTimeout(pollT); pollT = setTimeout(renderRuns, 30000); }
  else { if (!rs.dataset.msg) rs.textContent = ""; $("#rf-start").disabled = false; }
  try { const r = await fetch(`${(window.SCOUT_CONFIG.eventsBase || "").replace(/\/$/, "")}/runs/index.json?t=${Math.floor(Date.now() / 60000)}`, {cache: "no-store"}); runsCache = (await r.json()).runs || []; } catch {}
  const ghById = Object.fromEntries((st && st.gh || []).map((w) => [String(w.id), w]));
  const rows = runsCache.map((r) => `<tr><td><a href="#${esc(r.run)}" data-openrun="${esc(r.run)}">${esc(r.run)}</a></td><td class="sub">${esc(r.window || "")}</td><td class="sub">${esc(r.umbrella || "")}</td><td class="sub">${r.event_count} events · ${r.highlights} ★</td><td class="sub">${r.published_at ? esc(new Date(r.published_at).toLocaleDateString("en-US", {month: "short", day: "numeric"})) : ""}</td></tr>`).join("");
  const recent = (st && st.gh || []).filter((w) => w.status === "completed" && w.conclusion !== "success").slice(0, 3).map((w) => `<tr><td><span class="pill fail">Failed</span></td><td class="sub" colspan="3">${esc(new Date(w.created_at).toLocaleString("en-US", {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}))}</td><td><a href="${esc(w.url)}" target="_blank" rel="noopener">log</a></td></tr>`).join("");
  $("#runs-body").innerHTML = `<div class="scroll"><table class="list-table"><thead><tr><th>Run</th><th>Window</th><th>Umbrella</th><th>Results</th><th>Published</th></tr></thead><tbody>${rows}${recent}</tbody></table></div>`;
}
async function startSweep(sb) {
  const rs = $("#rf-status"); rs.dataset.msg = "1";
  const payload = {window_from: $("#rf-from").value, window_to: $("#rf-to").value, umbrella: $("#rf-umbrella").value.trim(), ig_tier: $("#rf-ig").checked ? "all" : "none", scouts: $("#rf-openai").checked && $("#rf-gemini").checked ? "both" : $("#rf-openai").checked ? "openai" : $("#rf-gemini").checked ? "gemini" : "none"};
  if (!payload.window_from || !payload.window_to || payload.window_to < payload.window_from) { rs.textContent = "Pick a valid date range."; return; }
  $("#rf-start").disabled = true; rs.textContent = "Starting…";
  const {data: {session}} = await sb.auth.getSession();
  try {
    const r = await fetch(`${window.SCOUT_CONFIG.supabaseUrl}/functions/v1/scout-trigger`, {method: "POST", headers: {"Content-Type": "application/json", Authorization: "Bearer " + session.access_token, apikey: window.SCOUT_CONFIG.supabaseAnonKey}, body: JSON.stringify(payload)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || j.message || ("HTTP " + r.status));
    rs.textContent = `Sweep started (${j.run || "run"}). Usually 10–25 minutes; this page updates itself.`;
    toast("Sweep started");
    setTimeout(renderRuns, 8000);
  } catch (e) { rs.textContent = "Couldn't start: " + (e.message || e); $("#rf-start").disabled = false; }
}

// ---------- sort tab (profiles)
let PROFILES = [], POOL = [], ASSIGN = {}, pcur = null, scur = null, sortLoaded = false, CHARTERS = {}, touched = new Set();
const akey = (e) => e.run + "|" + e.key;
const splitAk = (ak) => { const i = ak.indexOf("|"); return [ak.slice(0, i), ak.slice(i + 1)]; }; // key itself contains "|date"
const profilesOf = (e) => Object.keys(ASSIGN[akey(e)] || {});
const isSorted = (e) => profilesOf(e).length > 0;
async function loadSort() {
  const st = $("#ssync"); st.textContent = "Loading…";
  try {
    PROFILES = (await provider.profiles()).filter((p) => p.active !== false).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    POOL = await provider.allEvents();
    ASSIGN = {}; const legacy = [];
    (await provider.assignments()).forEach((x) => {
      if (x.key.includes("|")) { (ASSIGN[x.run + "|" + x.key] ||= {})[x.profile] = x; return; }
      // Rows saved before 2026-10-29 lost the "|date" suffix; resolve them against the pool by slug and rewrite.
      const matches = POOL.filter((e) => e.run === x.run && e.key.split("|")[0] === x.key);
      matches.forEach((e) => { (ASSIGN[akey(e)] ||= {})[x.profile] = Object.assign({}, x, {key: e.key}); });
      if (matches.length) legacy.push({x, keys: matches.map((e) => e.key)});
    });
    if (legacy.length) { st.textContent = `Migrating ${legacy.length} rows…`; for (const {x, keys} of legacy) { for (const k of keys) await provider.assign(x.run, k, x.profile, true); await provider.assign(x.run, x.key, x.profile, false); } }
    $("#sprofile").innerHTML = `<option value="">Any profile</option>` + PROFILES.map((p) => `<option value="${esc(p.slug)}">${esc(p.name)}</option>`).join("") + `<option value="none">None</option>`;
    $("#srun").innerHTML = `<option value="">All runs</option>` + [...new Set(POOL.map((e) => e.run))].map((r) => `<option>${esc(r)}</option>`).join("");
    sortLoaded = true; st.textContent = provider.name === "supabase" ? "Synced" : "This device only";
  } catch (e) { st.textContent = "Couldn't load: " + (e.message || e); }
  renderSort(); renderProfiles();
}
function sortVisible() {
  const q = $("#sq").value.trim().toLowerCase(), state = $("#sstate").value, pf = $("#sprofile").value, run = $("#srun").value, today = new Date().toISOString().slice(0, 10);
  return POOL.filter((e) =>
    (!run || e.run === run) && (!$("#shidepast").checked || !e.starts_at || (e.ends_at || e.starts_at).slice(0, 10) >= today) &&
    (state === "all" || (state === "unsorted" && touched.has(akey(e))) || (state === "sorted") === isSorted(e)) && (!pf || profilesOf(e).includes(pf)) &&
    (!q || `${e.title} ${e.venue} ${e.neighborhood}`.toLowerCase().includes(q))
  ).sort((a, b) => (a.starts_at || "").localeCompare(b.starts_at || ""));
}
function renderSort() {
  const unsorted = POOL.filter((e) => !isSorted(e)).length;
  $("#sort-metrics").innerHTML = [[POOL.length, "in pool"], [POOL.length - unsorted, "sorted"], [unsorted, "unsorted"]].map(([n, l]) => `<div class="metric"><b>${n}</b> ${l}</div>`).join("");
  const rows = sortVisible();
  $("#srows").innerHTML = rows.length ? rows.map((e) => {
    const on = ASSIGN[akey(e)] || {};
    const chips = PROFILES.map((p) => `<button class="pchip ${on[p.slug] ? "on" : ""} ${on[p.slug]?.source === "suggested" ? "sugg" : ""}" data-pa="${esc(p.slug)}" title="${esc(on[p.slug]?.reason || p.name)}">${esc(p.name)}</button>`).join("") +
      `<button class="pchip none ${on.none ? "on" : ""}" data-pa="none">None</button>`;
    return `<tr data-ak="${esc(akey(e))}" data-current="${scur === akey(e)}">
      <td class="c-name"><button class="name-btn" data-sopen="${esc(akey(e))}">${e.highlight ? `<span class="star" aria-label="Highlight">★</span>` : ""}${esc(e.title)}</button><div class="sub">${esc([fmtDate(e.starts_at), e.venue || e.neighborhood].filter(Boolean).join(" · "))}</div></td>
      <td class="c-cat"><span class="sub">${esc(e.category)}</span></td>
      <td class="c-prof"><div class="pchips">${chips}</div></td>
      <td class="c-chev"><button class="icon-btn name-btn" data-sopen="${esc(akey(e))}" aria-label="Open ${esc(e.title)}">${CHEV}</button></td></tr>`;
  }).join("") : `<tr><td colspan="4" class="empty">${POOL.length ? "Nothing matches these filters." : "No events yet; run a sweep."}</td></tr>`;
}
async function toggleAssign(ak, profile) {
  const [run, key] = splitAk(ak); const cur = ASSIGN[ak] || {}; const on = !cur[profile]; touched.add(ak);
  if (on && profile === "none") Object.keys(cur).forEach((p) => { if (p !== "none") delete cur[p]; });
  if (on && profile !== "none") delete cur.none;
  if (on) cur[profile] = {run, key, profile, source: "manual", updated_at: new Date().toISOString()}; else delete cur[profile];
  ASSIGN[ak] = cur; renderSort(); renderProfiles();
  $("#ssync").textContent = "Saving…";
  try {
    await provider.assign(run, key, profile, on);
    if (on && profile === "none") for (const p of PROFILES) await provider.assign(run, key, p.slug, false);
    if (on && profile !== "none") await provider.assign(run, key, "none", false);
    $("#ssync").textContent = "Saved";
  } catch (e) { $("#ssync").textContent = "Save failed: " + (e.message || e); }
}
async function charterFor(slug) {
  if (CHARTERS[slug] !== undefined) return CHARTERS[slug];
  try { const r = await fetch(`${(window.SCOUT_CONFIG?.eventsBase || "").replace(/\/$/, "")}/profiles/${slug}.md?t=${Math.floor(Date.now() / 60000)}`); CHARTERS[slug] = r.ok ? (await r.text()).replace(/^---[\s\S]*?---\n/, "") : ""; } catch { CHARTERS[slug] = ""; }
  return CHARTERS[slug];
}
function renderSortDetails(el, e) {
  const on = ASSIGN[akey(e)] || {};
  const chips = PROFILES.map((p) => `<button class="pchip ${on[p.slug] ? "on" : ""}" data-pa="${esc(p.slug)}">${esc(p.name)}</button>`).join("") + `<button class="pchip none ${on.none ? "on" : ""}" data-pa="none">None</button>`;
  el.innerHTML = `<div class="insp-head"><span class="label">Event details</span><button class="icon-btn btn btn-secondary" id="sd-close" aria-label="Back to profiles"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13"/></svg></button></div>
    <h2 class="ev-title">${esc(e.title)}</h2>
    <div class="sub">${esc(e.run)}${e.highlight ? " · Highlight" : ""}</div>
    <div class="sec" style="margin-top:16px"><div class="label" style="margin-bottom:10px">Profiles</div><div class="pchips" data-ak="${esc(akey(e))}">${chips}</div></div>
    ${detailFields(e)}
    ${detailSources(e)}`;
  $("#sd-close").onclick = () => { scur = null; if (window.innerWidth < 1280) el.hidden = true; renderSort(); renderProfiles(); };
}
async function renderProfiles() {
  const el = $("#pinsp"); if (el.dataset.inited !== "1") { el.dataset.inited = "1"; el.hidden = window.innerWidth < 1280; }
  if (scur) { const e = POOL.find((x) => akey(x) === scur); if (e) { renderSortDetails(el, e); return; } scur = null; }
  const counts = {}; Object.values(ASSIGN).forEach((m) => Object.keys(m).forEach((p) => counts[p] = (counts[p] || 0) + 1));
  const list = PROFILES.map((p) => `<div class="prow ${pcur === p.slug ? "sel" : ""}" data-pp="${esc(p.slug)}"><b>${esc(p.name)}</b><span class="sub">${counts[p.slug] || 0}</span></div>`).join("") +
    `<div class="prow ${pcur === "none" ? "sel" : ""}" data-pp="none"><b class="sub">None</b><span class="sub">${counts.none || 0}</span></div>`;
  const p = PROFILES.find((x) => x.slug === pcur);
  let detail = "";
  if (p) {
    const ch = await charterFor(p.slug);
    detail = `<div class="sec"><h2 class="ev-title" style="font-size:22px;line-height:28px">${esc(p.name)}</h2><div class="sub">@${esc(p.handle || "handle not set")} · ${counts[p.slug] || 0} events</div>
      <div class="pform">
        <label>Persona<textarea class="input" id="pp-persona" rows="4">${esc(p.persona || "")}</textarea></label>
        <label>Eventrrr handle<input class="input" id="pp-handle" value="${esc(p.handle || "")}" placeholder="foodie_cdmx"></label>
        <div class="actions" style="margin-top:12px"><button class="btn btn-primary" id="pp-save" style="flex:0 0 auto">Save</button><button class="btn btn-secondary" id="pp-export" style="flex:0 0 auto">Export to Eventrrr (${counts[p.slug] || 0})</button><button class="btn btn-secondary" id="pp-archive" style="flex:0 0 auto">Archive</button></div>
      </div></div>
      <div class="sec"><div class="label" style="margin-bottom:10px">Charter &amp; notes <a class="sub" href="https://github.com/danisbuilding/eventrrr-scout/blob/main/profiles/${esc(p.slug)}.md" target="_blank" rel="noopener">(edit on GitHub)</a></div><div class="charter">${esc(ch || "No charter yet. It gets written after your first sorting session.")}</div></div>`;
  } else if (pcur === "new") {
    detail = `<div class="sec"><div class="label">New profile</div><div class="pform">
      <label>Short id (slug)<input class="input" id="pp-slug" placeholder="family" pattern="[a-z0-9-]+"></label>
      <label>Name<input class="input" id="pp-name" placeholder="Family"></label>
      <label>Persona<textarea class="input" id="pp-persona" rows="4" placeholder="Who this curator is, what they show up for, what they'd never feature."></textarea></label>
      <label>Eventrrr handle<input class="input" id="pp-handle" placeholder="family_cdmx"></label>
      <div class="actions" style="margin-top:12px"><button class="btn btn-primary" id="pp-create" style="flex:0 0 auto">Create</button></div></div></div>`;
  }
  el.innerHTML = `<div class="insp-head"><span class="label">Profiles</span><span style="display:flex;gap:8px"><button class="btn btn-secondary" id="pp-new" style="min-height:32px;padding:6px 12px">+ New</button><button class="icon-btn btn btn-secondary close" id="pp-close" aria-label="Close profiles"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13"/></svg></button></span></div><div class="plist">${list}</div>${detail}`;
  $("#pp-new").onclick = () => { pcur = "new"; renderProfiles(); };
  $("#pp-close").onclick = () => { el.hidden = true; };
  el.querySelectorAll("[data-pp]").forEach((r) => r.onclick = () => { pcur = r.dataset.pp; $("#sprofile").value = pcur; $("#sstate").value = "all"; renderSort(); renderProfiles(); });
  const save = $("#pp-save"); if (save) save.onclick = async () => { try { await provider.saveProfile(Object.assign({}, p, {persona: $("#pp-persona").value.trim(), handle: $("#pp-handle").value.trim().replace(/^@/, "") || null})); toast("Profile saved"); PROFILES = (await provider.profiles()).filter((x) => x.active !== false); renderProfiles(); } catch (e) { toast("Save failed: " + (e.message || e)); } };
  const arch = $("#pp-archive"); if (arch) arch.onclick = async () => { if (!arch.dataset.sure) { arch.textContent = "Archive? Click again"; arch.dataset.sure = "1"; return; } try { await provider.saveProfile(Object.assign({}, p, {active: false})); pcur = null; await loadSort(); toast("Profile archived; its assignments are kept"); } catch (e) { toast("Failed: " + (e.message || e)); } };
  const exp = $("#pp-export"); if (exp) exp.onclick = () => {
    const list = POOL.filter((e) => (ASSIGN[akey(e)] || {})[p.slug] && (!$("#shidepast").checked || !e.starts_at || (e.ends_at || e.starts_at).slice(0, 10) >= new Date().toISOString().slice(0, 10)));
    if (!list.length) return toast("No upcoming events on this profile");
    if (list.length > 100) return toast("Eventrrr imports up to 100 at a time");
    const saveRun = META.run; META.run = "profile:" + p.slug; copyText(exportJson(list), `${list.length} events copied for @${p.handle || p.slug}. Paste into that account → Paste text.`); META.run = saveRun;
  };
  const create = $("#pp-create"); if (create) create.onclick = async () => {
    const slug = $("#pp-slug").value.trim().toLowerCase(), name = $("#pp-name").value.trim();
    if (!/^[a-z0-9-]{2,30}$/.test(slug)) return toast("Slug: 2–30 lowercase letters, digits or dashes");
    if (!name) return toast("Give it a name");
    try { await provider.saveProfile({slug, name, persona: $("#pp-persona").value.trim(), handle: $("#pp-handle").value.trim().replace(/^@/, "") || null, active: true, sort_order: 100 + PROFILES.length}); pcur = slug; await loadSort(); toast("Profile created"); } catch (e) { toast("Create failed: " + (e.message || e)); }
  };
}
function copySession() {
  const rows = []; Object.entries(ASSIGN).forEach(([ak, m]) => { const [run, key] = splitAk(ak); const e = POOL.find((x) => akey(x) === ak); Object.values(m).forEach((x) => rows.push({run, key, profile: x.profile, source: x.source || "manual", note: x.note || null, updated_at: x.updated_at, title: e?.title, category: e?.category, venue: e?.venue, neighborhood: e?.neighborhood, price_text: e?.price_text, starts_at: e?.starts_at, highlight: !!e?.highlight, url: e?.url, source_excerpt: (e?.source_excerpt || "").slice(0, 300)})); });
  const unsorted = POOL.filter((e) => !isSorted(e)).map((e) => ({run: e.run, key: e.key, title: e.title, category: e.category}));
  copyText(JSON.stringify({session: new Date().toISOString().slice(0, 10), profiles: PROFILES.map((p) => ({slug: p.slug, name: p.name, persona: p.persona})), assignments: rows, unsorted_count: unsorted.length}, null, 1), "Session copied; paste it to Claude to update the charters");
}

// ---------- boot
async function loadRun(run) {
  current = null; selected = new Set();
  setSync("Loading " + run + "…");
  try { decisions = await withTimeout(provider.load(run), 20000, "Loading run"); }
  catch (e) { EVENTS = []; byKey = {}; decisions = {}; fillSelects(); render(); setSync("Couldn't load: " + (e.message || e)); return; }
  byKey = Object.fromEntries(EVENTS.map((e) => [e.key, e]));
  try { selected = new Set(JSON.parse(localStorage.getItem(LS_SEL()) || "[]").filter((k) => byKey[k])); } catch {}
  try { if (tab === "events" && location.hash.slice(1) !== run) history.replaceState(null, "", "#" + run); } catch {}
  fillSelects(); render(); setSync(provider.name === "supabase" ? "Synced" : "");
}
const TABS = ["events", "sort", "sources", "runs"];
let tab = "events";
function showTab(name) {
  tab = TABS.includes(name) ? name : "events";
  document.querySelectorAll(".nav a[data-tab]").forEach((a) => { if (a.dataset.tab === tab) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  $("#app").hidden = tab !== "events"; $("#panel-sort").hidden = tab !== "sort"; $("#panel-sources").hidden = tab !== "sources"; $("#panel-runs").hidden = tab !== "runs";
  if (tab === "sources") renderSources(); if (tab === "runs") renderRuns(); if (tab === "sort" && !sortLoaded) loadSort();
}
function showApp(runs) {
  $("#gate").hidden = true;
  const h = (() => { try { return location.hash.slice(1); } catch { return ""; } })();
  showTab(TABS.includes(h) ? h : "events");
  const sel = $("#runsel");
  if (sel) sel.innerHTML = runs.map((r) => `<option value="${esc(r.run)}">${esc(r.run)}${r.umbrella ? " · " + esc(r.umbrella) : ""}</option>`).join("");
  const wanted = (() => { try { return location.hash.slice(1); } catch { return ""; } })();
  const run = runs.find((r) => r.run === wanted)?.run || (runs[0] && runs[0].run);
  if (sel && run) sel.value = run;
  if (run) loadRun(run); else render();
}
function showGate(html) { $("#app").hidden = true; const g = $("#gate"); g.hidden = false; g.innerHTML = html; }
const stage = (t) => { const g = $("#gate"); if (!g.hidden) g.innerHTML = `<div class="gate-card"><p>${esc(t)}</p></div>`; };
const withTimeout = (p, ms, what) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(what + " timed out after " + ms / 1000 + "s")), ms))]);

async function boot() {
  if (location.protocol === "http:" && location.hostname !== "localhost") { location.replace("https://" + location.host + location.pathname + location.hash); return; }
  wire();
  if (window.SCOUT_INLINE) { provider = inlineProvider(window.SCOUT_INLINE); $("#rf-start").disabled = true; $("#as-add").disabled = true; showApp(await provider.runs()); return; }
  const cfg = window.SCOUT_CONFIG || {};
  if (!cfg.supabaseUrl || !cfg.supabaseAnonKey || !window.supabase) { showGate(`<div class="gate-card"><h2 class="title">Eventrrr Scout</h2><p>Not configured yet: site/config.js needs the Supabase URL and anon key.</p></div>`); return; }
  // No cross-tab Web Lock: a suspended mobile tab can hold it forever and getSession() never resolves.
  const sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, {auth: {lock: (_name, _timeout, fn) => fn()}});
  const signIn = () => sb.auth.signInWithOAuth({provider: "google", options: {redirectTo: "https://scout.eventrrr.com/"}});
  const gateSignIn = () => { showGate(`<div class="gate-card"><h2 class="title">Eventrrr Scout</h2><p>Event review for curated calendars. Sign in to continue.</p><button class="btn btn-secondary btn-google" id="signin">${GOOGLE} Continue with Google</button></div>`); $("#signin").onclick = signIn; };
  stage("Checking session…");
  let session = null;
  try { ({data: {session}} = await withTimeout(sb.auth.getSession(), 12000, "Session check")); }
  catch (e) { showGate(`<div class="gate-card"><h2 class="title">Slow to load</h2><p>${esc(e.message || e)}. Close other Scout tabs and retry.</p><button class="btn btn-secondary" id="retry">Retry</button> <button class="link-btn" id="signout">Sign out</button></div>`); $("#retry").onclick = () => location.reload(); $("#signout").onclick = async () => { try { localStorage.clear(); } catch {} location.reload(); }; return; }
  if (!session) { gateSignIn(); sb.auth.onAuthStateChange((_, s) => { if (s) location.reload(); }); return; }
  const user = session.user;
  stage("Checking access for " + user.email + "…");
  const {data: rev, error: revErr} = await withTimeout(sb.from("scout_reviewers").select("email").limit(1), 15000, "Access check").catch((e) => ({data: null, error: e}));
  if (revErr) { showGate(`<div class="gate-card"><h2 class="title">Access check failed</h2><p>${esc(revErr.message)}</p><button class="btn btn-secondary" id="retry">Retry</button></div>`); $("#retry").onclick = () => location.reload(); return; }
  if (!rev || !rev.length) {
    showGate(`<div class="gate-card"><h2 class="title">Not on the list</h2><p>${esc(user.email)} isn't a reviewer for this scout.</p><button class="btn btn-secondary" id="signout">Sign out</button></div>`);
    $("#signout").onclick = async () => { await sb.auth.signOut(); location.reload(); }; return;
  }
  provider = supabaseProvider(sb, user, cfg);
  $("#rf-start").onclick = () => startSweep(sb);
  $("#as-add").onclick = () => addSource(sb, false); $("#as-force").onclick = () => addSource(sb, true);
  const acct = $("#account");
  if (acct) { acct.innerHTML = `${user.user_metadata?.avatar_url ? `<img class="avatar" src="${esc(user.user_metadata.avatar_url)}" alt="">` : ""}<button class="btn btn-secondary" id="signout">Sign out</button>`; $("#signout").onclick = async () => { await sb.auth.signOut(); location.reload(); }; }
  let runs = [];
  stage("Loading runs…");
  try { runs = await withTimeout(provider.runs(), 15000, "Loading runs"); } catch (e) { showGate(`<div class="gate-card"><h2 class="title">Couldn't load runs</h2><p>${esc(e.message || e)}</p><button class="btn btn-secondary" id="retry">Retry</button></div>`); $("#retry").onclick = () => location.reload(); return; }
  showApp(runs);
}
boot();
})();

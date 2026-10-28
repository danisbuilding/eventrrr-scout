// scout-trigger v2: reviewer-only actions for scout.eventrrr.com.
//   {action:"sweep", ...}       → GitHub repository_dispatch "sweep" on danisbuilding/eventrrr-scout
//   {action:"add_source", ...}  → verify a website / Instagram handle, append it to sources.yaml, commit
// Secrets: GITHUB_SCOUT_TOKEN (fine-grained PAT; Contents: read+write on that repo).
import { createClient } from "npm:@supabase/supabase-js@2";
import YAML from "npm:yaml@2.5.1";

const REPO = "danisbuilding/eventrrr-scout";
const SITE = "https://scout.eventrrr.com";
const cors = {
  "Access-Control-Allow-Origin": SITE,
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
const gh = (path: string, init: RequestInit = {}) =>
  fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${Deno.env.get("GITHUB_SCOUT_TOKEN")}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36";

async function sweep(body: Record<string, string>, email: string) {
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  const today = new Date().toISOString().slice(0, 10);
  const window_from = iso.test(body.window_from ?? "") ? body.window_from : today;
  const window_to = iso.test(body.window_to ?? "") ? body.window_to : new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10);
  const umbrella = (body.umbrella ?? "").toString().slice(0, 80);
  const ig_tier = ["1", "2", "all", "none"].includes(body.ig_tier) ? body.ig_tier : "all";
  const scouts = ["both", "openai", "gemini", "none"].includes(body.scouts) ? body.scouts : "none";
  const slug = umbrella ? "-" + umbrella.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") : "";
  const run = today + slug;
  const r = await gh("/dispatches", { method: "POST", body: JSON.stringify({ event_type: "sweep", client_payload: { run, window_from, window_to, umbrella, ig_tier, scouts, by: email } }) });
  if (r.status !== 204) return json(502, { error: `GitHub said ${r.status}: ${(await r.text()).slice(0, 200)}` });
  return json(200, { run, window_from, window_to });
}

async function verifySite(url: string): Promise<{ ok: boolean; title?: string; error?: string; warn?: string }> {
  try {
    const r = await fetch(url, { headers: { "User-Agent": UA, Accept: "text/html" }, redirect: "follow", signal: AbortSignal.timeout(12000) });
    if (r.status === 404 || r.status === 410) return { ok: false, error: "That page doesn't exist (HTTP 404)." };
    if (r.status >= 500) return { ok: false, error: `The site is down right now (HTTP ${r.status}). Try again later.` };
    const html = (await r.text()).slice(0, 200000);
    const title = (html.match(/<title[^>]*>([^<]{1,120})/i)?.[1] ?? "").trim();
    if (r.status === 403 || r.status === 429) return { ok: true, title, warn: "The site blocks automated visitors, so sweeps may get little from it. Added anyway." };
    if (!r.ok) return { ok: false, error: `The site answered HTTP ${r.status}.` };
    if (!/<html|<body|<div/i.test(html)) return { ok: false, error: "That URL doesn't return a web page (maybe a file or an API)." };
    return { ok: true, title };
  } catch (e) {
    return { ok: false, error: /timeout|aborted/i.test(String(e)) ? "The site didn't respond within 12 seconds." : "Couldn't reach that address. Check the spelling." };
  }
}

async function verifyInstagram(handle: string): Promise<{ ok: boolean; error?: string; warn?: string }> {
  try {
    const r = await fetch(`https://www.instagram.com/${handle}/`, { headers: { "User-Agent": UA, Accept: "text/html" }, redirect: "manual", signal: AbortSignal.timeout(12000) });
    if (r.status === 404) return { ok: false, error: `Instagram says @${handle} doesn't exist.` };
    if (r.status === 200) {
      const html = (await r.text()).slice(0, 300000);
      if (/"Page Not Found"|Sorry, this page isn't available/i.test(html)) return { ok: false, error: `Instagram says @${handle} doesn't exist.` };
      return { ok: true };
    }
    return { ok: true, warn: "Instagram wouldn't confirm the handle (it blocks automated checks). Added anyway; the next sweep will tell." };
  } catch {
    return { ok: true, warn: "Couldn't reach Instagram to verify. Added anyway; the next sweep will tell." };
  }
}

async function addSource(body: Record<string, string>, email: string) {
  const kind = body.kind === "instagram" ? "instagram" : body.kind === "web" ? "web" : null;
  if (!kind) return json(400, { error: "Pick Website or Instagram." });
  const force = body.force === "1";
  let entry: Record<string, unknown>, listKey: string, matchKey: string, matchVal: string, label: string, warn: string | undefined;

  if (kind === "web") {
    let url = (body.value ?? "").trim();
    if (!/^https?:\/\//i.test(url)) url = "https://" + url;
    let u: URL;
    try { u = new URL(url); if (!u.hostname.includes(".")) throw 0; } catch { return json(400, { error: "That doesn't look like a web address. Example: https://local.mx/" }); }
    if (/instagram\.com/i.test(u.hostname)) return json(400, { error: "That's an Instagram link. Choose Instagram and enter the handle instead." });
    const v = await verifySite(u.toString());
    if (!v.ok && !force) return json(422, { error: v.error, retryable: false });
    warn = v.warn;
    const name = (body.name ?? "").trim() || v.title?.split(/[|–\-·]/)[0].trim() || u.hostname.replace(/^www\./, "");
    entry = { name: name.slice(0, 60), url: u.toString(), tier: 2, enabled: true, added_by: email, added_at: new Date().toISOString().slice(0, 10) };
    listKey = "sites_tier2"; matchKey = "url"; matchVal = u.toString().replace(/\/$/, "").toLowerCase(); label = name;
  } else {
    const handle = (body.value ?? "").trim().replace(/^@/, "").replace(/^https?:\/\/(www\.)?instagram\.com\//i, "").replace(/[\/?#].*$/, "").toLowerCase();
    if (!/^[a-z0-9._]{1,30}$/.test(handle)) return json(400, { error: "That doesn't look like an Instagram handle. Example: @cdmxsecreta" });
    const v = await verifyInstagram(handle);
    if (!v.ok && !force) return json(422, { error: v.error });
    warn = v.warn;
    entry = { handle, tier: 2, enabled: true, added_by: email, added_at: new Date().toISOString().slice(0, 10) };
    listKey = "instagram_tier2"; matchKey = "handle"; matchVal = handle; label = "@" + handle;
  }

  // read, append, commit
  const cur = await gh("/contents/sources.yaml?ref=main");
  if (!cur.ok) return json(502, { error: `Couldn't read sources.yaml (GitHub ${cur.status}).` });
  const meta = await cur.json();
  const text = new TextDecoder().decode(Uint8Array.from(atob(meta.content.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
  const doc = YAML.parse(text) as Record<string, any>;
  const all = [...(doc.sites ?? []), ...(doc.sites_tier2 ?? []), ...(doc.instagram ?? []), ...(doc.instagram_tier2 ?? [])];
  const dup = all.find((x) => String(x[matchKey] ?? "").replace(/\/$/, "").toLowerCase() === matchVal);
  if (dup) return json(409, { error: `${label} is already in the list${dup.enabled === false ? " (currently off; enable it in sources.yaml)" : ""}.` });
  doc[listKey] = [...(doc[listKey] ?? []), entry];
  const out = YAML.stringify(doc, { lineWidth: 0 });
  const put = await gh("/contents/sources.yaml", {
    method: "PUT",
    body: JSON.stringify({ message: `sources: add ${label} (${kind}) via scout.eventrrr.com`, content: btoa(unescape(encodeURIComponent(out))), sha: meta.sha, branch: "main" }),
  });
  if (!put.ok) return json(502, { error: `Couldn't save (GitHub ${put.status}). Try again.` });
  return json(200, { added: label, kind, warn });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json(405, { error: "POST only" });
  const auth = req.headers.get("Authorization") ?? "";
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth } } });
  const { data: { user }, error: uerr } = await supabase.auth.getUser();
  if (uerr || !user) return json(401, { error: "Sign in first" });
  const { data: ok, error: rerr } = await supabase.rpc("scout_is_reviewer");
  if (rerr || !ok) return json(403, { error: "Not a reviewer" });
  let body: Record<string, string> = {};
  try { body = await req.json(); } catch { /* empty */ }
  if (body.action === "add_source") return addSource(body, user.email ?? "");
  return sweep(body, user.email ?? "");
});

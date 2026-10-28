// scout-trigger: lets an allow-listed reviewer start a sweep from scout.eventrrr.com.
// Verifies the caller's Supabase session, checks scout_is_reviewer(), then fires a
// GitHub repository_dispatch (event "sweep") on danisbuilding/eventrrr-scout.
// Secrets: GITHUB_SCOUT_TOKEN (fine-grained PAT, Contents: read+write on that repo).
import { createClient } from "npm:@supabase/supabase-js@2";

const REPO = "danisbuilding/eventrrr-scout";
const cors = {
  "Access-Control-Allow-Origin": "https://scout.eventrrr.com",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json(405, { error: "POST only" });

  const auth = req.headers.get("Authorization") ?? "";
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: auth } },
  });
  const { data: { user }, error: uerr } = await supabase.auth.getUser();
  if (uerr || !user) return json(401, { error: "Sign in first" });
  const { data: ok, error: rerr } = await supabase.rpc("scout_is_reviewer");
  if (rerr || !ok) return json(403, { error: "Not a reviewer" });

  let body: Record<string, string> = {};
  try { body = await req.json(); } catch { /* empty */ }
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  const today = new Date().toISOString().slice(0, 10);
  const window_from = iso.test(body.window_from ?? "") ? body.window_from : today;
  const window_to = iso.test(body.window_to ?? "") ? body.window_to : new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10);
  const umbrella = (body.umbrella ?? "").toString().slice(0, 80);
  const ig_tier = ["1", "2", "all", "none"].includes(body.ig_tier) ? body.ig_tier : "all";
  const scouts = ["both", "openai", "gemini", "none"].includes(body.scouts) ? body.scouts : "both";
  const slug = umbrella ? "-" + umbrella.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") : "";
  const run = today + slug;

  const gh = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${Deno.env.get("GITHUB_SCOUT_TOKEN")}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ event_type: "sweep", client_payload: { run, window_from, window_to, umbrella, ig_tier, scouts, by: user.email } }),
  });
  if (gh.status !== 204) return json(502, { error: `GitHub said ${gh.status}: ${(await gh.text()).slice(0, 200)}` });
  return json(200, { run, window_from, window_to });
});

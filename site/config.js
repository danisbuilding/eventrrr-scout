// Public settings. On deploy, pages.yml rewrites this file from the SCOUT_SUPABASE_URL / SCOUT_SUPABASE_ANON_KEY
// secrets with schema "iq" when the repo variable SCOUT_IQ_LIVE is "true" (the Scout IQ cutover); until then the
// committed values below (Eventrrr's project, scout_* tables) are what ships.
// The anon key is safe to publish (it ships in Eventrrr's own frontend); RLS does the protecting.
window.SCOUT_CONFIG = {
  supabaseUrl: "https://psqedmbyopememsqrynk.supabase.co",
  supabaseAnonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBzcWVkbWJ5b3BlbWVtc3FyeW5rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA4MDIwNjAsImV4cCI6MjEwNjM3ODA2MH0.rKZu46rNCfo3gNaSKJFFrKZbV7y0-Z7WKX_gnsN-sME",
  schema: "legacy",  // "legacy" = scout_* tables in Eventrrr's project; "iq" = Scout IQ (supabase/scout_iq*.sql)
  // where runs/index.json and runs/<run>/events.json are read from (public repo)
  eventsBase: "https://raw.githubusercontent.com/danisbuilding/eventrrr-scout/main",
};

// Public settings. The anon key is safe to publish (it ships in Eventrrr's own frontend); RLS does the protecting.
window.SCOUT_CONFIG = {
  supabaseUrl: "https://psqedmbyopememsqrynk.supabase.co",
  supabaseAnonKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBzcWVkbWJ5b3BlbWVtc3FyeW5rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA4MDIwNjAsImV4cCI6MjEwNjM3ODA2MH0.rKZu46rNCfo3gNaSKJFFrKZbV7y0-Z7WKX_gnsN-sME",
  // where runs/index.json and runs/<run>/events.json are read from (public repo)
  eventsBase: "https://raw.githubusercontent.com/danisbuilding/eventrrr-scout/main",
};

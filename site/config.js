// Public settings. The anon key is safe to publish; RLS does the protecting.
window.SCOUT_CONFIG = {
  supabaseUrl: "",
  supabaseAnonKey: "",
  // where runs/index.json and runs/<run>/events.json are read from (public repo)
  eventsBase: "https://raw.githubusercontent.com/danisbuilding/eventrrr-scout/main",
};

# web / search adapter

For each `sites[]` entry with `enabled: true`:
1. Scrape the homepage (Firecrawl, markdown). Collect links whose text or URL suggests an agenda/events/cartelera/qué-hacer page.
2. Scrape up to 5 of those listing pages. For a site that paginates by date, stop once pages fall outside the window.
3. Emit one RawItem per listing page (`text` = page markdown, `links` = all event links found, `source_url` = page URL), id `web:<site>:<sha1(url)[:12]>`.
4. If a listing is thin (titles only), scrape up to 20 individual event pages and emit each as its own RawItem.

For each umbrella `search_terms[]` plus a generic set ("eventos CDMX esta semana", "qué hacer en CDMX fin de semana", one per category in Spanish):
- Web search, take top ~8 results per term, scrape the ones that are listings. id `search:<term-slug>:<sha1(url)[:12]>`.

Keep `text` under ~12k chars per item; chunk long pages.

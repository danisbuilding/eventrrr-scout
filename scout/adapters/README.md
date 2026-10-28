# Adapters

Every source type has one doc here saying how its raw items are produced. All of
them emit `schema/raw_item.json` lines into `inbox/<run>/<source>.jsonl`.

| type | who runs it | doc |
|---|---|---|
| web | Claude (web search + Firecrawl scrape) | web.md |
| instagram | Claude via Apify MCP on the Mac (`apify/instagram-scraper`) | instagram.md |
| llm_scout | `scouts/run_scouts.py` on the Mac | ../../scouts/ |
| search | Claude web search on umbrella `search_terms` | web.md |
| whatsapp | v2 — Instinct / native export | whatsapp.md |
| newsletter | v2 — archive URL or forwarded email | web.md |

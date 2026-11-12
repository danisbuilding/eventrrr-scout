# Handover: building Eventrrr Scout

The build handover lives as a Claude doc (single source of truth; the repo copy was retired on 2026-11-02):
https://claude.ai/artifact/Sszqv2M5xCN1CjZNx6CBmw

Read it with the Artifact/Docs tools in a Claude chat. Short version: Start sweep → `scout-trigger` edge
function → `pipeline.yml` (Apify IG, web sweep, gpt-5-mini extract, normalize, score, publish); site in
`site/`; Supabase via Bolt prompts; secrets only in GitHub Actions and the edge function.

Since 2026-11-11: nightly `accuracy.yml` (tagging via `scout/enrich.py`, then the source re-read in `scout/accuracy.py`),
a weekly scheduled sweep, and on 2026-11-12 the data-quality rules and English text described in README
"Data quality and English" and in the Scout IQ Database Spec's "Since v1" section.

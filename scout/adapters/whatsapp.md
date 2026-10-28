# whatsapp adapter (v2, not built)

Groups are private, so there is no scraping. Input is an export:
- Instinct export (format TBD — DP to provide a sample file), or
- native WhatsApp "Export chat" .txt (+ media zip).

Each message becomes a RawItem: id `whatsapp:<group-slug>:<sha1(ts+sender+text)[:12]>`,
author = sender display name, posted_at = message time, text = body, media = attached
image filenames (Claude reads flyers the same way as Instagram).

Privacy: group names and sender names stay in `inbox/` only; nothing from WhatsApp is
published in the dashboard except the event itself and a `source_count`.

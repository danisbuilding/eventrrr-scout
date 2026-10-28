# instagram adapter (Apify)

Actor: `apify/instagram-scraper` (pay per result, ~$0.003/post on the free tier).

Input per sweep:
```json
{"resultsType": "posts",
 "directUrls": ["https://www.instagram.com/<handle>/", ...],
 "resultsLimit": <defaults.ig_posts_per_account>,
 "onlyPostsNewerThan": "<defaults.ig_newer_than>",
 "addParentData": true}
```
Run `scout/instagram_apify.py` (the `sweep` workflow does this with `APIFY_TOKEN`); it calls the actor, waits, and writes RawItems.

Map each post to a RawItem:
- id `instagram:<ownerUsername>:<shortCode>`
- source_url `https://www.instagram.com/p/<shortCode>/`
- author ownerUsername, posted_at timestamp, text caption
- links: any URLs in the caption + the profile's external URL
- media: displayUrl (and child images for carousels)
- meta: likesCount, commentsCount, hashtags, type

Flyers: when a caption is thin (< 80 chars) but there is an image, Claude reads the
image and fills `ocr_text`. Cap this at ~40 images per sweep.

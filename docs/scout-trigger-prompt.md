# Bolt prompt: deploy the scout-trigger edge function

Prerequisite (DP, in GitHub): create a fine-grained personal access token at
https://github.com/settings/personal-access-tokens/new — Repository access: only
`danisbuilding/eventrrr-scout`; Permissions → Repository → Contents: **Read and write**
(repository_dispatch and sources.yaml commits) and Actions: **Read and write** (Stop sweep, v3). Expiration: 1 year. Copy the token.

Then in Bolt:

```
Deploy a Supabase edge function named `scout-trigger` with exactly the code in the file I'm pasting below. Don't change the Eventrrr app itself.

Then set an edge-function secret named GITHUB_SCOUT_TOKEN with the value I'll give you separately (a GitHub token). SUPABASE_URL and SUPABASE_ANON_KEY are already available to edge functions by default.

The function: verifies the caller's Supabase session, calls the existing `scout_is_reviewer()` SQL function, and if true sends a GitHub repository_dispatch to danisbuilding/eventrrr-scout. CORS is limited to https://scout.eventrrr.com.

After deploying, tell me the function's URL and confirm the secret is set. Don't print the token.

<paste supabase/functions/scout-trigger/index.ts here>
```

## v3 (2026-11-02): Stop sweep

GitHub first: edit the token at https://github.com/settings/personal-access-tokens and add Permissions →
Repository → Actions: **Read and write**. Then in Bolt:

```
Redeploy the Supabase edge function `scout-trigger` with exactly the code I'm pasting below (v3: adds a "cancel" action that cancels a GitHub Actions run). Keep the existing GITHUB_SCOUT_TOKEN secret; don't change anything else in the project. Confirm when it's deployed.

<paste supabase/functions/scout-trigger/index.ts here>
```

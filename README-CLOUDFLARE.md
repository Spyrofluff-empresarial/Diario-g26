Deploying the site and anonymous publish Worker (overview)

1) Prerequisites
- Install `wrangler` (Cloudflare CLI). On Windows PowerShell:

```powershell
npm install -g wrangler
```

- Have a Cloudflare account and create a Workers KV namespace for submissions and for the index.

2) Prepare `wrangler.toml`
- Open `wrangler.toml` and replace `YOUR_ACCOUNT_ID` and the KV ids with the ones you create.

3) Create KV namespaces
- Use wrangler to create KV namespaces or create them in the Cloudflare dashboard:

```powershell
wrangler kv:namespace create "SUBMISSIONS" --preview --binding SUBMISSIONS
wrangler kv:namespace create "ENTRIES_INDEX" --preview --binding ENTRIES_INDEX
```

The command output will show the namespace IDs. Put them into `wrangler.toml`.

4) Local dev
- Run the worker locally to test endpoints:

```powershell
wrangler dev worker/index.js --env=dev
```

- Or to serve the static `sitio` folder you can use `wrangler pages dev` (Pages) and combine with Functions or route the API to the Worker.

5) Deploy
- Publish the Worker:

```powershell
wrangler publish
```

- For a full Pages + Functions setup, follow Cloudflare Pages docs: deploy the static `sitio` folder to Pages and map API calls (e.g., `/api/*`) to your Worker.

6) Notes on privacy and safety
- The worker stores text anonymously in KV; it does not capture IP addresses or other metadata.
- Moderation: consider adding server-side moderation or a manual review step before showing posts publicly.
- Avoid hosting illegal content; implement reporting/removal procedures.

If you want, I can:
- Add a simple entries list view that fetches `/api/entries` and renders recent posts on the index page.
- Add basic moderation (hold posts for manual approval) by adding a `published` flag and admin endpoint.

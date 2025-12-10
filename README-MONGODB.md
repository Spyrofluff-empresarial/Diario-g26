Deploying the site and anonymous publish Worker (MongoDB Data API)

1) Prerequisites
- Install `wrangler` (Cloudflare CLI). On Windows PowerShell:

```powershell
npm install -g wrangler
```

- A Cloudflare account and a MongoDB Atlas project. We'll use the MongoDB Data API (HTTP) so the Worker/Pages Function can talk to MongoDB without a native driver.

2) Enable MongoDB Data API
- In MongoDB Atlas, go to "Data API" (under App Services) and enable it for your App.
- Create an API Key (copy the key value; treat it as a secret).
- Note the Data API base URL, it looks like: `https://data.mongodb-api.com/app/<app-id>/endpoint/data/v1`

3) Configure `wrangler.toml` and secrets
- Open `wrangler.toml` and set your `account_id`.
- Configure the following values (we recommend storing the API key as a secret):

  - `MONGODB_DATA_API_URL` = `https://data.mongodb-api.com/app/<app-id>/endpoint/data/v1`
  - `MONGODB_DATA_SOURCE` = `<YourClusterName>` (e.g. Cluster0)
  - `MONGODB_DATABASE` = `<DatabaseName>`
  - `MONGODB_COLLECTION` = `<CollectionName>`

- Store the Data API key as a secret:

```powershell
wrangler secret put MONGODB_DATA_API_KEY
```

4) Local dev and testing
- To run the Worker locally and test endpoints:

```powershell
wrangler dev worker/index.js --local
```

- If you deploy static assets to Cloudflare Pages, you can route `/api/*` to this Worker or use Pages Functions to proxy calls to the Data API.

5) Deploy
- Publish the Worker:

```powershell
wrangler publish
```

6) Moderation, privacy and safety
- The Worker stores the submitted text in MongoDB via the Data API. The current implementation intentionally does not collect IP addresses.
- The Worker performs minimal sanitization (removes <script> tags and some handlers). For production, add robust sanitization and moderation (automatic or human).
- Consider adding a `published` flag and an admin-only approval flow before entries become public.

7) Next tasks I can do for you
- Add a client-side list on `index.html` that fetches `/api/entries` and renders recent posts.
- Add moderation: store `published:false` on submit and create an admin endpoint to approve posts.
- Convert the Worker to a Pages Function if you prefer deploying the static site to Pages and keeping the API as Functions.

If you want, I can now implement the client-side list rendering and a simple moderation flow (hold posts for approval).

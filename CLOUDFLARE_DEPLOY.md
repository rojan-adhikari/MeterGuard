# Host MeterGuard on Cloudflare Workers

This ZIP is configured for Cloudflare Workers and D1. It deploys the same dashboard/API code as the reference live app to **your own** `*.workers.dev` URL. Cloudflare credentials and a new D1 database are required. The reference ChatGPT Site's URL and database are separate.

## 1. Extract and install on your Mac

Install Node.js 22.13+ and npm, then in Terminal:

```bash
unzip MeterGuard_Cloudflare_Ready.zip
cd MeterGuard
npm ci
npx wrangler login
```

Wrangler opens a browser to authorize your Cloudflare account.

## 2. Create the database

```bash
npx wrangler d1 create meterguard-db
```

Copy the `database_id` UUID printed by Wrangler. Open `wrangler.json` and replace only `00000000-0000-4000-8000-000000000000` with that UUID. Keep the binding name `DB`. The Worker uses this binding for the review queue.

## 3. Build and create the production table

```bash
npm run build
npx wrangler d1 execute meterguard-db --remote --file=drizzle/0000_spicy_next_avengers.sql
```

Confirm the remote database operation if prompted. Run the SQL file only once for a new database. If you are updating an existing deployment with the `reviews` table already present, skip it. The build copies `frontend/` and `backend/` into the framework's expected paths and writes `dist/server/wrangler.json`.

## 4. Deploy

```bash
npx wrangler deploy --config dist/server/wrangler.json
```

Wrangler prints the new `https://meterguard.<your-subdomain>.workers.dev` URL. Open it and try **Analyze account → Upload CSV** with `frontend/assets/sgcc_real_sample.csv`. The first deployment has an empty review queue until you analyze an account.

For later edits, change files under `frontend/` or `backend/`, then run `npm run build` and the deploy command again. Run a new D1 migration only when the schema changes.

## If a command fails

- **D1 database not found / invalid database ID:** check the UUID in `wrangler.json`, then rebuild; the generated `dist/server/wrangler.json` must contain the same UUID.
- **No such table: reviews:** run the remote SQL command in step 3 against the same `meterguard-db` that the Worker binds.
- **Permission error:** run `npx wrangler login` again and select the Cloudflare account that owns the database.
- **Upload fails:** use the SGCC sample with the Upload CSV control or an hourly CSV with `account_id,timestamp,kwh`. File size is limited to 12 MB.

The app has no user authentication. Before putting private customer data online, add access control and audit logging.

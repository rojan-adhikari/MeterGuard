# MeterGuard — judge-friendly source

**Project:** Smart Meter-Based Electricity Fraud Risk Prediction  
**Reference app:** https://gridsense-meter-risk.rojan-adhikari.chatgpt.site

MeterGuard analyzes electricity-consumption histories and ranks accounts as Normal, Moderate, or High Risk. The dashboard shows trends and baseline changes, while the review queue records investigator status and notes. A flagged account still needs investigation and field evidence; a model score does not prove fraud.

## Read the code in this order

| Step | Folder/file | Explain to judges |
| --- | --- | --- |
| 1 | `frontend/ui.html` | Dashboard, CSV upload, manual entry, review queue, model-performance views. |
| 2 | `frontend/assets/styles.css` | Responsive layout, status colors, forms, tables, and charts. |
| 3 | `frontend/assets/app.js` | UI events, API calls, charts, validation, and queue controls. |
| 4 | `backend/api/analyze/` | Three prediction endpoints: auto-detected CSV, daily CSV, and manual input. |
| 5 | `backend/lib/data.ts`, `backend/lib/api.ts` | Hourly CSV validation, feature extraction, and three-class risk scoring. |
| 6 | `backend/lib/sgcc.ts` | Historical SGCC daily features, trained forest score, risk category, and patterns. |
| 7 | `backend/api/reviews/`, `backend/db/schema.ts` | Persistent review queue, search, status, and notes in Cloudflare D1. |
| 8 | `training/train_sgcc.py`, `training/train.py` | Reproducible model training and evaluation. |

See [JUDGES_WALKTHROUGH.md](JUDGES_WALKTHROUGH.md) for the explanation script and request flow.

The `frontend/`, `backend/`, and `training/` folders are the canonical source. Next.js/Vinext expects `public/`, `app/api/`, `lib/`, `db/`, and `drizzle/` at the root. `scripts/sync-source.mjs` generates those paths from the organized folders before `dev` and `build`. **Edit the organized folders**, then run `npm run sync:source` or rebuild; do not edit generated copies.

## Run locally (same UI and API as the live app)

Install Node.js 22.13+ and npm. On macOS or Linux, run from this folder:

```bash
npm ci
npm run build
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_spicy_next_avengers.sql
npm run start
```

Open the local address printed by Wrangler. The D1 migration is needed once per fresh local database. For code changes, use `npm run dev`; `predev` synchronizes the organized source. The local review database is separate from the hosted one. If the local database already has the table, skip the migration command.

## Input formats and sample files

- **Real historical daily CSV:** `CONS_NO`, optional `FLAG`, and date columns such as `2014/1/1`; use `frontend/assets/sgcc_real_sample.csv` (three actual historical account traces). The full public SGCC archive is at https://github.com/henryRDlab/ElectricityTheftDetection (download all split parts: `data.z01`, `data.z02`, `data.zip`).
- **Hourly CSV:** `account_id,timestamp,kwh`; use `frontend/assets/sample_readings.csv` (synthetic development sample). At least 72 readings per account.
- **Manual:** account ID, first timestamp, minutes between readings, and at least 72 kWh values.

The normal Upload CSV button automatically selects the daily or hourly endpoint based on the first column. The daily sample should be uploaded through this button or through the Real daily data tab.

## Models and measured limits

The hourly three-class model was trained on **synthetic development labels**; its measured metrics are in `backend/lib/evaluation.json`. They do not establish utility performance. The historical SGCC model was selected from Logistic Regression, Decision Tree, and Random Forest using validation average precision. It uses 42,372 labeled accounts split by account into training, validation, and held-out test sets. At the hosted high-priority threshold of 0.70, test precision was **0.5163** and recall **0.1314** against the published account labels (`backend/lib/sgcc-evaluation.json`). This is a historical holdout, not prospective field validation.

The hosted API loads `backend/lib/model.json` and `backend/lib/sgcc-forest.json`. `training/models/` contains saved Python artifacts and evaluation files. Python retraining alone does not update the deployed TypeScript representation: re-export the fitted model into the compatible format, verify inference parity, then deploy.

## Retraining

```bash
cd training
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python train_sgcc.py --input /path/to/extracted/data.csv --output models
python predict_sgcc.py --input data/sgcc_real_sample.csv --model models/sgcc_model.joblib --output sgcc_predictions.csv
```

For the hourly model, supply a readings CSV (`account_id,timestamp,kwh`) and verified account labels using `python train.py --readings /path/readings.csv --labels /path/labels.csv --output models`. The SGCC `FLAG` is a published dataset label and does not include field evidence for new accounts.

## API routes

- `POST /api/analyze/upload`: multipart CSV; auto-detect format.
- `POST /api/analyze/daily`: multipart SGCC daily CSV.
- `POST /api/analyze/manual`: JSON manual hourly readings.
- `GET /api/summary`, `/api/model`, `/api/model/sgcc`, `/api/reviews`.
- `PATCH /api/reviews/:account_id`: review status and notes.

This is a research/demo implementation without user authentication. A provider would need access control, auditing, and data governance before using private customer records.

## Cloudflare Workers deployment

Read [CLOUDFLARE_DEPLOY.md](CLOUDFLARE_DEPLOY.md) before deployment. Create a D1 database, replace the placeholder ID in `wrangler.json`, build, apply `drizzle/0000_spicy_next_avengers.sql` remotely, then deploy the Worker.

# MeterGuard

**Smart Meter-Based Electricity Fraud Risk Prediction**

MeterGuard helps an electricity provider review smart-meter consumption. It scores account histories, shows Normal, Moderate, or High Risk, highlights usage patterns, and gives investigators a queue for statuses and notes. A flag is an investigation priority, not proof of electricity theft; confirmation needs field evidence.

**Live app:** https://gridsense-meter-risk.rojan-adhikari.chatgpt.site

## What is included

- Dashboard with account totals, risk distribution, recent results, and consumption trends.
- CSV upload, manual hourly entry, historical daily-data upload, and validation messages.
- Account-level score, chart, baseline comparison, and descriptive usage patterns.
- Review queue with search, filters, statuses, and investigator notes stored in Cloudflare D1.
- Model-performance page showing measured development and historical-dataset results.
- `training/` with reproducible Python training scripts and saved Python artifacts; `lib/` has the trained model representations used by the hosted API.

## Data and models

| Input | CSV format | Model used by hosted app |
| --- | --- | --- |
| Hourly readings or manual entry | `account_id,timestamp,kwh`; at least 72 readings per account | Three-class development model trained on synthetic labels (`lib/model.json`) |
| Historical daily readings | `CONS_NO`, optional `FLAG`, and date columns such as `2014/1/1`; at least 180 date columns | SGCC historical Random Forest (`lib/sgcc-forest.json`) |

The general **Upload CSV** control detects the format using the first column. `public/assets/sgcc_real_sample.csv` contains three historical accounts for a quick upload. `public/assets/sample_readings.csv` is a synthetic hourly example and must not be presented as real utility data. The daily dataset comes from the [public SGCC Electricity Theft Detection repository](https://github.com/henryRDlab/ElectricityTheftDetection), covering 42,372 accounts and 2014–2016 histories. Download its three archive parts (`data.z01`, `data.z02`, `data.zip`) there to reproduce full training.

The SGCC `FLAG` is a published account-level label. It does not provide the incident date or field evidence for a new prediction. The historical evaluation uses disjoint account splits (60% train, 20% validation, 20% untouched test), **not** a prospective time test. At the high-priority score threshold of 0.70, the held-out test precision is **0.5163** and recall **0.1314**. The model therefore misses many positive labels and must not be used as an automated fraud verdict. See `lib/sgcc-evaluation.json` and `training/models/sgcc_evaluation.json` for all measured metrics. Development-model metrics in `lib/evaluation.json` are measured on synthetic labels and do not establish performance on utility accounts.

## Run the dashboard locally

Requirements: Node.js 22.13+ and npm. The app uses Next.js/Vinext on Cloudflare Workers with D1 for reviews.

```bash
npm ci
npm run build
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_spicy_next_avengers.sql
npm run start
```

Open the local URL printed by Wrangler. Apply the D1 migration only once for a given local database. After source edits, rebuild with `npm run build`; `npm run dev` is available for development. The deployed Site uses a separate production D1 database, so your local review queue starts empty.

## Retrain the Python models

Create a Python 3.11+ environment, then install dependencies:

```bash
cd training
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Train the three SGCC candidate models and score the bundled real sample:

```bash
python train_sgcc.py --input /path/to/extracted/data.csv --output models
python predict_sgcc.py --input data/sgcc_real_sample.csv --model models/sgcc_model.joblib --output sgcc_predictions.csv
```

The SGCC trainer cleans negative/missing readings, extracts consumption, variability, zero-use, weekend, and baseline-change features, selects among Logistic Regression, Decision Tree, and Random Forest on validation average precision, and writes a held-out evaluation report. The saved Python model is in `training/models/sgcc_model.joblib`. The synthetic hourly training path is `python train.py --readings /path/to/hourly.csv --labels /path/to/labels.csv --output models`; see `training/train.py --help` for arguments.

**Deployment note:** the hosted Cloudflare API loads the serialized models in `lib/`, not Python `joblib`. Running the Python trainer updates the Python artifact only; deploy a new compatible model representation and verify the API before claiming the hosted model was retrained. Only load `joblib` files from trusted sources.

## API

- `POST /api/analyze/upload` — multipart `file`, auto-detects hourly or SGCC daily CSV.
- `POST /api/analyze/daily` — multipart SGCC daily CSV.
- `POST /api/analyze/manual` — JSON `account_id`, `start_timestamp`, `interval_minutes`, `kwh_values`.
- `GET /api/summary`, `/api/model`, `/api/model/sgcc`, `/api/reviews`.
- `PATCH /api/reviews/:account_id` — update status and notes.

This project is a research/demo application without user authentication. Add identity, access control, audit trails, and a data-governance process before handling private utility customer records.

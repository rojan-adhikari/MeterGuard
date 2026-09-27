# MeterGuard: code walkthrough for judges

## 60-second explanation

MeterGuard takes smart-meter consumption readings, validates the file, extracts account-level usage features, and applies a trained model. It shows an investigation priority as Normal, Moderate, or High Risk. Investigators can review trends, compare recent use with a baseline, and record status and notes. A flag prompts an investigation; it is not a fraud finding.

## Follow one CSV upload

1. **Interface:** `frontend/ui.html` renders Upload CSV. `frontend/assets/app.js` sends the selected file to `/api/analyze/upload` and shows loading, result, or validation error.
2. **Route:** `backend/api/analyze/upload/route.ts` checks the file and size. A `CONS_NO` first column takes the SGCC daily path; otherwise it uses hourly parsing.
3. **Features:** `backend/lib/sgcc.ts` extracts long-term and recent consumption, gaps, near-zero periods, variation, and baseline ratios. The hourly path uses `backend/lib/data.ts` and `backend/lib/api.ts`.
4. **Model:** The daily path scores the serialized Random Forest in `backend/lib/sgcc-forest.json`. Risk categories use score thresholds (`>=0.70` High, `>=0.20` Moderate). The hourly synthetic-development model uses `backend/lib/model.json`.
5. **Storage:** The API writes results to D1. `backend/api/reviews/` reads and updates review status and investigator notes.
6. **Display:** The dashboard and queue fetch API results; the account detail draws a consumption chart and lists descriptive patterns.

## Questions to be ready for

- **Is this real data?** The SGCC daily sample contains real historical consumption records with published account labels. The hourly sample and its training labels are synthetic. No live smart-meter feed is connected.
- **Does High Risk mean fraud?** No. It prioritizes review. Field inspection and evidence determine what actually happened.
- **How was the model evaluated?** The SGCC dataset uses disjoint accounts across training, validation, and held-out test sets. The test precision and recall at the high-priority threshold are 0.5163 and 0.1314, respectively; see `backend/lib/sgcc-evaluation.json`.
- **Can we retrain it?** `training/train_sgcc.py` compares three models and saves the selected fitted Python pipeline. Updating the hosted app also requires exporting a compatible TypeScript model representation and verifying parity.
- **Why a review queue?** A model score is actionable only when a person can inspect the pattern, record findings, and track the case.

## Architecture at a glance

`frontend/` → `backend/api/` → `backend/lib/` → trained model and D1 → `frontend/` results.

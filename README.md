# AEGIS-AML MVP

This is a local-first hackathon MVP implementing the AEGIS-AML 3-layer architecture:
- RAW deterministic checks
- ML proxy risk scoring with explainable feature contributions
- Graph intelligence scoring with path/centrality/trust signals

## API
- Health: `GET /api/v1/health`
- Scam exposure: `POST /api/v1/scam-exposure`
- Feedback loop: `POST /api/v1/feedback`
- Active dynamic weights: `GET /api/v1/weights`

### Sharing API (ML Model + LLM for teammates)
Share your trained model and local LLM with remote teammates via REST endpoints.
All protected by the same `x-api-key` header when `AEGIS_REQUIRE_API_KEY=true`.

#### ML Inference
- **`POST /api/v1/ml/predict`** — Run standalone ML model inference (XGBoost or deterministic proxy)
  ```json
  {
    "transaction_amount": 75000,
    "tx_count_last_hour": 9,
    "has_upi": true,
    "transaction_note": "urgent mule transfer"
  }
  ```
  Returns: `score`, `probability`, `contributions`, `reasoning`, `model_source`, `nlp_terms`

- **`GET /api/v1/ml/info`** — Model metadata + top SHAP features

#### LLM Chat
- **`POST /api/v1/llm/chat`** — Conversational LLM (Ollama) with session rule injection
  ```json
  {
    "message": "What accounts have the highest risk?",
    "include_ml_artifacts": true
  }
  ```
  Returns: `reply`, `plan`, `result`, `suggested_next`, `llm_used`, `model_name`

- **`GET /api/v1/llm/status`** — Check Ollama connectivity and LLM config

#### NLP Analysis
- **`POST /api/v1/nlp/analyze`** — Analyse a transaction note for AML risk signals (lexicon + LLM)
  ```json
  {"note": "urgent cashout to mule wallet"}
  ```
  Returns: `score` (0-100), `matched_terms`, `llm_summary`, `llm_enabled`

#### Session Rules (API-level CRUD)
- **`GET /api/v1/session-rules`** — List active API session rules
- **`POST /api/v1/session-rules`** — Inject rules via natural language
  ```json
  {"text": "In this session, prioritize recall >= 0.80"}
  ```
- **`DELETE /api/v1/session-rules`** — Clear all API session rules

## Agentic AML demo (RAW + SAR + A2A-inspired)
- Run local agentic orchestration pipeline on CSV:
  - `python scripts/run_agentic_aml_demo.py --data-path data/training_transactions.csv --max-rows 200 --report-path artifacts/agentic_report.json`
- Module used:
  - `app/services/agentic_aml.py`
- Output:
  - `artifacts/agentic_report.json` containing summary metrics and a sample SAR-style report.

## Run locally
1. Create/activate virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start server:
   - `uvicorn app.main:app --reload`

### One-command start/stop (PowerShell)
- Start API + dashboard:
  - `./scripts/start_all.ps1`
- Check API/dashboard status + health:
  - `./scripts/status_all.ps1`
- Stop API + dashboard:
  - `./scripts/stop_all.ps1`

## Share backend with teammate (hackathon mode)

1. Start local services:
  - `./scripts/start_all.ps1`
2. (Optional but recommended) enable API key protection for non-public endpoints:
  - `$env:AEGIS_REQUIRE_API_KEY='true'`
  - `$env:AEGIS_API_KEY='your-strong-shared-key'`
3. Set allowed frontend origins (comma-separated). For temporary hackathon testing you can use `*`:
  - `$env:AEGIS_CORS_ORIGINS='*'`
  - Example for specific dev origins: `$env:AEGIS_CORS_ORIGINS='http://localhost:3000,https://your-frontend-domain.vercel.app'`
4. Restart API after env changes:
  - `./scripts/stop_all.ps1`
  - `./scripts/start_all.ps1`
5. Expose backend publicly:
  - `./scripts/share_backend.ps1`
  - This uses `cloudflared` if available, otherwise `ngrok`.
6. Share with teammate:
  - Base URL (from tunnel output), e.g. `https://xxxx.trycloudflare.com`
  - Health check: `GET /api/v1/health`
  - Swagger docs: `/docs`
  - If API key is enabled, send header on protected endpoints:
    - `x-api-key: your-strong-shared-key`

### Endpoint auth behavior
- Public endpoint:
  - `GET /api/v1/health`
- Protected when `AEGIS_REQUIRE_API_KEY=true`:
  - `POST /api/v1/scam-exposure`
  - `POST /api/v1/feedback`
  - `GET /api/v1/weights`

## Unified Frontend (default)
- Launch one all-in-one dashboard:
  - `streamlit run app/ui/hackathon_dashboard.py`
- Includes everything in one place:
  - Live transaction risk scoring + orchestration trace
  - Human feedback loop + dynamic weight recalibration
  - Batch simulation lab
  - Case intelligence monitor (leaderboard, exposure mix, recent cases)
  - No-code training controls with target recall
  - Explainability and artifact dashboards

## Editable RAW rules (hot reload)
- RAW rules are configured in [rules/raw_rules.json](rules/raw_rules.json).
- Update rule thresholds/weights/components in this JSON file.
- The RAW engine auto-reloads rules when file timestamp changes (no code edit needed).

## NLP installation/setup
- Install dependencies:
  - `pip install -r requirements.txt`
- Download NLP resources:
  - `python scripts/setup_nlp.py`

## Local LLM setup (recommended for your hardware)
- For a laptop with 16GB RAM + RTX 4060 8GB, use a 7B quantized model for best quality/speed balance.
- Recommended default model:
  - `phi3.5`
- One-time setup (requires Ollama installed locally):
  - `python scripts/setup_local_llm.py --model phi3.5`
- Enable LLM-augmented NLP in current PowerShell session:
  - `$env:AEGIS_LLM_ENABLED='true'`
  - `$env:AEGIS_LLM_MODEL='phi3.5'`
  - `$env:AEGIS_LLM_ENDPOINT='http://localhost:11434/api/generate'`
- Then run your app normally:
  - `streamlit run app/ui/hackathon_dashboard.py`
- Notes:
  - If Ollama is unavailable, the project automatically falls back to deterministic lexicon NLP.
  - LLM output is constrained to structured JSON and merged with existing explainable signals.

## ML training
- Put your local real CSV at `data/training_transactions.csv` (or pass custom path).
- Preview transformed features before training:
  - `python scripts/preview_feature_mapping.py --data-path data/training_transactions.csv --rows 15`
- Train deterministic local model (XGBoost + SHAP):
  - `python scripts/train_ml.py --data-path data/training_transactions.csv`
  - AML-oriented threshold tuning example: `python scripts/train_ml.py --data-path data/training_transactions.csv --target-recall 0.70`
- PaySim-like datasets are auto-supported (columns: `amount`, `step`, `nameOrig`, `isFraud`).
- AML-CFT tabular format is also supported (columns like `Time`, `Date`, `Sender_account`, `Receiver_account`, `Amount`, `Payment_currency`, `Received_currency`, `Sender_bank_location`, `Receiver_bank_location`, `Payment_type`, `Is_laundering`, `Laundering_type`).
- No external runtime dataset downloads are required in the training flow.
- Output model path:
  - `artifacts/ml_model.joblib`
- Output metadata path:
  - `artifacts/ml_model_metadata.json`
- Output SHAP summary path:
  - `artifacts/ml_model_shap_summary.json`
- Runtime behavior:
  - If the model artifact exists, `ml_service` uses trained inference.
  - If not, backend falls back to deterministic proxy scoring.

## Example request
```json
{
  "account_id": "acct_1001",
  "upi_id": "user@upi",
  "transaction_amount": 62000,
  "tx_count_last_hour": 7,
  "transaction_note": "urgent cashout to mule wallet"
}
```

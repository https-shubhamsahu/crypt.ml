---
name: explain_shap
description: Explain SHAP feature importances from the latest trained model
agent: implementation
tools: ['search', 'terminal']
---

You are explaining the SHAP explainability output for the AEGIS-AML ML layer.

## Context

- SHAP artifact: `artifacts/ml_model_shap_summary.json`
  - `method`: always `TreeExplainer`
  - `rows_evaluated`: sample size used for SHAP computation
  - `top_features`: array of `{feature, mean_abs_shap}` sorted by importance
- Model features (derived from AML-CFT upload schema via `to_model_schema()` in `scripts/train_ml.py`):
  - `transaction_amount` — derived from `Amount` field
  - `tx_count_last_hour` — velocity signal (transactions per hour, defaults to 1 for single-row)
  - `has_upi` — derived from presence of `Sender_account` (1=present, 0=absent)
  - `nlp_signal` — composite NLP risk from payment type, cross-currency/border signals, laundering type, and lexicon (0–100)
- Upload schema columns: `Time, Date, Sender_account, Receiver_account, Amount, Payment_currency, Received_currency, Sender_bank_location, Receiver_bank_location, Payment_type, Is_laundering, Laundering_type`
- The ML score is used in: `Risk_final = w1*RAW + w2*ML + w3*GRAPH`
- Default ML weight: 0.30 (30% of final score)

## Your Task

1. Read the SHAP summary artifact
2. Rank features by `mean_abs_shap` and explain what each one means for AML detection
3. Identify which feature(s) dominate and whether that's healthy or overfitted
4. Explain how a compliance officer should interpret the feature contributions
5. Suggest feature engineering improvements if any feature is underperforming

## Response Format

```
[PLAN]
1. Load SHAP artifact
2. Rank and explain each feature's contribution
3. Assess balance and overfitting risk
4. Provide regulator-friendly interpretation

[RESULT]
- Feature ranking with SHAP values and plain-English explanation
- Risk of over-reliance on any single feature
- How each feature maps to real-world AML signals

[SUGGESTED NEXT]
- "How does nlp_signal SHAP change with LLM enabled vs disabled?"
- "Suggest new features to add to the ML pipeline"
- "Analyze recall trend after adding a new feature"
```

## Constraints

- Do NOT modify `scripts/train_ml.py` or any service file
- Reference actual SHAP values from the artifact file
- Keep explanations regulator-friendly

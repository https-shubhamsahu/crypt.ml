---
name: analyze_recall_trend
description: Analyze fraud recall trends across training sessions and suggest improvements
agent: implementation
tools: ['search', 'terminal']
---

You are analyzing the recall trend of the AEGIS-AML ML pipeline.

## Context

- Model: XGBoost binary classifier stored at `artifacts/ml_model.joblib`
- Metadata: `artifacts/ml_model_metadata.json` — contains `roc_auc`, `threshold`, `target_recall`, `rows_used`, `class_distribution`
- SHAP: `artifacts/ml_model_shap_summary.json` — contains `top_features` with `mean_abs_shap`
- Training script: `scripts/train_ml.py` — function `train_model(data_path, target_recall)`
- Threshold selection: `_threshold_for_target_recall()` picks the lowest threshold achieving the requested recall; falls back to F1-optimal via `_best_threshold()`

## Your Task

1. Read `artifacts/ml_model_metadata.json` for current metrics
2. Identify the `target_recall` vs achieved ROC-AUC gap
3. Analyze `class_distribution` for label imbalance
4. Check the `threshold` — a low threshold means high recall but more false positives
5. Cross-reference with SHAP to see which features drive recall

## Response Format

```
[PLAN]
1. Load metadata and SHAP artifacts
2. Analyze recall/threshold relationship
3. Identify class imbalance impact
4. Suggest improvement actions

[RESULT]
- Current recall target: X
- Current ROC-AUC: X
- Current threshold: X
- Class balance: fraud=X, legit=X
- Dominant features by SHAP: [list]
- Assessment: [explanation of recall health]

[SUGGESTED NEXT]
- "Retrain with target_recall=0.80 and compare metrics"
- "Show SHAP feature impact on recall changes"
- "Explain how NLP signal strength affects ML recall"
```

## Constraints

- Do NOT modify `scripts/train_ml.py` or `app/services/ml_service.py`
- Express threshold/recall improvements as suggestions
- Always reference actual artifact values, never hallucinate metrics

# Zhipu GLM Risk Scoring Evaluation

This directory contains a self-contained pilot experiment for comparing direct
GLM-5.2 risk scoring with the existing RandomForest scorer.

The scripts intentionally do not store API keys. Pass the key through
`ZHIPU_API_KEY`, `--api-key-file`, or `--api-key-stdin`.

## Pilot Run

Score a balanced subset from the same random holdout split used by
`training/train_randomforest.py`:

```bash
python3 zhipu_glm_eval/score_with_glm.py \
  --api-key-stdin \
  --limit 30 \
  --max-tokens 512 \
  --response-format-json \
  --disable-thinking \
  --output zhipu_glm_eval/outputs/glm52_holdout_jsonmode_pilot30.jsonl
```

Then compare GLM scores with the reproduced RandomForest holdout predictions:

```bash
python3 zhipu_glm_eval/compare_glm_rf.py \
  --glm-scores zhipu_glm_eval/outputs/glm52_holdout_jsonmode_pilot30.jsonl \
  --output-dir zhipu_glm_eval/outputs/jsonmode_pilot30
```

Outputs are written under `zhipu_glm_eval/outputs/`.

## Full Holdout Band Run

For the thesis-facing comparison, prefer the full holdout split and risk-band
analysis instead of MAE against the old rigid labels:

```bash
python3 zhipu_glm_eval/score_with_glm.py \
  --api-key-stdin \
  --all-holdout \
  --max-tokens 512 \
  --response-format-json \
  --disable-thinking \
  --output zhipu_glm_eval/outputs/glm52_holdout_jsonmode_full.jsonl
```

Then summarize whether GLM scores fall in the expected risk intervals:

```bash
python3 zhipu_glm_eval/analyze_score_bands.py \
  --glm-scores zhipu_glm_eval/outputs/glm52_holdout_jsonmode_full.jsonl \
  --output-dir zhipu_glm_eval/outputs/jsonmode_full_bands
```

The rule-defined intervals are:

- `0-20`: low
- `21-34`: low_medium
- `35-49`: medium_cloud_or_test
- `50-79`: suspicious
- `80-100`: high

## What Is Compared

- `teacher_score`: the existing `llm_label.risk_score` in
  `training/scored_data.jsonl`.
- `rf_score`: RandomForest predictions reproduced with the same preprocessing,
  train/test split, and model parameters as `training/train_randomforest.py`.
- `glm_score`: direct GLM-5.2 scoring from the original fingerprint payload and
  `scoring/rule_knowledge_base.json`.

Before sending a sample to GLM, `llm_label` is removed so the model cannot copy
the existing score.

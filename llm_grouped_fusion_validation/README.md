# GLM-5.2 Grouped-Fusion Validation

This directory validates two additions:

1. Google-official knowledge metadata in `scoring/rule_knowledge_base.json`.
2. Stable-device grouping, group sample weights, and train-fold runtime perturbation for repeated device profiles.

See `EXPERIMENT_DESIGN.md` for the advisor-facing design.

## 1. Prepare Offline Assets

```bash
python3 llm_grouped_fusion_validation/prepare_validation_assets.py
```

This creates:

- `rule_kb_no_official_ablation.json`
- `group_metadata.csv`
- `validation_sample_manifest.csv`
- `targeted_sample_manifest.csv`
- `llm_group_evidence.jsonl`
- `llm_group_evidence_augmented.jsonl`
- `perturbation_plan.json`
- `ASSET_SUMMARY.md`

## 2. Score Boundary Pilot With GLM-5.2

K0 no-official knowledge:

```bash
python3 llm_grouped_fusion_validation/score_group_evidence_with_glm.py \
  --api-key-stdin \
  --model glm-5.2 \
  --knowledge-version K0_no_official \
  --rule-kb llm_grouped_fusion_validation/rule_kb_no_official_ablation.json \
  --evidence llm_grouped_fusion_validation/llm_group_evidence.jsonl \
  --manifest llm_grouped_fusion_validation/validation_sample_manifest.csv \
  --manifest-filter boundary_candidate \
  --response-format-json \
  --disable-thinking \
  --output llm_grouped_fusion_validation/outputs/glm52_group_scores_k0_boundary.jsonl
```

K1 official knowledge:

```bash
python3 llm_grouped_fusion_validation/score_group_evidence_with_glm.py \
  --api-key-stdin \
  --model glm-5.2 \
  --knowledge-version K1_official \
  --rule-kb scoring/rule_knowledge_base.json \
  --evidence llm_grouped_fusion_validation/llm_group_evidence.jsonl \
  --manifest llm_grouped_fusion_validation/validation_sample_manifest.csv \
  --manifest-filter boundary_candidate \
  --response-format-json \
  --disable-thinking \
  --output llm_grouped_fusion_validation/outputs/glm52_group_scores_k1_boundary.jsonl
```

## 3. Evaluate Knowledge Ablation

```bash
python3 llm_grouped_fusion_validation/evaluate_knowledge_ablation.py \
  --k0 llm_grouped_fusion_validation/outputs/glm52_group_scores_k0_boundary.jsonl \
  --k1 llm_grouped_fusion_validation/outputs/glm52_group_scores_k1_boundary.jsonl \
  --output-dir llm_grouped_fusion_validation/outputs/knowledge_ablation_boundary
```

## 4. Direct Risk-Score Knowledge Ablation

The group-score ablation is useful for fusion, but direct risk scoring is the
cleaner check for whether official knowledge changes GLM's final risk judgment.

K0 no-official knowledge:

```bash
python3 llm_grouped_fusion_validation/score_direct_manifest_with_glm.py \
  --api-key-stdin \
  --model glm-5.2 \
  --knowledge-version K0_no_official \
  --rule-kb llm_grouped_fusion_validation/rule_kb_no_official_ablation.json \
  --manifest llm_grouped_fusion_validation/validation_sample_manifest.csv \
  --manifest-filter rule_targeted_candidate \
  --response-format-json \
  --disable-thinking \
  --output llm_grouped_fusion_validation/outputs/glm52_direct_k0_targeted.jsonl
```

K1 official knowledge:

```bash
python3 llm_grouped_fusion_validation/score_direct_manifest_with_glm.py \
  --api-key-stdin \
  --model glm-5.2 \
  --knowledge-version K1_official \
  --rule-kb scoring/rule_knowledge_base.json \
  --manifest llm_grouped_fusion_validation/validation_sample_manifest.csv \
  --manifest-filter rule_targeted_candidate \
  --response-format-json \
  --disable-thinking \
  --output llm_grouped_fusion_validation/outputs/glm52_direct_k1_targeted.jsonl
```

Then evaluate:

```bash
python3 llm_grouped_fusion_validation/evaluate_knowledge_ablation.py \
  --k0 llm_grouped_fusion_validation/outputs/glm52_direct_k0_targeted.jsonl \
  --k1 llm_grouped_fusion_validation/outputs/glm52_direct_k1_targeted.jsonl \
  --output-dir llm_grouped_fusion_validation/outputs/knowledge_ablation_direct_targeted
```

## 5. Score Full Original and Augmented Evidence

For full grouped-fusion validation, score originals and train-fold augmentation candidates.

Original K1 scores:

```bash
python3 llm_grouped_fusion_validation/score_group_evidence_with_glm.py \
  --api-key-stdin \
  --model glm-5.2 \
  --knowledge-version K1_official \
  --rule-kb scoring/rule_knowledge_base.json \
  --evidence llm_grouped_fusion_validation/llm_group_evidence.jsonl \
  --response-format-json \
  --disable-thinking \
  --output llm_grouped_fusion_validation/outputs/glm52_group_scores_k1_full.jsonl
```

Augmented K1 scores:

```bash
python3 llm_grouped_fusion_validation/score_group_evidence_with_glm.py \
  --api-key-stdin \
  --model glm-5.2 \
  --knowledge-version K1_official \
  --rule-kb scoring/rule_knowledge_base.json \
  --evidence llm_grouped_fusion_validation/llm_group_evidence_augmented.jsonl \
  --include-augmented \
  --response-format-json \
  --disable-thinking \
  --output llm_grouped_fusion_validation/outputs/glm52_group_scores_k1_augmented.jsonl
```

## 6. Evaluate Cached Group Fusion

```bash
python3 llm_grouped_fusion_validation/evaluate_cached_group_fusion.py \
  --scores \
    llm_grouped_fusion_validation/outputs/glm52_group_scores_k1_full.jsonl \
    llm_grouped_fusion_validation/outputs/glm52_group_scores_k1_augmented.jsonl \
  --output-dir llm_grouped_fusion_validation/outputs/group_fusion_k1
```

The fusion evaluator always tests on original evidence rows. Augmented evidence rows are eligible only in training folds.

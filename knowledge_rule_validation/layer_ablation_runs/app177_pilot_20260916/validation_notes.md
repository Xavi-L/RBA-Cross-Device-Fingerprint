# Verification

- 13 focused unit tests passed (5 input-ablation boundaries and 8 existing semantic-relation tests).
- All 276 full-App stage/lane alert-ID sets agree with the existing accepted expanded two-source outputs.
- Balanced replay: 69 pairs x 7 views x 2 lanes = 966 comparisons; 1932 stage/lane records.
- Latest unlabeled QC is separate: 26 samples x 7 views x 2 lanes = 364 records.
- No Browser67/Full244 decisions were emitted; both groups remain NOT_EVALUATED.
- No training, LLM call, threshold adjustment or formal metric computation.

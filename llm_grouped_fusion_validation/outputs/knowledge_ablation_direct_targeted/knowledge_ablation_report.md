# Knowledge Ablation Report

| Metric | K0 no official | K1 official | Delta |
|---|---:|---:|---:|
| Rows | 60 | 60 | 0 |
| MAE | 2.367 | 2.750 | 0.383 |
| RMSE | 3.291 | 4.649 | 1.358 |
| Five-band match | 96.67% | 96.67% | 0.00% |
| Three-band match | 100.00% | 96.67% | -3.33% |
| High-risk F1 | 1.000 | 1.000 | 0.000 |
| Future-only reason hits | 0 | 0 | 0 |

- Paired improved rows: 7
- Paired worsened rows: 8
- Paired unchanged rows: 45

Interpretation note: lower MAE/RMSE is better; higher band match and high-risk F1 are better; future-only reason hits should stay at 0.

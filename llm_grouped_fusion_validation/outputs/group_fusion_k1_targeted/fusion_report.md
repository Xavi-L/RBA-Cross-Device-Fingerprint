# Cached GLM Group Fusion Report

| Config | Train perturbation | Sample weight | MAE | RMSE | High-risk F1 |
|---|---:|---:|---:|---:|---:|
| Original group scores, unweighted | False | False | 7.983 | 9.954 | 0.333 |
| Original group scores + group sample weight | False | True | 6.318 | 7.761 | 0.467 |
| Train-fold runtime perturbation, unweighted | True | False | 7.983 | 9.954 | 0.333 |
| Train-fold runtime perturbation + group sample weight | True | True | 6.318 | 7.761 | 0.467 |

Test folds use only original evidence rows. Augmented evidence rows, if available, are used only in training folds.

# MOPSO-DT 4-Hour Benchmark Report

Generated: 2026-05-04 10:33:24
Mode: Quick
GPU Available: False

## Part 1: Scalability
| J | Runtime (s) | HV | Solutions | ECR Range |
|---|------------|----|-----------|-----------|
| 10 | 0.6±0.0 | 0.0200 | 3 | [0.000, 0.020] |
| 20 | 0.6±0.0 | 0.1097 | 4 | [0.030, 0.110] |

## Part 2: Ablation Study
| Config | Scenario | HV | Solutions | ECR Max |
|--------|----------|----|-----------|--------|
| A. Baseline | Small | 0.3290 | 3 | 0.330 |
| B. +Standard W | Small | 0.1994 | 19 | 0.200 |
| C. +Crowding GB | Small | 0.1495 | 27 | 0.150 |
| D. Full | Small | 0.1495 | 27 | 0.150 |

## Part 3: Region Robustness
| Shape | HV | ECR Max | J_min |
|-------|----|---------|-------|
| lshape | 0.1172 | 0.118 | 1.4907e-05 |
| square | 0.0498 | 0.050 | 8.9265e-06 |

## Part 4: Parameter Sensitivity

### N_P
| Value | HV | Time (s) | Solutions |
|-------|----|---------|-----------|
| 10 | 0.7416 | 0.7 | 5 |
| 30 | 0.4864 | 1.8 | 8 |

### T_max
| Value | HV | Time (s) | Solutions |
|-------|----|---------|-----------|
| 5 | 0.7416 | 0.7 | 5 |
| 10 | 0.5937 | 1.3 | 7 |

### p_c
| Value | HV | Time (s) | Solutions |
|-------|----|---------|-----------|
| 0.5 | 0.7416 | 0.8 | 5 |
| 0.9 | 0.7416 | 0.9 | 5 |

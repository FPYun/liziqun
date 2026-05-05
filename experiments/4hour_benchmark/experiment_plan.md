# 4-Hour CPU+GPU Hybrid Benchmark Suite — 实验计划

## 1. 实验目标

全面评估 MOPSO-DT 算法的四个方面：
1. **可扩展性** — 随雷达数量 J 如何扩展
2. **改进贡献** — 三个改进组件各自贡献多少（消融实验）
3. **区域鲁棒性** — 对不同形状的部署区域是否鲁棒
4. **参数敏感性** — 关键超参数的影响

## 2. CPU+GPU Hybrid Architecture

MOPSO 每轮迭代评估 N_P 个粒子。HybridMOPSO 同时使用 GPU 和 CPU：

```
粒子: [=========== N_P ===========]
GPU:  [======== 80% ========]      ← CuPy 向量化 (串行, 快)
CPU:                    [== 20% ==] ← ThreadPoolExecutor (并行)
                         ↑ 两组同时并发 ↑
```

- GPU 单次评估约比 CPU 快 15x
- CPU 使用多线程并行
- 保守墙钟加速比: **4x**（实际 GPU 越好则越快）

## 3. 运行时估算公式

```
T_cpu(seconds) ≈ N_P × T_max × J × grid_size² × 4.5 × 10⁻⁷
```

基准：J=50, N_P=100, T_max=200, grid=25 → 281s（源自 test_gpu.py）

## 4. 实验结构（共 98 runs，墙钟 ~4h）

### 公共默认参数
- region: 正方形
- beta=0.02, P0=0.95, P_min=0.8, is_air=True
- MOPSO: archive_size=100, c_1=2.0, c_2=2.0, p_c=0.9

---

### Part 1: 可扩展性分析 (15 runs, ~1.2h 墙钟)

**科学问题**: MOPSO-DT 随雷达数量 J 如何扩展？

| J | N_P | T_max | grid | 任务点 | 单次CPU | ×3 seeds CPU | 墙钟(~4x) |
|---|-----|-------|------|--------|---------|-------------|----------|
| 10 | 100 | 300 | 40 | 1600 | 3.6 min | 10.8 min | 2.7 min |
| 20 | 100 | 300 | 40 | 1600 | 7.2 min | 21.6 min | 5.4 min |
| 40 | 100 | 300 | 40 | 1600 | 14.4 min | 43.2 min | 10.8 min |
| 80 | 100 | 300 | 40 | 1600 | 28.8 min | 86.4 min | 21.6 min |
| 120 | 100 | 300 | 40 | 1600 | 43.2 min | 129.6 min | 32.4 min |

**固定**: region=500km², w_strategy='standard', p_m_base=0.01, select_gb='crowding'
**指标**: runtime, archive_size, objectives范围, hypervolume

---

### Part 2: 消融实验 (36 runs, ~1.5h 墙钟)

**4 种配置**:
| 配置 | w_strategy | select_gb | p_m_base |
|------|-----------|-----------|----------|
| A. Baseline | legacy | random | 0.0 |
| B. +Standard W | standard | random | 0.0 |
| C. +Crowding GB | standard | crowding | 0.0 |
| D. Full | standard | crowding | 0.01 |

**3 种场景**:
| 场景 | 区域 | J | grid | N_P | T_max | 单次CPU |
|------|------|---|------|-----|-------|---------|
| Small | 200km² | 10 | 30 | 80 | 400 | 2.2 min |
| Medium | 400km² | 30 | 35 | 80 | 400 | 8.8 min |
| Large | 600km² | 50 | 40 | 80 | 400 | 19.2 min |

4 configs × 3 scenarios × 3 seeds = **36 runs**
CPU: 362 min (6.0h) → 墙钟: ~91 min

---

### Part 3: 区域鲁棒性 (20 runs, ~0.75h 墙钟)

**5 种区域**:
| 区域 | 描述 |
|------|------|
| Square | 300×300 正方形 |
| L-shape | L 形 (0,0)-(300,0)-(300,100)-(100,100)-(100,300)-(0,300) |
| With-holes | 300×300 含 100×100 方形空洞 |
| Narrow | 300×50 狭长走廊 |
| Star | 8 顶点三角函数星形 |

**固定**: J=30, grid=40, N_P=100, T_max=250, 4 seeds
单次CPU: 9.0 min → CPU: 180 min (3.0h) → 墙钟: ~45 min

---

### Part 4: 参数敏感性 (27 runs, ~0.5h 墙钟)

**固定**: J=30, grid=35 (1225任务点), p_c=0.9, 3 seeds

**N_P 扫描** (T_max=200):
| N_P | 单次CPU | ×3 seeds |
|-----|---------|----------|
| 30 | 1.6 min | 4.9 min |
| 60 | 3.3 min | 9.9 min |
| 120 | 6.6 min | 19.8 min |

**T_max 扫描** (N_P=80):
| T_max | 单次CPU | ×3 seeds |
|-------|---------|----------|
| 100 | 2.2 min | 6.6 min |
| 200 | 4.4 min | 13.2 min |
| 400 | 8.8 min | 26.4 min |

**p_c 扫描** (N_P=80, T_max=200):
| p_c | 单次CPU | ×3 seeds |
|-----|---------|----------|
| 0.5 | 4.4 min | 13.2 min |
| 0.7 | 4.4 min | 13.2 min |
| 0.9 | 4.4 min | 13.2 min |

27 runs, CPU: 120.6 min → 墙钟: ~30 min

---

## 5. 总计

| Part | Runs | CPU耗时 | 墙钟 |
|------|------|---------|------|
| 1. 可扩展性 | 15 | 4.86 h | 1.2 h |
| 2. 消融实验 | 36 | 6.04 h | 1.5 h |
| 3. 区域鲁棒性 | 20 | 3.00 h | 0.75 h |
| 4. 参数敏感性 | 27 | 2.01 h | 0.5 h |
| **总计** | **98** | **15.9 h** | **~4.0 h** |

## 6. 待实现文件

| 文件 | 说明 |
|------|------|
| `src/hybrid_mopso.py` | HybridMOPSO 类，继承 MOPSO_DT，CPU+GPU 并发评估 |
| `experiment_4hour.py` | 实验主脚本，4 部分依次执行 |
| `README.md` | 实验说明与快速开始 |

## 7. 输出物

| 文件 | 说明 |
|------|------|
| `figures/scalability.png` | 5面板: runtime/Pareto/HV/ECR-range/J_min-range vs J |
| `figures/ablation.png` | 堆叠柱状图: 4配置×3场景 |
| `figures/regions.png` | 5种区域部署方案可视化 |
| `figures/sensitivity.png` | 3面板参数影响曲线 |
| `results/experiment_report.md` | 自动生成的完整报告 |
| `results/experiment_results.json` | 结构化数据 |

## 8. HybridMOPSO 实现要点

1. 继承 `MOPSO_DT`，新增参数 `cpu_evaluate_func` 和 `gpu_fraction=0.8`
2. 重写 `_evaluate_particles_parallel()`：
   - 粒子按 `gpu_fraction` 分为 GPU 组和 CPU 组
   - GPU 组: 用 `evaluate_func` 串行评估（CuPy 向量化已充分并行）
   - CPU 组: 用 `ThreadPoolExecutor` + `cpu_evaluate_func` 并行评估
   - 两组通过 `concurrent.futures` 同时启动，`as_completed` 收集结果
3. CPU evaluate_func: 需要创建强制使用 numpy 的评估函数版本
   - 关键：将 `evaluation._calc_detection_matrix_simple` 和 `_calc_jamming_matrix_simple` 复制为 numpy 版本
4. 其他方法（`_evaluate_and_archive`, `_evaluate_and_update_best`）调用重写后的并行方法

## 9. 关键依赖路径

```
experiment_4hour.py
    ├── src/hybrid_mopso.py (HybridMOPSO)
    │   ├── src/mopso.py (MOPSO_DT)
    │   ├── src/evaluation.py (GPU evaluate_func + CPU 版本)
    │   └── src/optimization_utils.py
    ├── src/decomposition.py
    ├── src/evaluation.py (RadarConfig, generate_uniform_task_points, etc.)
    ├── src/benchmarks.py (find_knee_point, get_extreme_points)
    └── src/pareto_visualization.py
```

## 10. 验证

```bash
cd experiments/4hour_benchmark

# 快速测试 (~2 min)
python experiment_4hour.py --quick

# 完整运行
python experiment_4hour.py
```

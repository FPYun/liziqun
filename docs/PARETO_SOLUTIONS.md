# Pareto解的生成过程与思路

**日期**: 2026-05-04
**项目**: 多功能雷达网络部署优化 (MOPSO-DT)

---

## 1. 问题背景：为什么需要Pareto优化？

雷达网络部署面临两个冲突的目标：
- **目标1 (f₁)**: 最大化期望覆盖率 (ECR) — 希望覆盖更多区域
- **目标2 (f₂)**: 最小化干扰功率密度 (J_min) — 希望降低被敌方侦测的风险

这两个目标相互制约：提高覆盖率通常会增加被侦测风险，反之亦然。

Pareto优化能同时找到一族非支配解，呈现目标间的完整权衡边界。

---

## 2. Pareto支配关系

### 2.1 支配的定义

对于两个解 A 和 B：
- **A 支配 B** 当且仅当：
  1. A 在所有目标上不差于 B
  2. A 在至少一个目标上严格优于 B

### 2.2 最小化问题转换

MOPSO-DT 中：
- f₁' = 1 - ECR（覆盖率最大化 → 最小化）
- f₂' = J_norm（归一化干扰功率密度 → 最小化）

### 2.3 代码位置

支配判断和拥挤度计算均在 `src/mopso.py` 的 `MOPSO_DT` 类中实现。

---

## 3. 外部档案机制

### 3.1 档案的作用

外部档案（Archive）存储所有发现的非劣解：
- 每评估一个粒子，将其与档案中的解比较
- 新解不被任何档案解支配 → 加入档案
- 新解支配某些档案解 → 删除被支配解

### 3.2 档案大小控制

当档案超过 `archive_size`（默认100）时，按拥挤度距离修剪，保留分布最均匀的解集。

---

## 4. 拥挤度距离

### 4.1 为什么需要？

防止档案中所有解聚集在Pareto前沿的某一点。拥挤度大的解位于稀疏区域，应优先保留。

### 4.2 计算公式

```
d_i(m) = (f_{i+1}(m) - f_{i-1}(m)) / (f_max(m) - f_min(m))
CD_i = Σ_m d_i(m)
```

边界解拥挤度 = ∞（优先保留）。

---

## 5. MOPSO-DT 算法流程

### 5.1 主循环

```
初始化粒子群
    ↓
评估 → 更新档案
    ↓
迭代 t = 1 to T_max:
    ↓
    计算动态参数:
      w = 惯性权重 (由 w_strategy 决定)
      p_m = max(p_m_base, w/N_P)
    ↓
    维护档案（拥挤度修剪）
    ↓
    选择全局最优 gb:
      random: 随机选择
      crowding: 拥挤度加权轮盘赌 ← 促进多样性
    ↓
    更新连续变量（PSO速度-位置公式）
    ↓
    更新二进制变量（交叉+变异）
    ↓
    评估 → 更新 pb → 更新档案
    ↓
返回Pareto前沿
```

### 5.2 改进要点

相比原始版本的三项关键改进：

| 改进项 | 原始 | 改进后 | 效果 |
|--------|------|--------|------|
| 惯性权重 w | 0.4→0.0 (legacy) | 0.9→0.4 (standard) | 全局探索能力大幅提升 |
| 变异概率 p_m | w/N_P (~0.008→0) | max(0.01, w/N_P) | 维持1%基础变异，防早熟 |
| gb选择 | 纯随机 | 拥挤度加权 | 引导填充前沿稀疏区 |

**A/B对比结果**（200km×200km, 8雷达, N_P=20, T_max=30）：

| 指标 | BASELINE | IMPROVED | 提升 |
|------|----------|----------|------|
| Pareto解数 | 4 | 34 | +750% |
| 超体积(HV) | 0.0399 | 0.0498 | +25% |
| f2范围 | 0.0013 | 0.0048 | +160% |

---

## 6. 归一化目标函数

### 6.1 为什么需要归一化？

ECR范围[0, 0.04] vs J_min范围[1e-6, 1e-5]，量纲差异极大。不归一化会导致目标空间距离被某个维度主导。

### 6.2 归一化方法

在 `create_normalized_evaluate_function()` 中实现：
- f₁ = 1 - ECR
- f₂ = J / J_max_ref（参考值归一化）

---

## 7. 辅助工具

### 7.1 拐点检测 (`src/benchmarks.py`)

```python
from src.benchmarks import find_knee_point, get_extreme_points

# 找到Pareto前沿上f1和f2最均衡的拐点
knee_idx = find_knee_point(objectives)  # argmin(f1² + f2²)

# 获取三个关键点：最佳覆盖、最佳干扰、拐点
best_cov, best_int, knee = get_extreme_points(objectives)
```

### 7.2 增强可视化 (`src/pareto_visualization.py`)

```python
from src.pareto_visualization import plot_pareto_front_enhanced

# 带拐点标注和颜色梯度的Pareto前沿图
plot_pareto_front_enhanced(objectives, save_path='pareto.png')
```

### 7.3 实验框架 (`src/experiment_runner.py`)

```python
from src.experiment_runner import ExperimentRunner

runner = ExperimentRunner()
runner.add_milestone('M0', 'Sanity Check')
runner.add_experiment('M0', 'E001', 'Quick Test', run_func)
runner.run_all()
runner.generate_report()  # 输出Markdown + JSON
```

---

## 8. 总结

```
Pareto解生成的关键要素：

1. 支配关系判断 → 区分优劣解
2. 外部档案维护 → 存储非劣解集
3. 拥挤度距离   → 保持多样性
4. 改进惯性权重 → standard策略 (0.9→0.4)
5. 变异概率下限 → p_m_base=0.01
6. 拥挤度选择   → 引导探索稀疏区域
7. 归一化目标   → 平衡不同量纲
```

---

## 参考文件

- `src/mopso.py` — MOPSO-DT 主算法（支配判断、拥挤度、PSO更新）
- `src/evaluation.py` — ECR/J_min 计算和归一化
- `src/benchmarks.py` — 拐点检测、标准测试函数
- `src/pareto_visualization.py` — Pareto前沿可视化
- `src/experiment_runner.py` — 结构化实验框架

---

**文档版本**: 2.0  
**最后更新**: 2026-05-04

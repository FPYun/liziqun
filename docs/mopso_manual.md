# MOPSO-DT 算法技术说明文档

## 目录
1. [算法概述](#1-算法概述)
2. [数学原理](#2-数学原理)
3. [核心类与接口](#3-核心类与接口)
4. [算法流程详解](#4-算法流程详解)
5. [参数配置指南](#5-参数配置指南)
6. [使用示例](#6-使用示例)
7. [性能优化建议](#7-性能优化建议)

---

## 1. 算法概述

### 1.1 什么是 MOPSO-DT？

**MOPSO-DT**（Multi-Objective Particle Swarm Optimization based on Decomposition and Transformation）是基于分解和变换的多目标粒子群优化算法。

### 1.2 应用领域

该算法专门用于**多功能雷达网络在复杂区域的部署优化**，能够同时处理：
- **连续变量**：雷达节点的归一化坐标位置
- **离散变量**：雷达部署的区域编码

### 1.3 核心特点

| 特性 | 说明 |
|------|------|
| 混合变量处理 | 同时优化连续坐标和二进制编码 |
| Pareto优化 | 维护非劣解档案，输出Pareto前沿 |
| 多样性保持 | 拥挤度距离机制防止早熟收敛 |
| 动态参数 | 惯性权重和变异概率随迭代自适应调整 |

---

## 2. 数学原理

### 2.1 决策变量表示

决策变量矩阵 **Φ** 的结构：

```
Φ = [hat_x₁, hat_y₁, b₁₁, b₁₂, ..., b₁Nₚ
     hat_x₂, hat_y₂, b₂₁, b₂₂, ..., b₂Nₚ
     ...
     hat_xJ, hat_yJ, bJ₁, bJ₂, ..., bJNₚ]
```

其中：
- **J**：雷达节点数
- **N_bin**：区域编码位数
- **(hat_xⱼ, hat_yⱼ)** ∈ [0,1]²：第j个雷达的归一化坐标
- **bⱼₖ** ∈ {0,1}：第j个雷达的第k位区域编码

### 2.2 Pareto支配关系

对于解 **A** 和 **B**，若满足：

```
∀i: fᵢ(A) ≤ fᵢ(B)  ∧  ∃j: fⱼ(A) < fⱼ(B)
```

则称 **A 支配 B**。

**注意**：本问题中目标1（覆盖率）需最大化，目标2（干扰）需最小化。实现时通过取负将最大化问题统一转化为最小化问题。

### 2.3 连续变量更新（PSO公式）

**速度更新**：
```
v(t+1) = w·v(t) + c₁·r₁·(pb - x(t)) + c₂·r₂·(gb - x(t))
```

**位置更新**：
```
x(t+1) = x(t) + v(t+1)
```

**边界处理**：
```
x(t+1) = clip(x(t+1), 0, 1)
```

参数说明：
- **w**：惯性权重，`w = -0.4/T_max × t + 0.4`
- **c₁, c₂**：认知和社会学习因子（默认2.0）
- **r₁, r₂**：[0,1]均匀分布随机数
- **pb**：个体历史最优位置
- **gb**：全局最优位置

### 2.4 二进制变量更新

#### 交叉操作（Crossover）

以概率 **p_c** 触发：
```
if r₃ < p_c:
    if r₄ < c₁/(c₁+c₂):
        bᵢⱼ(t+1) = pbᵢⱼ(t)    # 继承个体最优
    else:
        bᵢⱼ(t+1) = gbᵢⱼ(t)    # 继承全局最优
```

#### 变异操作（Mutation）

若未触发交叉，以概率 **p_m** 变异：
```
if r₅ < p_m:
    bᵢⱼ(t+1) = 1 - bᵢⱼ(t)     # 位取反
```

变异概率：`p_m = w / N_P`

### 2.5 拥挤度距离计算

对于第 **i** 个解在第 **m** 个目标上的拥挤度贡献：

```
cdᵢ(m) = (fₘ(i+1) - fₘ(i-1)) / (fₘ^max - fₘ^min)
```

总拥挤度：
```
CDᵢ = Σₘ cdᵢ(m)
```

边界解的拥挤度设为 **∞**（优先保留）。

---

## 3. 核心类与接口

### 3.1 Particle 类

表示粒子群中的一个粒子（候选解）。

```python
@dataclass
class Particle:
    position_continuous: np.ndarray   # 形状: (2J,)
    velocity_continuous: np.ndarray   # 形状: (2J,)
    position_binary: np.ndarray       # 形状: (J, N_bin)
    pb_continuous: np.ndarray         # 形状: (2J,)
    pb_binary: np.ndarray             # 形状: (J, N_bin)
    objectives: Optional[np.ndarray]  # 形状: (2,)
    pb_objectives: Optional[np.ndarray]  # 形状: (2,)
```

### 3.2 MOPSO_DT 类

主优化器类。

#### 构造函数

```python
MOPSO_DT(
    J: int,                          # 雷达节点数
    N_bin: int,                      # 区域编码位数
    evaluate_func: Callable,         # 目标函数评估接口
    N_P: int = 50,                   # 粒子群规模
    T_max: int = 500,                # 最大迭代次数
    c_1: float = 2.0,                # 认知学习因子
    c_2: float = 2.0,                # 社会学习因子
    p_c: float = 0.9,                # 交叉概率
    archive_size: int = 100,         # 档案大小限制
    verbose: bool = True             # 是否显示进度
)
```

#### 主要方法

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `optimize()` | 执行优化主流程 | `(archive, stats)` |
| `get_pareto_front()` | 获取Pareto前沿 | `(continuous, binary, objectives)` |
| `_dominates(obj1, obj2)` | 判断支配关系 | `bool` |
| `_calculate_crowding_distance()` | 计算拥挤度 | `np.ndarray` |

---

## 4. 算法流程详解

### 4.1 整体流程图

```
┌─────────────────────────────────────────────────────────────┐
│                         初始化阶段                           │
├─────────────────────────────────────────────────────────────┤
│ 1. 初始化粒子群                                              │
│    - 连续变量: rand[0,1]                                     │
│    - 二进制变量: rand{0,1}                                   │
│    - 速度: 0                                                 │
│    - pb = 当前位置                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      评估与初始归档                          │
├─────────────────────────────────────────────────────────────┤
│ 2. 评估所有粒子                                              │
│    - 调用 evaluate_func(Φ)                                   │
│    - 得到目标值 [coverage, interference]                     │
│                                                              │
│ 3. 初始归档                                                  │
│    - 所有解加入档案                                          │
│    - 非劣排序，剔除被支配解                                  │
│    - 随机选择 gb                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
         ┌─────────│   迭代 t=1 to T_max │──────────┐
         │         └──────────────────┘           │
         │                                        │
         ▼                                        │
┌─────────────────┐                               │
│ 计算动态参数    │                               │
│ w = -0.4/T_max × t + 0.4                       │
│ p_m = w / N_P                                  │
└────────┬────────┘                               │
         │                                        │
         ▼                                        │
┌─────────────────┐                               │
│ 维护档案        │                               │
│ - 非劣排序      │                               │
│ - 计算拥挤度    │                               │
│ - 截断至限制    │                               │
└────────┬────────┘                               │
         │                                        │
         ▼                                        │
┌─────────────────┐                               │
│ 选择全局最优 gb │                               │
│ (随机从档案选)  │                               │
└────────┬────────┘                               │
         │                                        │
         ▼                                        │
┌──────────────────────────────────┐            │
│         更新连续变量 (PSO)        │            │
├──────────────────────────────────┤            │
│ v = w·v + c₁·r₁·(pb-x) + c₂·r₂·(gb-x)        │
│ x = x + v                                      │
│ x = clip(x, 0, 1)                              │
└────────┬─────────────────────────┘            │
         │                                        │
         ▼                                        │
┌──────────────────────────────────┐            │
│      更新二进制变量 (交叉+变异)    │            │
├──────────────────────────────────┤            │
│ if r₃ < p_c:                                   │
│     继承 pb 或 gb                              │
│ else if r₅ < p_m:                              │
│     取反变异                                   │
└────────┬─────────────────────────┘            │
         │                                        │
         ▼                                        │
┌──────────────────────────────────┐            │
│      评估并更新最优解             │            │
├──────────────────────────────────┤            │
│ - 评估新位置                                   │
│ - 更新 pb (支配关系判断)                       │
│ - 加入档案                                     │
└────────┬─────────────────────────┘            │
         │                                        │
         └────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         输出结果                             │
├─────────────────────────────────────────────────────────────┤
│ - Pareto前沿解集                                             │
│ - 每个解的决策变量                                           │
│ - 目标函数值                                                 │
│ - 优化统计信息                                               │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 关键步骤详解

#### 步骤1：初始化

生成 **N_P** 个粒子：
- 连续变量：`np.random.uniform(0, 1, size=2J)`
- 二进制变量：`np.random.randint(0, 2, size=(J, N_bin))`
- 速度：`np.zeros(2J)`
- 个体最优 **pb** = 当前位置

#### 步骤2：非劣排序

```python
# 算法复杂度: O(N²)
for each solution i:
    for each solution j:
        if i dominates j:
            mark j as dominated
        elif j dominates i:
            mark i as dominated
            break

# 保留非支配解
archive = [sol for sol in archive if not sol.dominated]
```

#### 步骤3：档案维护

当档案大小超过限制时：
1. 计算所有解的拥挤度距离
2. 按拥挤度降序排列
3. 保留前 **archive_size** 个解

```python
distances = _calculate_crowding_distance()
sorted_indices = np.argsort(distances)[::-1]
archive = [archive[i] for i in sorted_indices[:archive_size]]
```

---

## 5. 参数配置指南

### 5.1 默认参数值

| 参数 | 默认值 | 说明 | 建议范围 |
|------|--------|------|----------|
| N_P | 50 | 粒子数 | 30-100 |
| T_max | 500 | 迭代次数 | 200-1000 |
| c_1 | 2.0 | 认知因子 | 1.5-2.5 |
| c_2 | 2.0 | 社会因子 | 1.5-2.5 |
| p_c | 0.9 | 交叉概率 | 0.7-0.95 |
| archive_size | 100 | 档案大小 | 50-200 |

### 5.2 参数调优建议

#### 粒子数 N_P

- **问题规模小**（J ≤ 5）：N_P = 30-40
- **问题规模中**（5 < J ≤ 15）：N_P = 50-70
- **问题规模大**（J > 15）：N_P = 80-100

#### 迭代次数 T_max

- **快速测试**：100-200
- **标准优化**：300-500
- **高精度优化**：800-1000

#### 学习因子 c_1, c_2

- **c₁ > c₂**：强调个体探索，适合多峰问题
- **c₁ < c₂**：强调社会学习，收敛更快但易早熟
- **c₁ = c₂ = 2.0**：平衡探索与开发（推荐）

#### 交叉概率 p_c

- **p_c 较高**（0.9+）：二进制变量更多继承优秀解
- **p_c 较低**（0.7-）：更多变异，增加多样性

### 5.3 问题特定配置

#### 小型问题（J=3, N_bin=2）
```python
MOPSO_DT(J=3, N_bin=2, N_P=30, T_max=100, archive_size=30)
```

#### 中型问题（J=10, N_bin=4）
```python
MOPSO_DT(J=10, N_bin=4, N_P=50, T_max=300, archive_size=80)
```

#### 大型问题（J=20, N_bin=5）
```python
MOPSO_DT(J=20, N_bin=5, N_P=80, T_max=500, archive_size=150)
```

---

## 6. 使用示例

### 6.1 基础用法

```python
import numpy as np
from src.mopso_dt import MOPSO_DT

# 定义目标函数
def evaluate(Phi):
    """
    Phi: 决策变量矩阵 (J, 2+N_bin)
    返回: [coverage, interference]
    """
    # 提取坐标
    coordinates = Phi[:, :2]  # (J, 2)
    encoding = Phi[:, 2:]     # (J, N_bin)
    
    # 计算覆盖率（示例）
    coverage = np.mean(coordinates[:, 0])
    
    # 计算干扰（示例）
    interference = np.std(coordinates[:, 1])
    
    return np.array([coverage, interference])

# 创建优化器
mopso = MOPSO_DT(
    J=5,                    # 5个雷达
    N_bin=3,                # 3位编码
    evaluate_func=evaluate,
    N_P=50,
    T_max=200,
    verbose=True
)

# 执行优化
archive, stats = mopso.optimize()

# 获取结果
continuous, binary, objectives = mopso.get_pareto_front()
print(f"找到 {len(objectives)} 个非劣解")
print(f"覆盖率: [{objectives[:,0].min():.3f}, {objectives[:,0].max():.3f}]")
```

### 6.2 与坐标变换结合

```python
from src.coordinate_transform import transform_coordinates
from shapely.geometry import Polygon

# 定义部署区域
region = Polygon([(0, 0), (10, 0), (10, 10), (5, 15), (0, 10)])

def evaluate_with_transform(Phi):
    """结合坐标变换的评估函数"""
    J = Phi.shape[0]
    
    # 坐标变换
    physical_positions = []
    for j in range(J):
        hat_x, hat_y = Phi[j, 0], Phi[j, 1]
        x, y = transform_coordinates(region, hat_x, hat_y)
        physical_positions.append([x, y])
    
    positions = np.array(physical_positions)
    
    # 计算目标...
    coverage = calculate_coverage(positions)
    interference = calculate_interference(positions)
    
    return np.array([coverage, interference])
```

### 6.3 结果可视化

```python
import matplotlib.pyplot as plt

# 获取Pareto前沿
continuous, binary, objectives = mopso.get_pareto_front()

# 绘制
fig, ax = plt.subplots(figsize=(8, 6))
scatter = ax.scatter(objectives[:, 0], objectives[:, 1], 
                    c=range(len(objectives)), cmap='viridis',
                    s=50, edgecolors='black')
ax.set_xlabel('Coverage (maximize)')
ax.set_ylabel('Interference (minimize)')
ax.set_title('Pareto Front')
ax.grid(True, alpha=0.3)
plt.colorbar(scatter, label='Solution Index')
plt.savefig('pareto_front.png', dpi=150)
```

---

## 7. 性能优化建议

### 7.1 评估函数优化

评估函数是性能瓶颈，建议：

```python
# ❌ 低效：逐个计算
def evaluate_slow(Phi):
    results = []
    for j in range(J):
        # 逐个计算
        result = compute(Phi[j])
        results.append(result)
    return np.array(results)

# ✅ 高效：向量化计算
def evaluate_fast(Phi):
    # 使用numpy向量化操作
    results = vectorized_compute(Phi)
    return results
```

### 7.2 并行评估

```python
from multiprocessing import Pool

def evaluate_parallel(Phi_list):
    """并行评估多个粒子"""
    with Pool(processes=4) as pool:
        results = pool.map(evaluate_func, Phi_list)
    return np.array(results)
```

### 7.3 内存优化

对于大规模问题：

```python
# 限制档案大小
archive_size = min(100, N_P * 2)

# 定期清理历史记录
if t % 100 == 0:
    mopso.history['crowding_distances'] = []
```

### 7.4 收敛判断

提前停止条件：

```python
# 如果档案大小连续多代不变，可能已收敛
if len(set(mopso.history['archive_size'][-20:])) == 1:
    print("算法已收敛，提前停止")
    break
```

---

## 8. 常见问题解答

### Q1: 为什么档案中的解数量很少？

**可能原因**：
- 评估函数返回的目标值过于相似
- 支配关系判断过于严格
- 档案大小限制过小

**解决方案**：
```python
# 检查评估函数是否返回多样化结果
test_objectives = [evaluate(random_Phi()) for _ in range(10)]
print(np.std(test_objectives, axis=0))  # 应有明显差异
```

### Q2: 算法收敛太慢？

**优化建议**：
1. 增加惯性权重初始值
2. 增加粒子数
3. 检查评估函数性能
4. 减少二进制编码位数

### Q3: 结果多样性不足？

**可能原因**：
- 社会学习因子 c₂ 过大
- 交叉概率 p_c 过高
- 档案维护过于激进

**解决方案**：
```python
# 增加多样性
mopso = MOPSO_DT(
    c_1=2.5, c_2=1.5,  # 强调个体探索
    p_c=0.7,           # 降低交叉概率
    archive_size=150   # 增大档案
)
```

---

## 9. 参考文献

1. Kennedy, J., & Eberhart, R. (1995). Particle swarm optimization. *Proceedings of ICNN'95*.
2. Coello, C. A. C., et al. (2004). Handling multiple objectives with particle swarm optimization. *IEEE TEC*.
3. Deb, K., et al. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. *IEEE TEC*.

---

**文档版本**: 1.0  
**最后更新**: 2026-04-01  
**作者**: Claude Code

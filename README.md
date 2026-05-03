# 多功能雷达网络部署优化 — MOPSO-DT

基于区域分解和多目标粒子群优化（MOPSO-DT）的雷达网络部署优化算法，同时优化期望覆盖率（ECR）和干扰功率密度（J_min）。

## 项目结构

```
liziqun/
├── src/                         # 核心算法库
│   ├── mopso.py                     # MOPSO-DT多目标优化（3种惯性策略+拥挤度选择）
│   ├── decomposition.py             # 区域分解算法（论文Algorithm 1）
│   ├── coordinate_transform.py      # 凸多边形坐标变换
│   ├── evaluation.py                # ECR和干扰功率密度计算（含GPU加速修复）
│   ├── benchmarks.py                # 标准测试函数 + 拐点检测
│   ├── pareto_visualization.py      # Pareto前沿增强可视化
│   ├── experiment_runner.py         # 结构化实验框架
│   ├── region_visualizer.py         # 区域分解可视化
│   ├── optimization_utils.py        # 性能优化工具（Numba JIT加速）
│   ├── grid_evaluator.py            # GPU网格评估
│   ├── cupy_gpu_fix.py              # CuPy Windows CJK路径修复
│   ├── logger.py                    # 日志系统
│   └── exceptions.py                # 异常处理
│
├── experiments/                # 实验脚本
│   ├── experiment_comprehensive.py      # 综合4任务（大区域/Pareto/相关性/权重）
│   ├── experiment_comprehensive_fast.py # 快速版
│   ├── experiment_challenging.py        # 挑战性场景
│   ├── experiment_paper_aligned.py      # 论文参数对齐
│   ├── tune_mopso.py                    # MOPSO参数调优
│   └── quick_compare.py                 # 改进前后A/B对比
│
├── tests/                      # 测试文件
│   ├── test_mopso.py               # MOPSO算法测试
│   ├── test_mopso_pytest.py        # MOPSO pytest套件
│   ├── test_performance.py         # 性能基准测试
│   ├── test_visualize.py           # 可视化测试
│   └── test_gpu.py                 # GPU加速测试
│
├── docs/                       # 技术文档
│   ├── mopso_manual.md             # MOPSO-DT技术手册
│   ├── decomposition_guide.md      # 区域分解算法详解
│   └── PARETO_SOLUTIONS.md         # Pareto解生成过程说明
│
├── figures/                    # 可视化输出
├── paper/                      # 论文材料
├── pyproject.toml              # 项目配置
├── requirements.txt            # Python依赖
└── README.md
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行实验

```bash
# 改进前后A/B对比（最快，~3秒）
python experiments/quick_compare.py

# MOPSO参数调优
python experiments/tune_mopso.py

# 综合实验（大区域 + Pareto分析 + 权重分析）
python experiments/experiment_comprehensive.py

# 论文参数对齐实验
python experiments/experiment_paper_aligned.py

# 挑战性场景
python experiments/experiment_challenging.py
```

### 运行测试

```bash
pytest tests/ -v
```

## 核心模块

### MOPSO-DT (`src/mopso.py`)

基于分解和变换的多目标粒子群优化，关键特性：

| 特性 | 说明 |
|------|------|
| 混合变量 | 同时优化连续坐标 + 二进制区域编码 |
| 惯性权重 | 3种策略：legacy(0.4→0.0) / standard(0.9→0.4) / adaptive |
| 全局最优选择 | 随机 / 拥挤度加权轮盘赌（促进多样性） |
| 变异概率 | `max(p_m_base, w/N_P)`，保证下限不退化 |
| 性能优化 | Numba JIT批量更新 + 多线程并行评估 |

**推荐配置**：

```python
from src.mopso import MOPSO_DT

mopso = MOPSO_DT(
    J=8, N_bin=3,
    evaluate_func=evaluate_func,
    N_P=50, T_max=200,
    w_strategy='standard',      # 标准惯性权重 (0.9→0.4)
    p_m_base=0.01,              # 1%基础变异率
    select_gb='crowding'        # 拥挤度加权选择
)
```

相比原始配置（legacy + random），Pareto解数量提升 **750%**，多样性范围提升 **160%**。

### 区域分解 (`src/decomposition.py`)

将复杂多边形（含空洞、凹顶点）分解为凸多边形并分配二进制编码，详见 `docs/decomposition_guide.md`。

### 坐标变换 (`src/coordinate_transform.py`)

将 [0,1]² 归一化坐标映射到任意凸多边形内的物理坐标。

### 评估模块 (`src/evaluation.py`)

- ECR（期望覆盖率）计算
- J_min（最小干扰功率密度）计算
- 雷达方程模型和A2G/G2G传播模型

### 辅助工具

| 模块 | 功能 |
|------|------|
| `benchmarks.py` | ZDT1/ZDT2/Schaffer标准测试函数 + 拐点检测 |
| `pareto_visualization.py` | Pareto前沿增强可视化（拐点标注、颜色梯度） |
| `experiment_runner.py` | 结构化实验框架（里程碑管理 + Markdown/JSON报告） |

## 算法流程

```
输入部署区域 (复杂多边形)
    ↓
区域分解 → 凸多边形 + 二进制编码
    ↓
MOPSO-DT 优化
  ├─ 初始化粒子群
  ├─ 迭代 t = 1..T_max:
  │   ├─ 计算动态参数 (w, p_m)
  │   ├─ 选择全局最优 gb (random/crowding)
  │   ├─ 更新连续变量 (PSO速度-位置)
  │   ├─ 更新二进制变量 (交叉+变异)
  │   └─ 评估 → 更新档案
  └─ 输出 Pareto 前沿
    ↓
坐标变换 [0,1]² → 物理坐标
    ↓
输出最优部署方案 (ECR vs J_min 权衡)
```

## A/B 对比结果

在 200km×200km, 8雷达, N_P=20, T_max=30 条件下的快速验证：

| 指标 | BASELINE (原始) | IMPROVED (改进) | 变化 |
|------|----------------|-----------------|------|
| Pareto解数量 | 4 | 34 | **+750%** |
| 运行时间 | 1.4s | 1.2s | -14% |
| 超体积(HV) | 0.0399 | 0.0498 | +25% |
| f2范围(多样性) | 0.0013 | 0.0048 | +160% |

## 详细文档

- `docs/mopso_manual.md` — MOPSO-DT技术手册
- `docs/decomposition_guide.md` — 区域分解算法详解
- `docs/PARETO_SOLUTIONS.md` — Pareto解生成过程说明

## 许可证

MIT License

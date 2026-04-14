# 部署区域分解与MOPSO优化算法

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

本项目包含部署区域分解算法和基于分解变换的多目标粒子群优化（MOPSO-DT）算法的完整实现。

## 项目结构

```
liziqun/
├── src/                      # 源代码
│   ├── decomposition.py          # 区域分解算法（论文Algorithm 1）
│   ├── mopso.py                  # MOPSO-DT多目标优化
│   ├── coord_transform.py        # 凸多边形坐标变换
│   ├── pso_basic.py              # 基础PSO算法
│   ├── optimization_utils.py     # 性能优化工具（Numba JIT加速）
│   ├── logger.py                 # 日志系统
│   ├── exceptions.py             # 异常处理
│   └── visualize.py              # 可视化模块
│
├── tests/                    # 测试文件
│   ├── test_mopso.py             # MOPSO测试套件
│   └── test_visualize.py         # 可视化测试
│
├── examples/                 # 使用示例
│   └── demo_decomposition.py     # 区域分解示例
│
├── figures/                  # 生成的图片
│   ├── 01_comparison.png
│   ├── 02_coord_transform.png
│   ├── 03_custom_polygon.png
│   ├── 04_decomposition.png
│   ├── 05_pareto_simple.png
│   ├── 06_pareto_test.png
│   ├── 07_step_by_step.png
│   └── 08_test_summary.png
│
├── docs/                     # 文档
│   ├── decomposition_guide.md    # 区域分解算法详解
│   └── mopso_manual.md           # MOPSO-DT技术手册
│
└── README.md                 # 本文件
```

## 快速开始

### 安装依赖

```bash
# 基础依赖
pip install numpy shapely matplotlib pytest

# 性能优化依赖（可选但推荐）
pip install numba
```

### 性能优化

本项目使用 **Numba JIT 编译** 加速核心计算，在以下函数中获得显著性能提升：

| 函数 | 加速比 |
|------|--------|
| 拥挤度距离计算 | **~40x** |
| Pareto 支配判断 | **~1.2x** |
| 二进制变量批量更新 | **~5x** |

启用方式：
```python
from src.mopso import MOPSO_DT

mopso = MOPSO_DT(
    J=10, N_bin=3, evaluate_func=your_func,
    use_batch_update=True  # 启用批量更新优化
)
```

运行性能测试：
```bash
python tests/test_performance.py
```

### 运行测试

```bash
# 运行所有 pytest 测试（推荐）
pytest tests/test_mopso_pytest.py -v

# 运行带覆盖率报告的测试
pytest tests/test_mopso_pytest.py -v --cov=src

# 运行原有测试
python tests/test_mopso.py
```

### 运行区域分解

```bash
# 运行示例
python examples/demo_decomposition.py

# 查看详细文档
cat docs/decomposition_guide.md
```

## 核心模块说明

### 1. 区域分解 (`src/decomposition.py`)

实现论文Algorithm 1，将复杂多边形分解为凸多边形：
- 处理不连通区域
- 消除空洞（两条线段切割）
- 凸分解（Hertel-Mehlhorn算法）
- 二进制编码分配

### 2. MOPSO优化 (`src/mopso.py`)

基于分解和变换的多目标粒子群优化：
- 混合变量处理（连续+二进制）
- Pareto非劣解维护
- 拥挤度距离计算
- 外部档案管理
- **完善的异常处理**和**日志记录**

### 3. 坐标变换 (`src/coord_transform.py`)

凸多边形内的坐标变换：
- [0,1]×[0,1] 到物理坐标的映射
- 支持任意凸多边形
- 基于shapely的几何运算

### 4. 日志系统 (`src/logger.py`)

统一的日志记录功能：
- 控制台输出
- 文件记录（自动创建logs/目录）
- 日志混入类 `LogMixin`

### 5. 异常处理 (`src/exceptions.py`)

自定义异常体系：
- `RadarDeploymentError`: 项目基类异常
- `InvalidParameterError`: 参数验证错误
- `EvaluationError`: 评估函数错误
- `DecompositionError`: 分解算法错误

## 使用示例

### MOPSO-DT优化（带日志和异常处理）

```python
from src.mopso import MOPSO_DT
from src.exceptions import InvalidParameterError, MOPSOError
import numpy as np
import logging

# 定义评估函数
def evaluate(Phi):
    # Phi: 决策变量矩阵 (J, 2+N_bin)
    coverage = np.mean(Phi[:, 0])
    interference = np.std(Phi[:, 1])
    return np.array([coverage, interference])

try:
    # 创建优化器（启用日志）
    mopso = MOPSO_DT(
        J=5,              # 5个雷达节点
        N_bin=3,          # 3位区域编码
        evaluate_func=evaluate,
        N_P=50,           # 50个粒子
        T_max=200,        # 200次迭代
        log_level=logging.INFO  # 日志级别
    )

    # 执行优化
    archive, stats = mopso.optimize()

    # 获取Pareto前沿
    cont, binary, objs = mopso.get_pareto_front()
    print(f"找到 {len(objs)} 个非劣解")

except InvalidParameterError as e:
    print(f"参数错误: {e}")
except MOPSOError as e:
    print(f"优化错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")
```

### 区域分解

```python
from src.decomposition import DeploymentRegionDecomposer
from shapely.geometry import Polygon

# 创建多边形
polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])

# 分解
decomposer = DeploymentRegionDecomposer()
convex_polys, codes, n_bits = decomposer.decompose(polygon)

print(f"分解为 {len(convex_polys)} 个凸多边形")
print(f"二进制编码位数: {n_bits}")
```

## 测试结果

所有测试已通过：
- ✅ 单元测试（支配关系、拥挤度、二进制更新、档案维护）
- ✅ Schaffer N.1测试（30个非劣解）
- ✅ ZDT1测试（50个非劣解，误差0.000000）
- ✅ 集成测试（坐标变换+MOPSO）
- ✅ 可视化测试

查看测试生成的图片：`figures/08_test_summary.png`

## 算法流程图

```
部署区域分解 + MOPSO-DT 完整流程:

┌─────────────────┐
│   输入部署区域   │
│  (复杂多边形)    │
└────────┬────────┘
         ▼
┌─────────────────┐
│  1. 区域分解     │
│  - 连通性处理    │
│  - 空洞消除      │
│  - 凸分解        │
│  - 二进制编码    │
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. MOPSO-DT    │
│  - 初始化粒子群  │
│  - 迭代优化      │
│  - Pareto档案   │
└────────┬────────┘
         ▼
┌─────────────────┐
│  3. 坐标变换     │
│  [0,1]→物理坐标  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  输出最优部署    │
│  Pareto非劣解集  │
└─────────────────┘
```

## 详细文档

- 区域分解算法详解：`docs/decomposition_guide.md`
- MOPSO-DT技术手册：`docs/mopso_manual.md`
- 源码注释：各模块内含详细中文注释

## 许可证

MIT License

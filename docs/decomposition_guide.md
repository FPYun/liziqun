# 部署区域分解算法 (Deployment Region Decomposition)

实现论文Algorithm 1的部署区域分解算法，将复杂多边形（含空洞、凹顶点或不连通区域）分解为凸多边形并分配二进制编码。

## 功能特性

- **处理不连通区域**：将MultiPolygon分解为连通分量
- **消除空洞**：使用两条线段切割方法消除多边形内部空洞
- **凸分解**：使用优化的Hertel-Mehlhorn算法（O(n log n)复杂度）
- **二进制编码**：为每个凸多边形分配唯一的二进制编码
- **严格连通性判断**：完善的多边形连通性检查

## 安装

### 环境要求

- Python 3.8+
- numpy
- shapely

### 安装依赖

```bash
pip install numpy shapely
```

### 可选依赖

```bash
# 三角剖分（推荐）
pip install scipy

# 可视化
pip install matplotlib
```

## 快速开始

### 基础用法

```python
from shapely.geometry import Polygon
from src.decomposition import DeploymentRegionDecomposer

# 创建部署区域
region = Polygon([(0, 0), (300, 0), (300, 300), (0, 300)])

# 创建分解器并执行分解
decomposer = DeploymentRegionDecomposer(verbose=False)
convex_polys, codes, n_bits = decomposer.decompose(region)

print(f"分解为 {len(convex_polys)} 个凸多边形")
print(f"使用 {n_bits} 位二进制编码")
```

### 在MOPSO-DT中使用

```python
from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import create_normalized_evaluate_function
from src.mopso import MOPSO_DT

# 区域分解
region = Polygon([(0, 0), (200, 0), (200, 200), (0, 200)])
decomposer = DeploymentRegionDecomposer(verbose=False)
polygons, codes, n_bits = decomposer.decompose(region)

# N_bin用于MOPSO编码
J = 8  # 雷达数量
evaluate_func = create_normalized_evaluate_function(
    task_points, radar_configs, polygons, J, n_bits
)

mopso = MOPSO_DT(J=J, N_bin=n_bits, evaluate_func=evaluate_func)
```

## API参考

### DeploymentRegionDecomposer类

#### 构造函数

```python
DeploymentRegionDecomposer(verbose: bool = True)
```

- `verbose`: 是否显示详细进度信息

#### decompose方法

```python
decompose(region: Union[Polygon, MultiPolygon]) -> Tuple[List[Polygon], Dict[int, str], int]
```

**参数:**
- `region`: 输入区域（Polygon或MultiPolygon）

**返回:**
- `convex_polygons`: 凸多边形列表
- `binary_codes`: 索引到二进制编码的映射字典
- `n_bits`: 所需的二进制位数 = ceil(log2(N_S))

## 算法说明

### 算法流程

```
输入: 复杂多边形（可能含空洞、凹顶点、不连通）
输出: (凸多边形列表, 二进制编码, 编码位数)

1. 处理不连通区域
   - 如果输入是MultiPolygon，分解为独立的多边形

2. 处理空洞区域
   - 从空洞边界顶点向外部边界引两条线段
   - 使用这些线段切割多边形，消除空洞

3. 凸分解（Hertel-Mehlhorn算法）
   - 对多边形进行三角剖分
   - 构建邻接关系（O(n)复杂度）
   - 合并相邻凸多边形

4. 二进制编码
   - 计算所需位数: N_bin = ceil(log2(N_S))
   - 为每个凸多边形分配唯一编码
```

### 复杂度分析

| 步骤 | 复杂度 | 说明 |
|-----|-------|------|
| 连通性处理 | O(n) | 边界分析 |
| 空洞消除 | O(h × n) | h为空洞数量 |
| 三角剖分 | O(n log n) | Delaunay三角剖分 |
| 凸分解 | O(n log n) | 优化的Hertel-Mehlhorn |
| **总计** | **O(n log n)** | n为总顶点数 |

## 性能

在Intel i7处理器上的性能测试结果：

| 区域大小 | 顶点数 | 平均耗时 | 凸多边形数 |
|---------|-------|---------|----------|
| 200km×200km | 4 | 0.0028s | 1 |
| 300km×300km | 4 | 0.0032s | 1 |
| 不规则凹形 | 10 | 0.0068s | 3 |
| 带空洞 | 20 | 0.015s | 7 |

## 参考文件

- `src/decomposition.py` — 核心算法实现
- `src/coordinate_transform.py` — 坐标变换模块
- `src/mopso.py` — MOPSO-DT优化器
- `src/evaluation.py` — 评估函数

---

**文档版本**: 1.1  
**最后更新**: 2026-05-04

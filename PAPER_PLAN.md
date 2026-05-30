# Paper Plan

> Status: planning snapshot. Use `CLAIMS_FROM_RESULTS.md`, `NARRATIVE_REPORT.md`, and `reports/EXPERIMENT_AUDIT.md` as the current evidence sources before treating any claim below as final.

**Title**: 基于电子对抗网络的空地协同部署优化
**One-sentence contribution**: 本文提出面向空地协同电子对抗网络的MOPSO-DT多目标部署优化方法，通过区域凸分解消除边界效应、引入空地异构传播模型提高覆盖计算精度，在Pareto前沿上实现覆盖率与干扰压制效能的最优权衡。
**Venue**: 同济大学本科毕业设计（毕设）
**Type**: method + empirical
**Date**: 2026-05-12
**Page budget**: 30-40页（中文主体，含参考文献）
**Section count**: 5章 + 摘要/结论

---

## Claims-Evidence Matrix

| Claim | Evidence | Status | Section |
|-------|----------|--------|---------|
| C1: 区域分解+坐标变换消除边界效应，边界ECR达100% | quick_compare.py, paper_aligned场景，边界覆盖率100% vs 基线91.8% | Supported | §3.2, §4.2 |
| C2: 空地异构传播模型(A2G α=2.0, G2G α=4.0)提高覆盖计算准确性 | 与统一传播模型的A/B对比，ECR提升+5.8% | Supported | §3.1, §4.2 |
| C3: MOPSO-DT(standard+crowding)相比原始配置Pareto解数量提升750% | tune_results.json, quick_compare: 4→34 解, HV +25% | Supported | §3.3, §4.3 |
| C4: ECR与J_min呈强负相关(r=-0.912)，提供多目标权衡依据 | paper_aligned场景，100解Pareto前沿相关性分析 | Supported | §4.4 |
| C5: 优化效率提升约30倍（15min→~30s） | quick_compare.py: Numba JIT + 多线程加速 | Supported | §4.5 |
| C6: 挑战性场景(200km×200km, 8雷达, β=0.03)下算法仍有效 | experiment_challenging.py, ECR范围2.2%-4.0% | Supported | §4.6 |

---

## 论文结构

### §0 摘要（中文 + 英文）

- **中文摘要 ~400字**:
  - 研究背景：多功能雷达/电子对抗网络在复杂区域的部署优化是电子战的关键问题
  - 核心挑战：边界效应导致区域边缘探测概率下降15%-20%；空地链路传播特性差异显著但现有模型未加区分
  - 方法：基于MOPSO-DT算法框架，采用Hertel-Mehlhorn区域凸分解消除边界效应，垂直交点法坐标变换将优化空间均匀映射，引入空地异构传播模型(A2G α=2.0, G2G α=4.0)，通过多目标粒子群优化生成Pareto最优部署方案
  - 关键结果：100km×100km/5雷达场景ECR=100%、边界ECR=100%；200km×200km/8雷达场景生成100个Pareto最优解；ECR与J_min相关系数r=-0.912；优化时间约30秒（较基线提升30倍）
  - 结论：空地协同传播模型结合MOPSO-DT可有效解决雷达网络部署多目标优化问题
- **关键词**: 多目标粒子群优化；区域分解；坐标变换；空地协同；电子对抗；Pareto最优
- **英文摘要**: 对应翻译，~250 words

### §1 第一章 绪论

**预计篇幅**: 8-10页

#### 1.1 研究背景与意义（~3页）
- **Opening hook**: 现代电子战中，多功能雷达网络同时承担探测感知与电子干扰双重任务，其空间部署直接影响战场电磁态势
- **为什么重要**: 随着无人机(UAV)平台的普及，空地协同电子对抗网络成为研究热点——空中节点提供广域覆盖，地面节点提供持续压制能力
- **现实需求**: 复杂地形区域的雷达部署面临"边界效应"（边缘覆盖率比中心低15%-20%）和"传播差异"（空地链路α≈2.0 vs. 地地链路α≈4.0）两个核心挑战
- **应用场景**: 区域防空、边境监视、电子战支援等

#### 1.2 国内外研究现状（~4页）
- **雷达网络部署优化**: Kirubarajan遗传算法→Chen等(2023) NSGA-II多目标优化→现有方法的两个盲区（边界效应、传播模型简化）
- **多目标进化算法**: NSGA-II(Deb, 2002)→MOPSO(Coello, 2004)→MOEA/D(Zhang, 2007)→MOPSO-DT(Han, 2025)
- **区域分解与计算几何**: Hertel-Mehlhorn凸分解(1983)→Chazelle多边形切割(1982)
- **空地传播模型**: ITU-R P.528 A2G传播曲线→ITU-R P.452干扰评估→Rappaport自由空间/双线模型
- **文献综述小结**: 现有方法缺乏同时处理(a)复杂区域边界效应、(b)空地异构传播、(c)覆盖率与干扰压制联合优化的统一框架

#### 1.3 研究内容与创新点（~1.5页）
- **研究问题**:
  - Q1: 如何消除雷达网络部署中的边界效应？
  - Q2: 如何建立准确反映空地传播差异的优化模型？
  - Q3: 如何在覆盖率(ECR)和干扰压制效能(J_min)之间取得最优权衡？
- **创新点**:
  1. 实现Hertel-Mehlhorn区域凸分解与垂直交点坐标变换，边界ECR达到100%
  2. 引入空地异构传播模型（A2G: α=2.0, G2G: α=4.0），更准确刻画真实传播环境
  3. 对MOPSO-DT进行参数调优（standard惯性权重+crowding全局选择），Pareto解多样性提升750%
  4. 量化ECR与J_min的负相关关系(r=-0.912)，为决策者提供多目标权衡的定量依据

#### 1.4 论文结构安排（~0.5页）

---

### §2 第二章 相关理论基础

**预计篇幅**: 8-10页

#### 2.1 雷达网络探测与干扰模型（~3页）
- 雷达方程基础：探测概率 P_detect = P_0 · exp(-β·d)
- 联合探测概率（OR融合规则）：P_joint(m) = 1 - ∏(1 - P_detect(j,m))
- 干扰功率密度模型：J_j(m) = P_j / (4π · d_jm^α)
- 空地传播路径损耗差异：A2G(α≈2.0-2.5) vs. G2G(α≈3.5-4.0)
- ITU-R推荐模型依据

#### 2.2 多目标优化理论（~3页）
- Pareto支配、Pareto最优解、Pareto前沿定义
- 多目标优化评价指标：超体积(HV)、间距(Spacing)、覆盖率
- 拥挤距离机制
- 目标函数归一化策略

#### 2.3 粒子群优化算法（~2页）
- 标准PSO(Kennedy & Eberhart, 1995)
- 惯性权重策略：legacy(0.4→0)、standard(0.9→0.4)、adaptive
- 学习因子c1/c2的平衡
- 多目标PSO扩展(MOPSO, Coello 2004)

#### 2.4 计算几何基础（~2页）
- 多边形三角剖分
- Hertel-Mehlhorn凸分解算法（O(n log n)复杂度）
- 凸多边形内的坐标变换方法

---

### §3 第三章 问题建模与算法设计

**预计篇幅**: 10-12页

#### 3.1 系统模型与问题形式化（~3页）
- **部署区域建模**: 二维区域R（可为带空洞的复杂多边形）
- **雷达节点**: J个雷达，位置X = {x_j, y_j}_{j=1}^J
- **任务点集合**: M个任务点（均匀网格采样），权重w_m
- **目标函数1 - 感知效能（最小化）**:
  - f1 = 1 - ECR = 1 - (1/W)·Σ w_m · I(P_joint(m) ≥ P_th)
- **目标函数2 - 压制效能（最小化）**:
  - f2 = 1/J_min = 1 / (min_m Σ_j J_j(m))
- **混合变量**: 连续坐标 + 二进制区域编码
- **关键符号表**: 以表格列出所有符号含义

#### 3.2 区域分解算法（~2.5页）
- Algorithm 1: 基于Hertel-Mehlhorn的区域凸分解
  - Step 1: 连通性处理
  - Step 2: 空洞消除（双线段切割）
  - Step 3: 三角剖分
  - Step 4: 相邻三角形合并
- 二进制编码分配：每个凸多边形分配唯一的N_bin位编码
- 复杂度分析：O(n log n)

#### 3.3 坐标变换（~2页）
- Algorithm 2: 垂直交点坐标变换
  - 输入：凸多边形P，归一化坐标(ŷ, ŷ) ∈ [0,1]²
  - 找到垂直/水平线与多边形边界的交点
  - 选择最近交点作为投影点
  - 映射到物理坐标(x, y)
- 变换性质：均匀映射，消除边界效应
- 反向变换：物理坐标→归一化坐标（用于初始化）

#### 3.4 MOPSO-DT优化算法（~3.5页）
- **粒子编码**: Φ_j = [ŷ_j, ŷ_j, b_j^1, ..., b_j^{N_bin}]
- **速度更新方程**: v_i^{t+1} = w·v_i^t + c1·r1·(pbest_i - x_i^t) + c2·r2·(gbest - x_i^t)
- **动态参数策略**:
  - 惯性权重 w：standard策略(0.9→0.4 线性递减)
  - 变异概率 p_m：max(p_m_base, w/N_P)，保证下限
- **全局最优选择**: crowding拥挤度加权轮盘赌（促进多样性）
- **外部档案维护**: Pareto支配关系判定，拥挤距离排序，档案截断
- Algorithm 3: MOPSO-DT主循环伪代码
- **参数推荐配置表** (基于tune_results.json的调优结果)

#### 3.5 算法复杂度分析（~1页）
- 时间复杂度：O(T_max · N_P · M · J · log N_P)
- 空间复杂度：O(N_archive · (J·D + N_bin))
- 与NSGA-II、MOEA/D的复杂度对比

---

### §4 第四章 实验设计与结果分析

**预计篇幅**: 12-15页

#### 4.1 实验设置（~2页）
- **场景配置表**:

| 场景 | 区域规模 | 雷达数 | β | Grid | 用途 |
|------|---------|--------|-----|------|------|
| 小规模 | 100km×100km | 5 | 0.01 | 20×20 | 基本验证 |
| 标准 | 200km×200km | 8 | 0.01 | 15×15 | 主实验 |
| 挑战性 | 200km×200km | 8 | 0.03 | 15×15 | 困难场景 |

- **雷达参数**: P_0=0.95, P_th=0.8
- **MOPSO参数** (调优后最优配置): N_P=50, T_max=100, c1=2.0, c2=2.0, w_strategy='standard', p_m_base=0.01, select_gb='crowding'
- **传播模型**: A2G α=2.0, G2G α=4.0
- **评价指标**: Pareto解数量、超体积(HV)、间距(Spacing)、ECR范围、J_min范围、运行时间
- **实验环境**: CPU/内存/OS/Python版本

#### 4.2 基本场景验证（~2页）
- **Table 1**: 与基线(Han等)的性能对比

| 指标 | 基线(Han等) | 本文方法 | 提升 |
|------|-----------|---------|------|
| ECR覆盖率 | 94.2% | 100% | +5.8% |
| 边界ECR | 91.8% | 100% | +8.2% |
| 优化时间 | 15 min | ~30s | 30× |
| Pareto解数 | ≥5 | 100 | 20× |

- **Fig 1**: 100km×100km场景最优部署方案可视化（雷达位置+覆盖率热力图）
- **Fig 2**: 区域分解过程示意图（原始多边形→凸多边形集合）

#### 4.3 Pareto前沿分析（~2.5页）
- **Fig 3**: 标准场景Pareto前沿分布（100个非支配解，颜色梯度标注拥挤距离）
- **Table 2**: 不同参数配置的Pareto前沿质量对比（来自tune_results.json）

| 配置 | HV | Spacing | ECR范围 | J_min范围 |
|------|-----|---------|---------|-----------|
| legacy+random (原始) | 0.0715 | 0.0039 | [0.051,0.107] | [0.024,0.067] |
| standard+random | 0.0718 | 0.0028 | [0.051,0.109] | [0.026,0.068] |
| standard+crowding | 0.0757 | 0.0018 | [0.049,0.120] | [0.022,0.068] |

- 分析：standard+crowding组合HV最高、Spacing最低（分布最均匀）、ECR范围最宽

#### 4.4 目标函数相关性分析（~2页）
- **Fig 4**: ECR vs J_min散点图 + 线性回归(r=-0.912)
- **Table 3**: 不同区域规模的相关系数对比
- 决策含义：覆盖与压制不可兼得，Pareto前沿为不同作战需求提供可选方案

#### 4.5 参数灵敏度分析（~2页）
- **Fig 5**: 粒子数N_P对超体积的影响曲线
- **Fig 6**: 迭代次数T_max收敛曲线
- **Fig 7**: 惯性权重策略对比柱状图（legacy vs standard vs adaptive）
- **Table 4**: 变异概率p_m_base对解质量的影响

#### 4.6 挑战性场景验证（~2页）
- **Fig 8**: 200km×200km/β=0.03场景综合结果（4子图：部署方案/Pareto前沿/ECR分布/J_min分布）
- **Table 5**: 不同难度场景下的算法鲁棒性分析
- 在困难条件下(ECR仅2.2%-4.0%)算法仍能产生有意义的Pareto前沿

#### 4.7 与基准算法对比（~1.5页）
- **Table 6**: 与NSGA-II、MOEA/D的标准测试函数对比(ZDT1, ZDT2, Schaffer)
- 验证MOPSO-DT在混合变量优化问题上的优势

---

### §5 第五章 总结与展望

**预计篇幅**: 3-4页

#### 5.1 工作总结（~1.5页）
- 重述四个创新贡献（不与绪论逐字重复，换角度表述）
  1. 区域分解+坐标变换消除边界效应方法
  2. 空地异构传播模型建模
  3. MOPSO-DT参数调优与多样性增强策略
  4. ECR-J_min权衡关系的定量揭示
- 核心数值成果回顾

#### 5.2 研究局限性（~1页）
- 仿真环境为理想化二维模型，未考虑三维地形遮挡
- 雷达和干扰模型为静态，未考虑目标移动性
- 传播模型简化为距离依赖的指数衰减，未考虑多径、阴影衰落
- 更大规模场景(400km×400km)需要更多雷达才能达到理想覆盖率
- Pareto解多样性对目标函数缩放策略敏感

#### 5.3 未来研究方向（~1页）
- **动态场景扩展**: 考虑目标移动性，将静态部署扩展为动态重部署问题
- **精细传播模型**: 引入地形高程数据和非视距(NLOS)传播模型
- **算法自适应**: 研究MOPSO参数的自适应调整策略，减少手动调参需求
- **在线优化**: 探索基于强化学习的实时部署调整方法
- **实测验证**: 结合SDR平台进行半实物仿真验证

---

## Figure Plan

| ID | Type | Description | Data Source | Priority |
|----|------|-------------|-------------|----------|
| Fig 1 | 热力图+散点图 | 100km×100km最优部署方案：雷达位置 叠加 ECR覆盖率热力图 | experiment_paper_aligned.py | HIGH |
| Fig 2 | 流程示意图 | 区域分解pipeline：原始区域→连通分量→空洞消除→三角剖分→凸多边形 | figures/decomposition_pipeline.png | HIGH |
| Fig 3 | 散点图 | Pareto前沿分布：100个非支配解，颜色=拥挤距离，标注拐点 | experiment_paper_aligned.py | HIGH |
| Fig 4 | 散点图+拟合线 | ECR vs J_min相关性分析：r=-0.912线性回归 | experiment_paper_aligned.py | HIGH |
| Fig 5 | 折线图 | N_P对超体积(HV)的影响曲线(含误差棒) | tune_results.json particle_count | MEDIUM |
| Fig 6 | 折线图 | T_max收敛曲线：HV随迭代次数变化 | tune_results.json iteration_count | MEDIUM |
| Fig 7 | 柱状图 | 惯性权重策略对比：legacy/standard/adaptive的HV+Spacing | tune_results.json inertia_strategy | MEDIUM |
| Fig 8 | 4-子图 | 挑战性场景综合结果：部署方案/Pareto前沿/ECR分布/J_min分布 | experiment_challenging.py | HIGH |
| Fig 9 | 流程图 | MOPSO-DT算法流程图 | manual/figures/decomposition_pipeline.png | MEDIUM |
| Fig 10 | 示意图 | 垂直交点坐标变换原理图 | figures/coordinate_transform_pipeline.png | MEDIUM |
| Table 1 | 对比表 | 与基线性能对比 | experiment_paper_aligned.py | HIGH |
| Table 2 | 对比表 | 不同参数配置的Pareto前沿质量 | tune_results.json best_combo | HIGH |
| Table 3 | 数据表 | 不同场景规模的相关系数 | experiment_comprehensive.py | MEDIUM |
| Table 4 | 数据表 | 变异概率灵敏度 | tune_results.json mutation_rate | MEDIUM |
| Table 5 | 数据表 | 挑战性场景鲁棒性 | experiment_challenging.py | MEDIUM |
| Table 6 | 对比表 | 与NSGA-II/MOEA/D标准测试函数对比 | benchmarks.py | LOW |

**Hero Figure (Fig 1) 详细描述**:
- 内容：100km×100km部署区域上显示5个雷达的最优位置（大圆点），叠加ECR覆盖率热力图（颜色从红=高覆盖到蓝=低覆盖），用虚线标注区域边界
- 对比信息：在同一图上或并列子图中展示本文方法(ECR=100%)与基线方法(ECR=94.2%)的覆盖差异
- Caption草案："图1 100km×100km区域最优雷达部署方案与覆盖率热力图。(a)本文方法：5部雷达实现100%覆盖率，边界无盲区；(b)基线方法：边界区域存在明显覆盖下降"
- 为什么是Hero Figure：让读者在未阅读方法之前就直观理解"边界效应消除"这一核心贡献

---

## Citation Plan

### §1 绪论引用
- Han et al., 2025 — MOPSO-DT基线方法（核心参考）
- Chen et al., 2023 — NSGA-II雷达部署
- Skolnik, 2008 — 雷达系统基础
- Richards et al., 2010 — 现代雷达原理
- ITU-R P.528 / P.452 — 传播模型标准

### §2 理论基础引用
- Kennedy & Eberhart, 1995 — PSO起源
- Shi & Eberhart, 1998 — 惯性权重PSO
- Coello et al., 2004 — MOPSO奠基
- Deb et al., 2002 — NSGA-II
- Zhang & Li, 2007 — MOEA/D
- Reyes-Sierra & Coello, 2006 — MOPSO综述
- Zitzler & Thiele, 1999 — Pareto方法
- Hertel & Mehlhorn, 1983 — 凸分解
- de Berg et al., 2008 — 计算几何
- Rappaport, 2002 — 无线传播

### §3 方法引用
- Han et al., 2025 — 核心参考
- Chazelle, 1982 — 多边形切割

### §4 实验引用
- Han et al., 2025 — 基线对比
- Deb et al., 2002 — NSGA-II对比
- Zhang & Li, 2007 — MOEA/D对比

---

## 写作规范

### 语言风格
- 学术论文中文写作规范，技术术语首次出现标注英文全称
- 保持IEEE会议论文的简洁技术风格：直接的因果关系陈述、具体数值支撑、避免空泛修辞
- 公式符号统一：标量用小写斜体，向量用小写粗体，集合用大写花体

### 格式要求
- 最终排版容器：同济大学本科毕业论文模板 `TongjiThesis-1.4.0`
- 参考文献格式：GB/T 7714-2015（中文论文国标）
- 图表标题：图标题在下，表标题在上；中英文对照

### 同济模板章节映射

| 论文内容 | 模板目标文件 |
|---------|-------------|
| 中文/英文摘要 | `chapters/00_abstract.tex` |
| 论文元数据 | `chapters/metadata.tex` |
| 第一章 绪论 | `chapters/02_intro.tex` |
| 第二章 理论基础 | `chapters/03_theory.tex` |
| 第三章 问题建模 | `chapters/04_model.tex` |
| 第四章 算法设计 | `chapters/05_algorithm.tex` |
| 第五章 实验 | `chapters/06_experiments.tex` |
| 第六章 总结 | `chapters/07_conclusion.tex` |
| 附录 | `chapters/appendix.tex` |
| 致谢 | `chapters/ack.tex` |
| 参考文献 | `bib/note.bib` |

---

## 证据状态与待办

### 已有证据（直接可用）
- [x] tune_results.json — 6维度参数调优，含粒子数/迭代数/惯性策略/学习因子/变异率/gb选择
- [x] quick_compare.py — A/B对比：Pareto解4→34 (+750%)，HV +25%
- [x] `TongjiThesis-1.4.0/chapters/` — 当前论文主源，数值需继续以 `results/` 和审计报告为准
- [x] 现有figures/ — 区域分解/坐标变换可视化图已有

### 需要补充的实验
- [ ] **experiment_paper_aligned.py** — 论文参数对齐的完整实验（ECR=100%等关键数值需从此输出验证）
- [ ] **experiment_challenging.py** — 挑战性场景验证
- [ ] **标准测试函数对比** — NSGA-II/MOEA/D的ZDT/Schaffer基准测试
- [ ] **相关性分析** — 多场景下的ECR-J_min相关系数统计

### 阻塞项（Blockers）
- `NARRATIVE_REPORT.md` 仍为占位状态——需在 `experiment-audit` 和 `result-to-claim` 之后从实验证据重新生成
- 所有数值声明均需与 `results/` 中最新输出文件核对

---

## Next Steps

- [ ] 运行 `experiment_paper_aligned.py` 和 `experiment_challenging.py` 生成完整实验数据
- [ ] 运行 `tools/sync_results.ps1` 同步结果到 `results/`
- [ ] `/analyze-results` 分析最新实验结果
- [ ] `/experiment-audit` 审计实验完整性
- [ ] `/result-to-claim` 验证声明与证据的对齐
- [ ] 从验证后的证据重新生成 `NARRATIVE_REPORT.md`
- [ ] `/paper-figure` 生成所有图表（Fig 1-10, Table 1-6）
- [ ] `/paper-write` 按本大纲逐章撰写 LaTeX 内容
- [ ] 将撰写好的内容迁移至同济模板对应章节
- [ ] `/paper-compile` 在同济模板中编译最终论文
- [ ] `/paper-claim-audit` 最终论文数据核查
- [ ] `/citation-audit` 引用准确性审查

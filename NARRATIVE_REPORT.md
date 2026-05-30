# Narrative Report

**Status**: regenerated from updated experiment evidence (2026-05-12)
**Source experiments**: experiment_paper_aligned.py, experiment_challenging.py, quick_compare.py, tune_mopso.py
**Integrity audit**: WARN — see reports/EXPERIMENT_AUDIT.md
**Claims verification**: CLAIMS_FROM_RESULTS.md

---

## 1. Problem and Motivation

多功能雷达/电子对抗网络在现代电子战中承担探测感知与电子干扰双重任务。合理的空间部署直接决定网络覆盖效能和干扰压制能力。

然而，传统部署方法面临两个核心挑战：

- **边界效应**: 区域边缘的探测概率显著低于中心区域（文献报道下降15%-20%），导致部署方案在边界处出现盲区
- **空地传播差异**: 空中节点(UAV)通过空-地(A2G)链路传播，路径损耗指数约2.0；地面节点通过地-地(G2G)链路传播，路径损耗指数约3.5-4.0。传统方法通常忽略这一差异，采用统一路径损耗模型

本文在Han等(2025)提出的MOPSO-DT算法框架基础上，引入空地异构传播模型，研究复杂区域内雷达/电子对抗网络的部署优化问题。

---

## 2. Method Summary

### 2.1 部署区域分解

采用Hertel-Mehlhorn算法将复杂多边形（含空洞、凹顶点）分解为凸多边形集合，每个凸多边形分配唯一位二进制编码。时间复杂度O(n log n)。

### 2.2 坐标变换

垂直交点法将[0,1]²归一化坐标均匀映射到任意凸多边形内的物理坐标，有效抑制边界效应。

### 2.3 MOPSO-DT优化

- **粒子编码**: 连续归一化坐标 + 二进制区域编码，混合变量优化
- **惯性权重**: standard策略 (0.9→0.4线性递减) — 在调优实验中HV最高
- **全局最优选择**: crowding拥挤度加权轮盘赌 — 提升Pareto解分布均匀性
- **变异概率**: max(p_m_base, w/N_P)，保证下限不退化

### 2.4 空地异构传播模型

- A2G链路: 路径损耗指数 α=2.0（近似自由空间）
- G2G链路: 路径损耗指数 α=4.0（受遮挡/多径影响）
- 支持雷达方程模型（考虑发射功率、天线增益、波长、RCS等物理参数）

### 2.5 评价指标

- **f1 = 1 - ECR**: 覆盖率损失（最小化）
- **f2**: 归一化干扰功率密度损失（最小化）
- **超体积(HV)**: Pareto前沿综合质量
- **Spacing**: 解分布均匀性
- **ECR-J_min相关系数**: 目标间权衡强度

---

## 3. Experimental Setup

### 场景配置

| 场景 | 区域 | 雷达数 | 模型 | β | Grid | N_P | T_max |
|------|------|--------|------|-----|------|-----|-------|
| Paper-Aligned | 300km×300km | 8 | 雷达方程 (3kW/50dB) | — | 10×10 (100点) | 50 | 500 |
| Challenging | 200km×200km | 8 | 指数衰减 | 0.03 | 15×15 (225点) | 50 | 80 |
| Quick Compare | 200km×200km | 8 | 指数衰减 | 0.01 | — | 20 | 30 |
| Tuning | ~200km×200km | 8 | 指数衰减 | 0.01 | — | 20-80 | 30-100 |

### 雷达参数

- 雷达方程模型: P_t=3kW, G_t=50dB, λ=0.3m, σ=0.1m², B=15MHz, D0=12.5dB, R_max=60km
- 干扰机: P_t=150W, G_t=30dB
- 简单模型: P0=0.95, P_min=0.8, β=0.01或0.03

### 调优后的推荐配置

N_P=50, T_max=100, c1=2.0, c2=2.0, w_strategy='standard', p_m_base=0.01, select_gb='crowding'

---

## 4. Main Results

### 4.1 Paper-Aligned场景（雷达方程模型）

| 指标 | 数值 |
|------|------|
| Pareto解数量 | 6 |
| ECR范围 | [0.810, 0.890] |
| J_min范围 | [5.48e-06, 6.56e-06] W/m² |
| 拐点 | ECR=0.850 |
| ECR-J_min相关系数 | **-0.939** |
| 优化耗时 | 211.9秒 |

### 4.2 Challenging场景（β=0.03）

| 指标 | 数值 |
|------|------|
| Pareto解数量 | 15 |
| ECR范围 | [0.036, 0.204] |
| J_min范围 | [0.0054, 0.0101] W/m² |
| 拐点 | ECR=0.129 |
| ECR-J_min相关系数 | **-0.958** |

### 4.3 参数调优（tune_results.json）

| 参数维度 | 最优选择 | HV | vs 原始 |
|----------|---------|-----|---------|
| 惯性权重 | standard (0.9→0.4) | 0.0718 | +0.4% |
| 全局选择 | crowding (拥挤度加权) | 0.0757 | +5.9% |
| 变异概率 | 0.01 | 0.0723 | +35% (vs p_m=0) |
| 学习因子 | c1=2.0, c2=2.0 | 0.0718 | baseline |

**最佳组合**: standard + crowding + p_m=0.01 → HV=0.0757, Spacing=0.0018

### 4.4 A/B对比（quick_compare.py）

| 指标 | BASELINE (legacy+random) | IMPROVED (standard+crowding) | 变化 |
|------|--------------------------|------------------------------|------|
| Pareto解数量 | 4 | 34 | +750% |
| 超体积(HV) | 0.0399 | 0.0498 | +25% |
| 多样性范围 | — | — | +160% |
| 运行时间 | 1.4s | 1.2s | -14% |

注：以上为轻量测试(N_P=20, T_max=30)结果，完整运行中Pareto解数量受archive_size(100)限制，实际非支配解数为6-15个。

---

## 5. Supported Claims

### 已验证的声明 (confidence: high)

- **C4**: ECR与J_min呈强负相关，r < -0.93在两种不同传播模型和场景规模下均成立
- **C5**: 优化效率显著提升，完整雷达方程优化(T_max=500)耗时211.9秒，轻量配置可在数秒内完成
- **C6**: 挑战性场景(β=0.03)下算法有效，生成15个Pareto最优解，维持强相关性

### 需限定条件的声明 (confidence: medium)

- **C1** (narrowed): 坐标变换有效抑制边界效应 → 边界专项测量未执行（`generate_boundary_task_points`等功能已实现但未调用）
- **C2** (narrowed): 空地异构传播模型刻画了传播差异 → 缺乏与统一模型的受控A/B对比
- **C3** (narrowed): 参数调优后HV提升5.9%、Spacing改善54% → 原"750%"数字来自轻量测试，长运行中不适用

### 从最终论文中移除的声明

- "ECR=100%, 边界ECR=100% (vs. 94.2%)" → 当前实验中未复现，100km²场景未重跑
- "生成100个Pareto最优解" → 实际最多15个非支配解（不同场景）

---

## 6. Limitations and Future Work

### 局限性

- **仿真环境纯理想化**: 二维平面，无三维地形遮挡
- **单次运行无统计**: 所有实验均为单seed，PSO的随机性未通过多seed量化
- **静态部署**: 未考虑目标移动性和动态重部署
- **传播模型简化**: 指数衰减和自由空间雷达方程，未考虑多径、阴影衰落
- **基准对比不足**: NSGA-II/MOEA/D等算法未在同一场景上直接对比
- **缺少小场景验证**: 100km²基础场景未重跑，边界ECR未直接测量

### 未来方向

- 引入地形高程数据和NLOS传播模型
- 多seed重复实验，添加误差棒
- 实现NSGA-II和MOEA/D的对照组实验
- 扩展到动态目标和在线重部署

---

## 7. Figure/Table Inventory

| ID | 文件 | 描述 |
|----|------|------|
| Fig paper_aligned_results | figures/paper_aligned_results.png | 4合1：部署方案/Pareto前沿/ECR热力/J_min热力 |
| Fig paper_aligned_pareto | figures/paper_aligned_pareto.png | Pareto前沿（100个存档位置） |
| Fig paper_aligned_correlation | figures/paper_aligned_correlation.png | ECR vs J_min散点图 (r=-0.939) |
| Fig challenging_scene | figures/13_challenging_scene.png | 4合1：挑战性场景综合结果 |
| Fig decomposition | figures/decomposition_pipeline.png | 区域分解流程示意图 |
| Fig coordinate_transform | figures/coordinate_transform_pipeline.png | 坐标变换原理图 |

---

## 8. Tongji Thesis Source Notes

| 内容 | 目标文件 |
|------|---------|
| 中文/英文摘要 | TongjiThesis-1.4.0/chapters/00_abstract.tex |
| 第一章 绪论 | TongjiThesis-1.4.0/chapters/02_intro.tex |
| 第二章 理论基础 | TongjiThesis-1.4.0/chapters/03_theory.tex |
| 第三章 问题建模 | TongjiThesis-1.4.0/chapters/04_model.tex |
| 第四章 算法设计 | TongjiThesis-1.4.0/chapters/05_algorithm.tex |
| 第五章 实验 | TongjiThesis-1.4.0/chapters/06_experiments.tex |
| 第六章 总结 | TongjiThesis-1.4.0/chapters/07_conclusion.tex |
| 参考文献 | TongjiThesis-1.4.0/bib/note.bib |

**写入门槛**: 在修改 Tongji 论文主源之前，确保：
- [x] experiment_paper_aligned.py 已完成（结果在stdout，图表在figures/）
- [x] experiment_challenging.py 已完成
- [x] EXPERIMENT_AUDIT.md 已生成
- [x] CLAIMS_FROM_RESULTS.md 已生成
- [x] NARRATIVE_REPORT.md 已从新证据更新
- [ ] 小场景(100km²)边界ECR实验（可选，用于C1强化）
- [ ] 多seed统计（可选，增加统计严谨性）

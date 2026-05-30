# Thesis Finalization Guide

本文件用于后续论文定稿，不在本次任务中直接修改论文正文。后续定稿时，应以当前项目代码、实验结果、图表和结构化数据为依据。

## 1. Finalization Principle

论文最终稿应满足：

- 每个核心数值都能追溯到 `results/`、实验日志或明确的图表生成脚本。
- 每个算法机制都能对应到 `src/` 中的实现。
- 每个图都能说明图意、来源和可复现性。
- 不把旧计划、旧草稿或历史 claim 当作事实。
- 对当前实验不支持的内容进行保守改写，而不是强行保留。

## 2. Strong Claims To Avoid

后续定稿时建议避免以下表述：

- “完全消除边界效应。”
- “MOPSO-DT 全面优于 NSGA-II、MOEA/D、SPEA2。”
- “Pareto 解数量稳定提升 750%。”
- “standard + crowding + p_m=0.01 是当前实验唯一最优配置。”
- “所有图表均已由本次实验完整复现。”

这些表述与本次验证结果存在冲突或证据不足。

## 3. Safer Supported Wording

可考虑使用以下方向：

- “通过区域分解与坐标变换，将复杂区域约束显式纳入部署编码与坐标映射过程。”
- “在测试场景中，ECR 与 `J_min` 呈现明显负相关，说明覆盖与压制能力之间存在权衡。”
- “在 Challenging 场景中，经典 MOEA 方法在部分 Pareto 指标上表现更强；本文方法的价值在于将复杂区域映射、异构传播评估和部署决策集成到统一流程。”
- “边界专项实验显示，坐标变换方案在 boundary ECR 上达到与 direct physical 搜索相同的均值，并高于 legacy MOPSO-DT 和 NSGA-II-DT，但 overall ECR 和 HV 并非最优。”
- “参数调优结果对随机性和实验设置敏感，最终推荐配置应以统一的复现实验结果为准。”

## 4. Chapter-Specific Guidance

### 摘要

摘要中的数值必须最后统一检查。建议只保留稳定事实：系统目标、方法组成、实验观察到的权衡、多算法对比的客观结论。

### 第 1 章 绪论

可保留研究背景、复杂区域、多功能节点和双目标部署动机。涉及“创新点”时要避免过强措辞，把贡献写成建模与系统集成、实验验证和适用边界说明。

### 第 2 章 理论基础

理论基础可以稳定保留。需要保证多目标优化、PSO、计算几何的描述服务于后文章节，不堆砌与项目无关的理论。

### 第 3 章 问题建模

应重点对齐 `src/evaluation.py`：

- 雷达配置参数。
- 探测概率。
- 干扰强度。
- ECR。
- `J_min`。
- 归一化目标。

如果使用物理单位或雷达方程参数，需确认与当前实验脚本一致。

### 第 4 章 算法设计

应对齐 `src/decomposition.py`、`src/coordinate_transform.py`、`src/mopso.py` 和 `src/baseline_algorithms.py`。算法流程可以保留，但要明确哪些是本文方法，哪些是公平对比基线。

### 第 5 章 实验

这是后续定稿最需要谨慎修改的章节：

- 多算法对比应客观呈现 MOEA/D、NSGA-II、SPEA2 的优势。
- 边界实验不能写成“边界效应完全消除”。
- 参数调优需根据本次最新 `results/tune_results.json` 重写或重新确认。
- 消融表必须按 `results/ablation_summary.json` 重写；当前传播模型、坐标变换和目标函数三张消融表均与最新结构化结果存在不一致，其中目标函数消融的“谁产生更多 Pareto 解”方向相反。
- `quick_compare.py` 只能作为快速 sanity check，不应作为最终主要结论。

### 第 6 章 总结

总结应强调：

- 完成了复杂区域部署建模和求解流程。
- 实现了区域分解、坐标变换、混合变量 MOPSO-DT 和多算法对比。
- 在当前测试场景中观察到覆盖与压制权衡。
- 方法存在适用边界，经典 MOEA 方法在部分指标上更强。

## 5. Suggested Next Steps Before Final Thesis Edits

1. 决定最终采用哪一组参数调优结果。
2. 如果坚持使用 `standard + crowding + p_m=0.01`，需要重新设计或说明与本次 `legacy + crowding + p_m=0.0` 最优结果的差异。
3. 用 `results/ablation_summary.json` 重写第 5 章三张消融表和对应解释，尤其是目标函数消融结论。
4. 明确哪些图是最终论文图，哪些只是辅助图。
5. 针对第 5 章逐表逐图重写实验结论。
6. 最后统一检查摘要、结论和创新点，确保它们不超过实验支撑范围。

## 6. Not Modified In This Task

本次没有主动修改：

- `TongjiThesis-1.4.3/chapters/*.tex`
- `TongjiThesis-1.4.3/bib/note.bib`
- 论文正文、摘要、图注、表格文字和结论内容

本次只新增说明、证据地图、定稿建议和验证摘要。

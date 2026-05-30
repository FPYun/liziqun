# Project System Explanation

本文件记录对 `liziqun` 当前有效项目内容的系统级理解，用于支撑后续毕设论文定稿。当前论文主源是 `TongjiThesis-1.4.3/`；`TongjiThesis-1.4.0/` 仅作为旧版本地论文容器保留对照。

## 1. Project Purpose

项目研究复杂部署区域内的多功能雷达/电子对抗网络协同部署优化。系统把部署问题建模为双目标优化：

- 最大化期望覆盖率 ECR，用于衡量任务点达到探测阈值的程度。
- 最大化最小等效干扰强度 `J_min`，用于衡量最薄弱任务点的压制能力。

代码将这两个任务指标转成最小化目标，输出 Pareto 非支配部署方案集。核心方法是 MOPSO-DT：区域分解和坐标变换负责处理复杂几何约束，MOPSO 负责搜索连续坐标与离散子区域编码组成的混合变量。

## 2. Repository Responsibilities

项目当前主要部分如下：

| 路径 | 责任 |
|---|---|
| `src/` | 核心算法库，包含区域分解、坐标变换、评价函数、MOPSO-DT、基线算法、指标和可视化。 |
| `experiments/` | 复现实验和论文支撑实验，包括参数调优、论文对齐实验、挑战场景、多算法对比和边界专项实验。 |
| `tests/` | 单元测试、集成测试、性能测试和实验协议测试。 |
| `tools/` | 图表生成、表格生成、PDF 检查、答辩材料生成和自动运行辅助脚本。 |
| `results/` | 结构化实验结果入口，当前包含 `algorithm_comparison.json`、`boundary_analysis.json`、`tune_results.json`。 |
| `reports/` | 审计报告和本次验证摘要。 |
| `figures/` | 实验和方法示意图的 PNG/SVG 源输出，部分图由脚本生成。 |
| `TongjiThesis-1.4.3/` | 当前论文草稿和最终写作容器，包含同济模板、章节、参考文献和论文实际引用的 PDF 图。 |
| `TongjiThesis-1.4.3/tables/` | 从外部论文模块归档的表格片段，当前主入口未直接引用，作为后续定稿素材保留。 |
| `TongjiThesis-1.4.3/figures/source/` | 从外部论文模块归档的可编辑源图和模板图资产，用于图形追溯，不直接作为正文引用对象。 |
| `TongjiThesis-1.4.0/` | 旧版本地论文容器，保留作对照，不再作为主源。 |
| `docs/` | 项目规则、本地工具说明、本次新增的系统说明和论文证据地图。 |

## 3. Core Runtime Flow

系统主流程可以概括为：

1. 输入部署区域、多功能节点数量、任务点、雷达/干扰参数。
2. `src.decomposition` 将复杂区域验证、修复、消孔、三角剖分并合并为凸子区域。
3. `src.coordinate_transform` 将粒子的归一化坐标 `(u, v)` 映射到目标凸多边形内部物理坐标。
4. `src.evaluation` 解码粒子，计算探测概率、ECR、干扰强度和归一化目标值。
5. `src.mopso` 使用 MOPSO-DT 更新连续坐标和二进制区域编码，维护外部非支配档案。
6. `src.metrics` 计算非支配过滤、HV、Spacing、拥挤距离和档案摘要。
7. `experiments/` 组织不同场景和算法配置，输出 JSON、PNG 或 PDF。
8. `tools/generate_comparison_figures.py` 根据 `results/` 生成论文对比图。
9. `TongjiThesis-1.4.3/` 引用图表和结果，作为后续论文定稿容器。

## 4. Core Code Understanding

### `src/decomposition.py`

该模块负责几何可行域处理。主要逻辑包括：

- `validate_polygon`、`fix_polygon`：检查输入多边形合法性，必要时尝试修复自交、空几何等问题。
- `is_polygon_connected`、`decompose_connected_components`：处理多组件几何。
- `eliminate_holes` 及内部递归函数：将带孔区域转为无孔多边形，便于后续剖分。
- `triangulate_polygon`：基于 Shapely 三角剖分生成初始小三角形。
- `convex_decomposition`：把三角形逐步合并为凸多边形。
- `assign_binary_codes`：给每个凸子区域分配二进制编码。
- `DeploymentRegionDecomposer`：封装完整流程，是实验和评价函数的主要入口。

在当前多数实验中，部署区域是矩形或 L 形区域，分解后可能只有 1 个凸区域，也可能有多个凸子区。论文中关于复杂区域约束处理的论述应基于该模块和边界专项实验，不应脱离实验结果宣称边界问题被完全消除。

### `src/coordinate_transform.py`

该模块把粒子内部的归一化坐标映射为真实空间坐标。核心思路是：

- 先计算凸多边形的 x 范围。
- 用 `u` 决定目标 x 坐标。
- 在该 x 位置求多边形垂直交线的 y 上下界。
- 用 `v` 在线段范围内插值得到 y 坐标。
- 用 `verify_point_in_polygon` 校验映射点是否在区域内。

该变换避免在外接矩形中大量采样后再剔除非法点，尤其适合复杂边界和非矩形区域。论文中关于坐标变换的图包括 overview、detail 和 pipeline 三类。

### `src/evaluation.py`

该模块是实验数值的核心来源。它定义：

- `RadarConfig`：节点功率、探测阈值、路径损耗、雷达方程参数、空地链路标记等。
- `TaskPoint`：任务点坐标和权重。
- 简化路径损耗模型：`path_loss_air_to_ground`、`path_loss_ground_to_ground`。
- 雷达方程模型：`calculate_reception_probability_radar_eq`、`calculate_jamming_power_radar_eq`。
- 批量矩阵计算：检测矩阵、干扰矩阵、CPU/GPU 转换。
- 指标计算：`calculate_ecr`、`calculate_jamming_density`、`calculate_boundary_ecr`。
- 粒子解码：`binary_to_polygon_index`、`decode_particle`。
- 评价函数工厂：`create_evaluate_function`、`create_normalized_evaluate_function`。

实验中的 ECR、`J_min`、边界 ECR、归一化目标值最终都要回到这个模块解释。

### `src/mopso.py`

该模块实现 MOPSO-DT。关键对象：

- `Particle`：保存连续坐标、速度、二进制区域编码、当前目标值和个体最优。
- `MOPSO_DT`：初始化粒子群，迭代更新连续变量和二进制变量，维护 Pareto 档案。

关键机制：

- 连续坐标使用 PSO 速度-位置更新。
- 二进制区域编码使用交叉和位翻转变异。
- 惯性权重支持 `legacy`、`standard`、`adaptive`。
- 全局引导解支持随机选择和拥挤距离加权选择。
- 外部档案通过支配关系和拥挤距离保持非支配性和多样性。

该模块是论文“算法设计”章的直接代码基础。

### `src/baseline_algorithms.py`

该模块为公平对比实验提供基线：

- `RandomSearchMO`
- `NSGA2_DT`
- `MOEAD_DT`
- `SPEA2_DT`

这些算法复用相同混合编码和评价函数，使 `compare_algorithms.py` 能在相同预算下比较 MOPSO-DT 与经典多目标方法。当前结果显示这些基线在若干指标上强于本文 MOPSO-DT，因此论文后续定稿必须避免“全面优于基线”的表述。

### `src/metrics.py`

该模块实现结果评价和档案维护：

- `filter_nondominated`
- `calculate_hypervolume_2d`
- `calculate_spacing`
- `truncate_by_crowding`
- `update_archive`
- `summarize_metric_records`

多算法对比、边界分析和论文图表中的 HV、Spacing、非支配解数量等都依赖这些指标。

### Visualization and Utilities

- `src/pareto_visualization.py`：增强 Pareto 前沿、代表性部署、收敛曲线和综合图。
- `src/region_visualizer.py`：区域、多边形分解、编码和步骤可视化。
- `src/grid_evaluator.py`：网格批量评估。
- `src/benchmarks.py`：Schaffer、ZDT 等标准多目标测试函数，以及膝点、极端点和代表性解抽样工具，主要用于算法行为验证。
- `src/optimization_utils.py`：Numba 加速支配判断、拥挤距离、二进制变量更新和决策矩阵构造。
- `src/cupy_gpu_fix.py`：处理 Windows CJK 路径下 CuPy 编译缓存问题。
- `src/exceptions.py`、`src/logger.py`：异常和日志体系。

## 5. Experiment Understanding

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `quick_compare.py` | 快速比较 legacy 与 improved MOPSO 配置。 | `figures/quick_compare_results.png`，控制台指标。 |
| `tune_mopso.py` | 多维参数调优，包括粒子数、迭代数、惯性策略、学习因子、变异率、gb 选择和组合搜索。 | `figures/tune_results.json` 和调优图。 |
| `experiment_paper_aligned.py` | 使用参考论文风格参数和雷达方程模型的主实验。 | `results/paper_aligned_results.json`，以及临时或论文目录中的 `paper_aligned_*.png/pdf` 图。 |
| `experiment_challenging.py` | 困难场景下的 MOPSO-DT 单算法实验。 | `results/challenging_scene_results.json`，以及临时或论文目录中的 `13_challenging_scene` 图。 |
| `compare_algorithms.py` | 相同预算下对比 ours、legacy、NSGA-II、MOEA/D、SPEA2、random。 | `results/algorithm_comparison.json`。 |
| `boundary_analysis.py` | L 形边界场景下比较 direct、legacy、NSGA-II、ours_transform。 | `results/boundary_analysis.json`。 |
| `ablation_core.py` | 消融实验框架，覆盖传播、坐标变换、归一化、区域和雷达数量等因素。 | 消融结果文件，当前需按后续定稿需求再核查。 |
| `experiment_comprehensive*.py` | 早期综合实验和快速版。 | 可作为历史辅助，不应优先支撑最终结论。 |

工具脚本中，`tools/generate_comparison_figures.py` 负责把 `results/*.json` 转成论文 PDF 图；`tools/generate_pipeline_figure.py` 负责重绘图 4.7 的 MOPSO-DT 迭代流程；`tools/generate_tables.py` 可从源码结构生成表格片段，当前已把外部模块中的表格片段归档到 `TongjiThesis-1.4.3/tables/`。

测试中，`test_baseline_algorithms.py`、`test_metrics.py`、`test_mopso*.py` 覆盖核心优化行为，`test_experiment_protocol.py` 检查多算法对比预算一致性，`test_performance.py` 提供性能基准入口，`test_gpu.py` 仅用于 GPU/CuPy 环境可用性检查。

## 6. Figures and Image Meaning

当前图片分为两类：方法示意图和实验结果图。

方法示意图：

- `fig_architecture`：系统架构，表达复杂区域、任务点、节点、评价函数和优化器之间的关系。
- `fig_inference`：评价/推理关系，表达部署方案如何进入探测和干扰计算。
- `fig_pipeline`：算法流程概要。
- `decomposition_pipeline`、`decomposition_variety`：区域分解过程和多种区域形态。
- `coordinate_transform_overview/detail/pipeline`：坐标变换的整体、细节和流程说明。

实验结果图：

- `paper_aligned_results`、`paper_aligned_pareto`、`paper_aligned_correlation`：论文对齐场景下的结果、Pareto 前沿和 ECR--`J_min` 关系。
- `13_challenging_scene`：挑战场景部署和结果图。
- `algorithm_pareto_overlay`、`algorithm_metrics_bars`、`runtime_quality_tradeoff`、`knee_deployment_comparison`：多算法对比图，由 `tools/generate_comparison_figures.py` 根据 `results/algorithm_comparison.json` 生成。
- `boundary_coverage_map`：边界专项实验图，由 `tools/generate_comparison_figures.py` 根据 `results/boundary_analysis.json` 生成。
- `tradeoff_fixed`：覆盖-压制权衡图，当前可作为展示图使用，但其生成链路需要在后续定稿前再次确认。

归档源资产：

- `TongjiThesis-1.4.3/figures/source/` 保存外部论文模块中当前项目缺少的 SVG、PNG、PDF 源图资产，用于后续重绘或追溯。
- `TongjiThesis-1.4.3/tables/` 保存外部论文模块中未被当前 `main.tex` 引用的自动生成表格片段，不参与当前 PDF 编译。

## 7. Current Evidence State

本次验证后，关键事实如下：

- 测试套件通过：47 passed，6 warnings。
- `quick_compare.py` 本轮显示 improved 配置运行更快且 HV 略高，但 Pareto 解数量少于 baseline，说明该脚本不应支撑“解数量必然大幅提升”的强结论。
- `tune_mopso.py` 本轮完整日志显示最佳组合为 `legacy + crowding + p_m_base=0.0`，HV 约 0.05245；这与旧文档中“standard + crowding + p_m=0.01”为最佳的说法存在冲突，后续定稿必须统一。
- `experiment_paper_aligned.py` 本轮得到 Pareto 解 7，ECR 范围 0.7800--0.8500，ECR--`J_min` 相关系数约 -0.9231。
- `experiment_challenging.py` 本轮得到 Pareto 解 10，ECR 范围 0.0311--0.2222，相关系数约 -0.968。
- `compare_algorithms.py` 本轮显示 MOEA/D 的平均 HV 最高，SPEA2 的 Spacing 最低，ours 运行时间较短但并非整体最优。
- `boundary_analysis.py` 本轮结果文件显示 ours_transform 与 direct_physical 的 boundary ECR 均值同为 0.15625，高于 legacy 和 NSGA-II；但 NSGA-II 的 overall ECR 和 HV 更高。

## 8. Thesis Source Understanding

`TongjiThesis-1.4.3/main.tex` 当前加载：

- `chapters/00_abstract.tex`
- `chapters/02_intro.tex`
- `chapters/03_theory.tex`
- `chapters/04_model.tex`
- `chapters/05_algorithm.tex`
- `chapters/06_experiments.tex`
- `chapters/07_conclusion.tex`
- `chapters/appendix.tex`
- `chapters/ack.tex`

论文草稿结构已经从原模板样例改成项目专用结构。本次任务不修改正文，只为后续定稿提供证据支撑。

## 9. Module-Level Reading Index

本节记录当前代码、实验、工具和测试的直接入口。它用于后续快速定位实现，不替代逐行阅读源码。

### Source Modules

| 模块 | 主要入口 | 在系统中的角色 |
|---|---|---|
| `src/decomposition.py` | `DeploymentRegionDecomposer` 定义于 `src/decomposition.py:734`，完整分解流程入口为 `src/decomposition.py:772` | 负责区域合法性检查、连通分量处理、空洞消除、三角剖分、凸合并和二进制编码，是复杂部署区域进入优化器前的几何预处理层。 |
| `src/coordinate_transform.py` | 坐标变换入口 `src/coordinate_transform.py:152`，点合法性检查 `src/coordinate_transform.py:219` | 把粒子的归一化坐标映射到指定凸子区域内的物理坐标，避免优化循环中频繁生成非法点。 |
| `src/evaluation.py` | 配置对象 `src/evaluation.py:79`、任务点 `src/evaluation.py:108`、ECR `src/evaluation.py:464`、`J_min` `src/evaluation.py:512`、归一化评估 `src/evaluation.py:900` | 统一承载探测概率、干扰强度、粒子解码、ECR、`J_min` 和优化目标转换；当前关键实验优先使用归一化评估入口。 |
| `src/mopso.py` | `Particle` 定义于 `src/mopso.py:37`，`MOPSO_DT` 定义于 `src/mopso.py:70`，主流程 `src/mopso.py:199` | 实现 MOPSO-DT 的粒子初始化、连续变量更新、二进制变量更新、非支配档案维护和 Pareto 解输出。 |
| `src/optimization_utils.py` | 支配判断 `src/optimization_utils.py:318`、拥挤距离 `src/optimization_utils.py:335`、二进制批量更新 `src/optimization_utils.py:351` | 为 MOPSO-DT 和基线算法提供可选 Numba 加速的核心算子。 |
| `src/metrics.py` | 非支配过滤 `src/metrics.py:19`、HV `src/metrics.py:43`、Spacing `src/metrics.py:72`、指标汇总 `src/metrics.py:144` | 负责实验结果评价、档案维护辅助和 JSON 汇总统计。 |
| `src/baseline_algorithms.py` | 基类 `src/baseline_algorithms.py:29`、Random `src/baseline_algorithms.py:127`、NSGA-II `src/baseline_algorithms.py:140`、MOEA/D `src/baseline_algorithms.py:203`、SPEA2 `src/baseline_algorithms.py:243` | 在同一混合编码和同一评价函数下提供多目标优化基线，支撑第五章公平比较。 |
| `src/grid_evaluator.py` | `GridEvaluator` 定义于 `src/grid_evaluator.py:18`，综合评价入口 `src/grid_evaluator.py:303` | 提供网格化覆盖和干扰评估能力，当前更像辅助评价器，不是主实验入口。 |
| `src/benchmarks.py` | Schaffer `src/benchmarks.py:14`、ZDT1 `src/benchmarks.py:26`、代表性解抽样 `src/benchmarks.py:111` | 提供标准多目标测试函数和代表性解筛选工具，主要用于算法行为测试与可视化辅助。 |
| `src/pareto_visualization.py` | Pareto 图 `src/pareto_visualization.py:18`、部署图 `src/pareto_visualization.py:73`、综合图 `src/pareto_visualization.py:170` | 提供早期或辅助可视化能力；论文正式图目前主要由 `tools/generate_comparison_figures.py` 生成。 |
| `src/region_visualizer.py` | 分解过程图 `src/region_visualizer.py:56`、细节图 `src/region_visualizer.py:190`、逐步图 `src/region_visualizer.py:338` | 用于解释区域分解过程和几何处理，不直接产生当前主 PDF 中全部图。 |
| `src/experiment_runner.py` | `ExperimentRunner` 定义于 `src/experiment_runner.py:20`，报告生成 `src/experiment_runner.py:110` | 早期实验编排辅助类；当前关键实验直接由 `experiments/*.py` 脚本组织。 |
| `src/exceptions.py` | 项目异常基类 `src/exceptions.py:10`，MOPSO 异常 `src/exceptions.py:81`，评估异常 `src/exceptions.py:97` | 定义可读的领域异常，支撑日志和错误定位。 |
| `src/logger.py` | 日志初始化 `src/logger.py:13`，`LogMixin` `src/logger.py:79` | 为优化器和工具提供统一日志接口。 |
| `src/cupy_gpu_fix.py` | 修复入口 `src/cupy_gpu_fix.py:70` | 处理 Windows 中文/emoji 路径下 CuPy 缓存路径问题，是环境兼容层。 |

### Experiment Scripts

| 脚本 | 关键入口 | 当前论文证据地位 |
|---|---|---|
| `experiments/quick_compare.py` | 配置运行 `experiments/quick_compare.py:26`，图生成 `experiments/quick_compare.py:121` | 快速 sanity check；结果有随机性，不宜单独支撑强结论。 |
| `experiments/tune_mopso.py` | 问题实例 `experiments/tune_mopso.py:124`，单次实验 `experiments/tune_mopso.py:155`，全量运行 `experiments/tune_mopso.py:315` | 支撑参数敏感性和推荐配置讨论；当前 `results/tune_results.json` 是主要证据。 |
| `experiments/experiment_paper_aligned.py` | 论文参数配置 `experiments/experiment_paper_aligned.py:65`，主实验 `experiments/experiment_paper_aligned.py:106`，摘要保存 `experiments/experiment_paper_aligned.py:449` | 支撑论文对齐场景图表，当前已写出 `results/paper_aligned_results.json`。 |
| `experiments/experiment_challenging.py` | 主实验 `experiments/experiment_challenging.py:57`，可视化 `experiments/experiment_challenging.py:154`，摘要保存 `experiments/experiment_challenging.py:227` | 支撑 Challenging 场景图表，当前已写出 `results/challenging_scene_results.json`。 |
| `experiments/compare_algorithms.py` | 场景构建 `experiments/compare_algorithms.py:82`，统一预算 `experiments/compare_algorithms.py:149`，单方法运行 `experiments/compare_algorithms.py:321` | 第五章多算法对比的主证据来源，输出 `results/algorithm_comparison.json`。 |
| `experiments/boundary_analysis.py` | 边界场景 `experiments/boundary_analysis.py:47`，归档分析 `experiments/boundary_analysis.py:196`，结果保存 `experiments/boundary_analysis.py:297` | 第五章边界专项实验的主证据来源，输出 `results/boundary_analysis.json`。 |
| `experiments/ablation_core.py` | 总入口 `experiments/ablation_core.py:38`，传播/变换/归一化/区域/节点数消融分别从 `experiments/ablation_core.py:94`、`experiments/ablation_core.py:141`、`experiments/ablation_core.py:199`、`experiments/ablation_core.py:234`、`experiments/ablation_core.py:277` 开始 | 提供消融框架；当前已生成 `results/ablation_*.npz` 和 `results/ablation_summary.json`，但论文表格仍需逐项核对。 |
| `experiments/experiment_comprehensive.py` | 大区域测试 `experiments/experiment_comprehensive.py:38` | 早期综合实验，当前只作历史辅助。 |
| `experiments/experiment_comprehensive_fast.py` | 快速综合测试 `experiments/experiment_comprehensive_fast.py:29` | 早期快速实验，当前只作历史辅助。 |

### Tooling and Tests

| 项目 | 入口 | 学习结论 |
|---|---|---|
| `tools/generate_comparison_figures.py` | 多算法前沿图 `tools/generate_comparison_figures.py:136`、指标柱状图 `tools/generate_comparison_figures.py:175`、边界图 `tools/generate_comparison_figures.py:259`、主入口 `tools/generate_comparison_figures.py:348` | 当前论文多算法和边界 PDF 图的主要生成脚本。 |
| `tools/generate_pipeline_figure.py` | 主入口 `tools/generate_pipeline_figure.py:55` | 当前图 4.7 的重绘脚本。 |
| `tools/generate_tables.py` | 模型参数表 `tools/generate_tables.py:165`、核心机制表 `tools/generate_tables.py:234`、主入口 `tools/generate_tables.py:354` | 从源码默认参数生成表格片段，当前默认输出到 `TongjiThesis-1.4.3/tables/`。 |
| `tools/summarize_ablation_results.py` | 汇总入口 `tools/summarize_ablation_results.py:35` | 把 `results/ablation_*.npz` 转换为可读的 `results/ablation_summary.json`，便于论文表格核对。 |
| `tools/sync_results.ps1` | 同步计划起于 `tools/sync_results.ps1:23`，复制逻辑位于 `tools/sync_results.ps1:54` | 把 `figures/` 或根目录中的实验 JSON 同步到 `results/`；可用于补齐 Paper-Aligned 和 Challenging 的结构化结果。 |
| `tools/run_4h_thesis_autorun.ps1` | 参数定义 `tools/run_4h_thesis_autorun.ps1:1`，staging 安全检查 `tools/run_4h_thesis_autorun.ps1:30` | 长时间自动跑实验/审查的辅助脚本，默认使用 staging 防止直接污染主目录。 |
| `tools/check_pdf.ps1` | 当前路径写死在 `tools/check_pdf.ps1:1` | 该脚本仍指向旧 `paper\figures`，属于遗留路径；使用前应改为当前 `TongjiThesis-1.4.3/figures` 或改为参数化。 |
| `tests/test_metrics.py` | HV 测试 `tests/test_metrics.py:31`，Spacing 测试 `tests/test_metrics.py:39` | 直接覆盖第五章结果指标的核心计算。 |
| `tests/test_experiment_protocol.py` | 预算一致性测试 `tests/test_experiment_protocol.py:13` | 覆盖多算法对比的公平预算约束。 |
| `tests/test_baseline_algorithms.py` | 基线档案契约 `tests/test_baseline_algorithms.py:28`，固定种子复现 `tests/test_baseline_algorithms.py:53` | 覆盖基线算法输出结构和可复现性。 |
| `tests/test_mopso_pytest.py` | 参数校验从 `tests/test_mopso_pytest.py:65` 开始，核心功能从 `tests/test_mopso_pytest.py:107` 开始 | 覆盖 MOPSO-DT 参数、决策矩阵、支配关系、拥挤距离和运行契约。 |
| `tests/test_mopso.py` | 支配关系 `tests/test_mopso.py:124`、拥挤距离 `tests/test_mopso.py:166`、二进制更新 `tests/test_mopso.py:204`、集成测试 `tests/test_mopso.py:392` | 更偏脚本式的算法行为验证和可视化测试。 |
| `tests/test_performance.py` | 微基准从 `tests/test_performance.py:65` 开始，端到端基准从 `tests/test_performance.py:144` 开始 | 用于验证加速算子和批量更新带来的性能表现。 |
| `tests/test_gpu.py` | CuPy 检查 `tests/test_gpu.py:31` | 环境可用性检查，不是论文结论证据。 |

## 10. Repository Coverage Audit

本节记录当前仓库学习覆盖状态。结论是：核心源码、关键实验、论文主源和主要结果文件已经纳入学习文档；少数辅助脚本属于旧路径、答辩材料或交互式可视化工具，不能直接作为论文结论证据。

### Covered Core Areas

| 范围 | 覆盖状态 | 说明 |
|---|---|---|
| `src/*.py` | 已覆盖 | 当前扫描到的所有源码模块均已在“Source Modules”中建立职责说明。 |
| `experiments/*.py` | 已覆盖 | 当前扫描到的全部实验脚本均已在“Experiment Scripts”中标注证据地位。 |
| `results/*.json` | 已覆盖 | `algorithm_comparison.json`、`boundary_analysis.json`、`tune_results.json` 已进入证据地图；`results/README.md:1` 说明 `results/` 是结构化实验输出入口。 |
| `TongjiThesis-1.4.3/` | 已覆盖 | 当前论文主源、章节结构、图表和证据边界已经在本文件与 `docs/THESIS_EVIDENCE_MAP.md` 中记录。 |
| `docs/THESIS_MIGRATION_RULES.md` | 已覆盖 | 该文件在 `docs/THESIS_MIGRATION_RULES.md:5` 明确 `TongjiThesis-1.4.3/` 为优先论文源，防止恢复 `paper/`、`paper-new/` 或 `tongji_thesis/`。 |
| `docs/TONGJI_TEMPLATE_HANDOFF.md` | 已覆盖 | 该文件在 `docs/TONGJI_TEMPLATE_HANDOFF.md:18` 记录新版模板主源和外部模板交接规则。 |
| `docs/LOCAL_TOOLING.md` | 已覆盖 | 该文件在 `docs/LOCAL_TOOLING.md:1` 记录被删除的 `.aris/`、`.claude/`、`.vscode/` 配置迁移说明。 |
| `docs/THESIS_FINALIZATION_GUIDE.md` | 已覆盖 | 该文件记录后续论文定稿原则、强主张禁用清单和章节级精修方向，是 `docs/THESIS_EVIDENCE_MAP.md` 的行动化补充。 |

### Auxiliary or Legacy Files

| 文件 | 当前作用 | 学习结论 |
|---|---|---|
| `tests/test_visualize.py` | 交互式区域分解可视化示例；入口菜单位于 `tests/test_visualize.py:171`。 | 文件名以 `test_` 开头，但主要是手动生成图片的演示脚本，不是当前自动化测试和论文结论主证据。 |
| `tools/fix_pdf_figures.py` | 旧论文图 PDF 清理脚本；路径写死到 `paper/figures`，见 `tools/fix_pdf_figures.py:11`。 | 当前主论文目录已迁移到 `TongjiThesis-1.4.3/`，该脚本属于遗留维护工具，使用前必须改路径或参数化。 |
| `tools/remove_images.py` | 旧论文 PDF 去图脚本；路径写死到 `paper/main.pdf`，见 `tools/remove_images.py:12`。 | 当前不应直接运行，除非先改为新版论文路径；它不是项目实验或论文证据生成链路。 |
| `tools/generate_defense_ppt.py` | 生成答辩 PPT、讲稿、证据表和图片来源说明，输出目录为 `reports/defense_ppt`，见 `tools/generate_defense_ppt.py:16`。 | 属于答辩材料生成工具，不是论文主源；脚本内仍出现旧 `TongjiThesis-1.4.0` 字样，后续若再生成答辩材料应先更新为 `TongjiThesis-1.4.3`。 |
| `tools/check_pdf.ps1` | PDF 图像检查脚本。 | 已知仍指向旧 `paper\figures`，当前只作为遗留脚本记录。 |

### Reports and Logs

| 文件或目录 | 当前作用 | 学习结论 |
|---|---|---|
| `reports/EXPERIMENT_AUDIT.md` | 实验审计报告，整体结论为 WARN，见 `reports/EXPERIMENT_AUDIT.md:7`。 | 可用于识别证据风险；其中旧 `paper/sections` 的不一致记录只说明历史草稿问题，不能覆盖当前 `TongjiThesis-1.4.3/` 的最新审计。 |
| `reports/EXPERIMENT_AUDIT.json` | 审计报告的结构化版本。 | 作为机器可读风险记录保留。 |
| `reports/VALIDATION_RUN_SUMMARY.md` | 本轮项目测试、关键实验、图表生成和论文编译摘要。 | 是当前学习任务的主要运行证据之一；Paper-Aligned、Challenging 和消融实验现在均已有 `results/` 下结构化输出。 |
| `reports/validation_logs/20260527_081434/` | 保存 pytest、实验、图表生成和编译日志。 | 日志可追溯运行过程；定稿引用具体数值时仍应优先使用 `results/` 中的结构化结果。当前日志包括 `pytest.log`、`quick_compare.log`、`tune_mopso.log`、`experiment_paper_aligned.log`、`experiment_challenging.log`、`compare_algorithms.log`、`boundary_analysis.log`、`generate_comparison_figures.log`、`compile_xelatex1.log`、`compile_biber.log`、`compile_xelatex2.log`、`compile_xelatex3.log`、`static_code_map.json`；边车文件包括 `pytest.meta.txt`、`quick_compare.meta.txt`、`tune_mopso.meta.txt`、`experiment_paper_aligned.meta.txt`、`experiment_challenging.meta.txt`、`compare_algorithms.meta.txt`、`boundary_analysis.meta.txt`、`generate_comparison_figures.meta.txt`、`compile_xelatex1.meta.txt`、`compile_biber.meta.txt`、`compile_xelatex2.meta.txt`、`compile_xelatex3.meta.txt`。 |
| `reports/README.md` | 说明 `reports/` 应存放审计和复核输出，见 `reports/README.md:1`。 | 该目录是风险和审计材料入口，不是实验原始结构化结果入口。 |

### Remaining Learning Gaps

| 缺口 | 影响 | 后续动作 |
|---|---|---|
| 消融结果已经补入 `results/`，但尚未逐项对照论文表格 | 第五章消融表已有结构化证据基础，但仍不能自动证明论文表格完全一致。 | 使用 `results/ablation_summary.json` 与 `TongjiThesis-1.4.3/chapters/06_experiments.tex` 的消融表逐项核对；必要时再调整正文或表格。 |
| Paper-Aligned 与 Challenging 已补充结构化 JSON | 该缺口已基本闭合，但图像文件仍可能存在根目录 PNG 与论文 PDF 不完全同步的问题。 | 后续若重新生成论文图，应统一输出位置并记录 PNG/PDF 转换链路。 |
| `tradeoff_fixed.pdf` 未定位到生成脚本和依赖数据 | 图 5 中节点数量权衡说明证据较弱。 | 补生成脚本/数据，或在论文中降格为示意图。 |
| 少数工具仍写死旧 `paper/` 或 `TongjiThesis-1.4.0/` 路径 | 误运行可能生成旧目录产物。 | 若后续需要使用这些工具，先统一改为 `TongjiThesis-1.4.3/` 或改为命令行参数。 |

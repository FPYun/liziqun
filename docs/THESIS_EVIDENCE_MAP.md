# Thesis Evidence Map

本文件把当前论文草稿内容与项目证据建立映射。它不是论文审稿结论，也不是终稿修改稿；它用于后续定稿时判断哪些内容有项目支撑。

## 1. Evidence Sources

| 证据源 | 状态 | 用途 |
|---|---|---|
| `src/` | 已阅读结构和核心逻辑 | 支撑方法、模型、算法实现描述。 |
| `experiments/` | 已重新运行关键实验 | 支撑实验设置、场景、参数和结果来源。 |
| `results/algorithm_comparison.json` | 本次刷新 | 支撑多算法对比。 |
| `results/boundary_analysis.json` | 本次刷新 | 支撑边界专项实验。 |
| `results/tune_results.json` | 已由本次 `figures/tune_results.json` 同步 | 支撑参数调优结论。 |
| `reports/EXPERIMENT_AUDIT.*` | 现有审计材料 | 支撑证据风险识别。 |
| `TongjiThesis-1.4.3/figures/*.pdf` | 当前新版模板论文引用图表目录 | 支撑论文图表。 |
| `TongjiThesis-1.4.3/figures/source/` | 已归档外部模块中当前项目缺少的源图资产 | 用于图形追溯，不直接证明正文结论。 |
| `TongjiThesis-1.4.3/tables/` | 已归档外部模块表格片段 | 当前主入口未引用，可作为后续定稿素材。 |
| `reports/validation_logs/20260527_081434/` | 本次本地日志 | 保存测试、实验和编译命令输出。 |

## 2. Chapter-to-Evidence Mapping

| 论文章节 | 当前主题 | 主要项目证据 |
|---|---|---|
| 摘要 | 问题、方法、实验结果摘要 | 应最终引用 `results/` 中确认后的核心数值。 |
| 第 1 章 绪论 | 背景、研究现状、研究内容 | 文献和项目动机；方法事实来自 `src/` 与实验设计。 |
| 第 2 章 相关理论基础 | 多目标优化、PSO、计算几何 | `src/mopso.py`、`src/metrics.py`、`src/decomposition.py`。 |
| 第 3 章 问题建模 | 探测、干扰、目标函数 | `src/evaluation.py`、`src/grid_evaluator.py`。 |
| 第 4 章 算法设计 | 区域分解、坐标变换、MOPSO-DT、对比协议 | `src/decomposition.py`、`src/coordinate_transform.py`、`src/mopso.py`、`src/baseline_algorithms.py`。 |
| 第 5 章 实验 | 参数、对比、边界、调优、讨论 | `experiments/*.py`、`results/*.json`、`tools/generate_comparison_figures.py`。 |
| 第 6 章 总结 | 工作总结、局限和展望 | 应基于已验证结果保守总结。 |

## 3. Formula and Implementation Trace

| 论文公式/方法点 | 论文位置 | 源码证据 | 一致性结论 |
|---|---|---|---|
| HV 超体积 | `TongjiThesis-1.4.3/chapters/03_theory.tex:40` | `src/metrics.py:43`--`src/metrics.py:69` | 源码实现二维最小化前沿的精确支配超体积，并按非支配解和参考点裁剪；与论文中作为解集质量评价指标的用法一致。 |
| Spacing 间距 | `TongjiThesis-1.4.3/chapters/03_theory.tex:49` | `src/metrics.py:72`--`src/metrics.py:89` | 源码使用最近邻 L1 距离并计算样本标准差；可支撑论文中“分布均匀性”含义。 |
| 拥挤距离与档案截断 | `TongjiThesis-1.4.3/chapters/03_theory.tex:58` | `src/optimization_utils.py:335`--`src/optimization_utils.py:348`、`src/metrics.py:92`--`src/metrics.py:120`、`src/mopso.py:621`--`src/mopso.py:675` | 源码中拥挤距离既用于有限档案截断，也用于 `crowding` 领导者选择；与第四章算法描述一致。 |
| PSO 连续变量更新 | `TongjiThesis-1.4.3/chapters/03_theory.tex:100`--`TongjiThesis-1.4.3/chapters/03_theory.tex:102`、`TongjiThesis-1.4.3/chapters/05_algorithm.tex:137` | `src/mopso.py:729`--`src/mopso.py:768` | 源码使用惯性项、个体最优项和全局最优项更新速度，再更新归一化坐标并裁剪到 `[0,1]`；与论文公式一致。 |
| 二进制编码交叉与变异 | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:149`、`TongjiThesis-1.4.3/chapters/05_algorithm.tex:158` | `src/mopso.py:770`--`src/mopso.py:829`、`src/optimization_utils.py:351`--`src/optimization_utils.py:380` | 源码按 `p_c` 在个体最优和全局最优二进制位之间继承，并按 `p_m` 独立变异；与算法 4.3 的混合变量更新流程一致。 |
| Hertel-Mehlhorn 风格凸分解 | `TongjiThesis-1.4.3/chapters/03_theory.tex:126`--`TongjiThesis-1.4.3/chapters/03_theory.tex:128`、`TongjiThesis-1.4.3/chapters/05_algorithm.tex:38` | `src/decomposition.py:474`--`src/decomposition.py:535`、`src/decomposition.py:604`--`src/decomposition.py:690`、`src/decomposition.py:820`--`src/decomposition.py:849` | 源码先三角剖分，再尝试合并相邻三角形为凸多边形，最后分配二进制编码；支撑论文中的区域分解流程。 |
| 垂直交点坐标变换 | `TongjiThesis-1.4.3/chapters/03_theory.tex:139`--`TongjiThesis-1.4.3/chapters/03_theory.tex:150`、`TongjiThesis-1.4.3/chapters/05_algorithm.tex:86` | `src/coordinate_transform.py:78`--`src/coordinate_transform.py:149`、`src/coordinate_transform.py:152`--`src/coordinate_transform.py:216`、`src/evaluation.py:573`--`src/evaluation.py:625` | 源码按凸多边形全局 `x` 边界映射横坐标，再沿垂线求局部 `y` 边界并插值；`decode_particle` 使用该函数把粒子解码为物理位置。 |
| 简化探测概率与干扰强度 | `TongjiThesis-1.4.3/chapters/04_model.tex:59`、`TongjiThesis-1.4.3/chapters/04_model.tex:95` | `src/evaluation.py:156`--`src/evaluation.py:188`、`src/evaluation.py:191`--`src/evaluation.py:215` | 源码实现指数衰减探测概率和路径损耗型干扰强度；与第三章简化传播模型一致。 |
| 雷达方程模型 | `TongjiThesis-1.4.3/chapters/04_model.tex:68`、`TongjiThesis-1.4.3/chapters/04_model.tex:73` | `src/evaluation.py:234`--`src/evaluation.py:296`、`src/evaluation.py:299`--`src/evaluation.py:320` | 源码包含雷达方程 SNR、探测概率近似和干扰功率密度计算；可支撑论文中“论文对齐场景/雷达方程模型”的描述。 |
| ECR 与 `J_{\min}` 物理指标 | `TongjiThesis-1.4.3/chapters/04_model.tex:112`、`TongjiThesis-1.4.3/chapters/04_model.tex:123` | `src/evaluation.py:464`--`src/evaluation.py:509`、`src/evaluation.py:512`--`src/evaluation.py:550`、`experiments/compare_algorithms.py:277`--`experiments/compare_algorithms.py:318` | 源码用 OR 融合计算 ECR，并取所有任务点总干扰强度最小值作为 `J_min`；实验输出阶段重新计算物理 ECR/`J_min`，与论文图表优先展示物理指标一致。 |
| 归一化优化目标 | `TongjiThesis-1.4.3/chapters/04_model.tex:100`、`TongjiThesis-1.4.3/chapters/04_model.tex:162` | `src/evaluation.py:900`--`src/evaluation.py:960`、`src/evaluation.py:963`--`src/evaluation.py:978`、`experiments/compare_algorithms.py:127`--`experiments/compare_algorithms.py:134` | 当前关键实验入口调用 `create_normalized_evaluate_function`，目标为 `f1=1-ECR` 和 `f2=J_ref/(J_min+J_ref)`；`src/evaluation.py:632`--`src/evaluation.py:690` 的 `1/J_min` 接口是遗留/对照接口，定稿时不应作为当前主实验目标表述依据。 |
| MOPSO-DT 主循环 | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:192`--`TongjiThesis-1.4.3/chapters/05_algorithm.tex:212` | `src/mopso.py:199`--`src/mopso.py:287`、`src/mopso.py:386`--`src/mopso.py:430`、`src/mopso.py:831`--`src/mopso.py:850` | 源码执行初始化、初始评估、档案维护、领导者选择、连续/二进制变量更新、重新评估和个体最优更新；与算法 4.3 的执行顺序一致。 |
| 多算法公平比较协议 | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:233` | `experiments/compare_algorithms.py:149`--`experiments/compare_algorithms.py:150`、`experiments/compare_algorithms.py:176`--`experiments/compare_algorithms.py:224`、`src/baseline_algorithms.py:127`--`src/baseline_algorithms.py:280` | 对比实验统一评价预算、场景、评估函数和结果汇总；基线算法实现包括 Random、NSGA-II、MOEA/D 和 SPEA2。 |

## 4. Figure Evidence Map

| 论文图 | 论文位置 | 图中含义 | 生成/来源 | 依赖数据 | 可复现性结论 |
|---|---|---|---|---|---|
| `intro_research_framework.pdf` | `TongjiThesis-1.4.3/chapters/02_intro.tex:13` | 绪论中的研究问题与技术路线总览。 | 论文目录内 PDF 存在；可编辑源资产为 `TongjiThesis-1.4.3/figures/source/intro_research_framework.svg`。 | 说明性示意图，不依赖实验数据。 | 可追溯到 SVG 资产，但自动生成脚本未定位，属于“可编辑但非脚本复现”。 |
| `fig_inference.pdf` | `TongjiThesis-1.4.3/chapters/04_model.tex:144` | 候选部署方案从粒子解码到 ECR、`J_min` 和目标函数的计算链路。 | 与 `figures/fig_inference.svg`、`figures/fig_inference.png` 对应。 | 说明性示意图，不依赖实验数据。 | 可追溯到 SVG/PNG 资产；未定位自动生成脚本。 |
| `coordinate_transform_pipeline.pdf` | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:5` | 区域分解、坐标变换和部署优化的总体方法流程。 | `figures/visualize_coordinate_transform.py:393` 生成 `figures/coordinate_transform_pipeline.png`；论文 PDF 同步链路需确认。 | 几何示例由脚本构造。 | PNG 可脚本复现；当前论文 PDF 与 PNG 的转换/同步步骤未完全记录。 |
| `fig_architecture.pdf` | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:14` | MOPSO-DT 系统模块架构。 | 与 `figures/fig_architecture.svg`、`figures/fig_architecture.png` 对应。 | 说明性架构图。 | 可编辑资产存在；未定位自动生成脚本。 |
| `decomposition_pipeline.pdf` | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:25` | 带空洞区域从原始区域到凸分解和编码的过程。 | `figures/visualize_decomposition.py:266` 生成 `figures/decomposition_pipeline.png`。 | 脚本内置带空洞区域示例。 | PNG 可脚本复现；论文 PDF 转换/同步链路需确认。 |
| `decomposition_variety.pdf` | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:61` | 多种代表性区域形状的凸分解结果。 | `figures/visualize_decomposition.py:167` 生成 `figures/decomposition_variety.png`。 | 脚本内置多种区域示例。 | PNG 可脚本复现；论文 PDF 转换/同步链路需确认。 |
| `coordinate_transform_overview.pdf` | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:74` | 归一化搜索空间到凸多边形物理空间的映射概览。 | `figures/visualize_coordinate_transform.py:139` 生成 `figures/coordinate_transform_overview.png`。 | 脚本内置凸多边形和采样点。 | PNG 可脚本复现；论文 PDF 转换/同步链路需确认。 |
| `coordinate_transform_detail.pdf` | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:105` | 垂直交点坐标变换的三步细节。 | `figures/visualize_coordinate_transform.py:262` 生成 `figures/coordinate_transform_detail.png`。 | 脚本内置凸多边形和示例点。 | PNG 可脚本复现；论文 PDF 转换/同步链路需确认。 |
| `fig_pipeline.pdf` | `TongjiThesis-1.4.3/chapters/05_algorithm.tex:224` | MOPSO-DT 迭代流程，含初始化、连续/二进制更新、评价和档案维护。 | `tools/generate_pipeline_figure.py:101`--`tools/generate_pipeline_figure.py:103` 同步生成根目录 PNG/SVG 和论文 PDF。 | 说明性流程图。 | 可由单一脚本直接复现到当前论文目录。 |
| `algorithm_pareto_overlay.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:73` | 多算法 ECR-`J_min` 非支配解分布。 | `tools/generate_comparison_figures.py:136`--`tools/generate_comparison_figures.py:172`。 | `results/algorithm_comparison.json`。 | 可由结构化 JSON 直接复现。 |
| `algorithm_metrics_bars.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:80` | 多算法 HV、Spacing、解数量和运行时间对比。 | `tools/generate_comparison_figures.py:175`--`tools/generate_comparison_figures.py:209`。 | `results/algorithm_comparison.json`。 | 可由结构化 JSON 直接复现。 |
| `runtime_quality_tradeoff.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:87` | 运行时间与 HV 的质量-效率权衡。 | `tools/generate_comparison_figures.py:212`--`tools/generate_comparison_figures.py:244`。 | `results/algorithm_comparison.json`。 | 可由结构化 JSON 直接复现。 |
| `knee_deployment_comparison.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:98` | 本文方法与最佳 HV 基线的膝点部署方案对比。 | `tools/generate_comparison_figures.py:302`--`tools/generate_comparison_figures.py:345`。 | `results/algorithm_comparison.json`，并调用 `experiments.compare_algorithms.build_scenario` 重建场景。 | 可由结构化 JSON 和场景构造函数复现。 |
| `boundary_coverage_map.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:126` | 边界任务点 covered/uncovered 分布以及部署位置。 | `tools/generate_comparison_figures.py:259`--`tools/generate_comparison_figures.py:299`。 | `results/boundary_analysis.json`，并调用 `experiments.boundary_analysis.build_boundary_scenario` 重建场景。 | 可由结构化 JSON 和场景构造函数复现。 |
| `paper_aligned_results.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:238` | Paper-Aligned 场景下部署、前沿、ECR 分布和相关性的综合图。 | `experiments/experiment_paper_aligned.py:409`--`experiments/experiment_paper_aligned.py:410` 生成 PNG/PDF。 | 实验运行时产生的 Pareto 解、ECR 和 `J_min` 数组；脚本可在 `experiments/experiment_paper_aligned.py:449`--`experiments/experiment_paper_aligned.py:480` 保存 JSON 摘要。 | 脚本具备生成逻辑；当前论文目录 PDF 与根目录 PNG 不完全同哈希，建议后续重跑并把 JSON 落入 `results/`。 |
| `paper_aligned_pareto.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:266` | Paper-Aligned 场景的 ECR-`J_min` Pareto 前沿单图。 | `experiments/experiment_paper_aligned.py:414`--`experiments/experiment_paper_aligned.py:429`。 | 同 Paper-Aligned 实验输出数组。 | 脚本具备生成逻辑；PDF 同步链路需后续确认。 |
| `13_challenging_scene.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:275` | Challenging 场景综合结果，含前沿、分布和相关性。 | `experiments/experiment_challenging.py:154`--`experiments/experiment_challenging.py:211`。 | Challenging 实验输出的 Pareto 解、ECR 和 `J_min` 数组；脚本可在 `experiments/experiment_challenging.py:227`--`experiments/experiment_challenging.py:258` 保存 JSON 摘要。 | 脚本具备生成逻辑；当前论文目录 PNG 与根目录 PNG 不完全同哈希，建议后续重跑并把 JSON 落入 `results/`。 |
| `paper_aligned_correlation.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:319` | Paper-Aligned 场景 ECR 与 `J_min` 的相关性散点图。 | `experiments/experiment_paper_aligned.py:433`--`experiments/experiment_paper_aligned.py:443`。 | Paper-Aligned 实验输出的 ECR 和 `J_min` 数组。 | 根目录 PNG 与论文目录 PNG 哈希一致；PDF 同步链路仍建议记录。 |
| `tradeoff_fixed.pdf` | `TongjiThesis-1.4.3/chapters/06_experiments.tex:328` | 不同雷达数量下 ECR 与 `J_min` 的权衡示意。 | 根目录存在 `figures/tradeoff_fixed.png`，论文目录存在 `tradeoff_fixed.pdf`。 | 依赖数据未在当前脚本扫描中定位。 | 生成链路需确认；定稿前应重建或降低其证据权重。 |

## 5. Current Thesis-Data Consistency Checks

| 论文位置 | 当前写法/数值 | 项目证据 | 复核结论 |
|---|---|---|---|
| 第 5 章表 `tab:algorithm_comparison` | 本文 MOPSO-DT HV 0.0308、Spacing 0.0071、解数 14.0、时间 58.3 s | `results/algorithm_comparison.json` 中 `method=ours` 的均值 | 与 JSON 四舍五入后一致。 |
| 第 5 章表 `tab:algorithm_comparison` | MOEA/D HV 0.0348 最高，SPEA2 Spacing 0.0017 最低 | `results/algorithm_comparison.json` summary | 支持“多算法各有优势”，不支持“本文方法全面最优”。 |
| 第 5 章表 `tab:boundary_analysis` | ours_transform 与 direct_physical 的 Boundary ECR 均为 0.156 | `results/boundary_analysis.json` summary | 与 JSON 四舍五入后一致；NSGA-II 的 Overall ECR 和 HV 更高也应在结论中保持。 |
| 第 5 章表 `tab:tuning_summary` | legacy + crowding + `p_m=0` 的 HV 0.0524 最高 | `results/tune_results.json` 的 `best_combo` | 与当前结果文件一致；后续不应把 `standard + crowding + p_m=0.01` 写成绝对最佳。 |
| 第 5 章表 `tab:inertia_comparison` | standard HV 0.0397 高于 legacy/adaptive，但 Spacing 不是最低 | `results/tune_results.json` 的 `inertia_strategy` | 与当前结果文件一致，仅说明该子实验下的惯性策略比较。 |
| 第 5 章 Paper-Aligned 表 | Pareto 解 7、ECR [0.780, 0.850]、相关系数约 -0.923 | `results/paper_aligned_results.json` | 与结构化 JSON 一致；本轮重跑耗时约 140.8 s。 |
| 第 5 章 Challenging 表 | Pareto 解 10、ECR [0.031, 0.222]、相关系数约 -0.968 | `results/challenging_scene_results.json` | 与结构化 JSON 一致。 |

## 6. Chapter 5 Claim-to-Data Audit

| 论文位置 | 当前表述或数字 | 原始证据 | 审计结论 |
|---|---|---|---|
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:63`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:68` | 多算法表：ours HV 0.0308、MOEA/D HV 0.0348、SPEA2 Spacing 0.0017 等。 | `results/algorithm_comparison.json` 的 `summary`：ours 平均 HV 0.030812、MOEA/D 平均 HV 0.034807、SPEA2 平均 Spacing 0.001706。 | 数字与结构化 JSON 四舍五入后一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:94` | “MOEA/D-DT 平均 HV 最高，SPEA2-DT Spacing 最低，NSGA-II-DT 解数量更多；不写成全面优于”。 | `results/algorithm_comparison.json`：MOEA/D HV 最高，SPEA2 Spacing 最低，SPEA2 解数最高、NSGA-II 解数也显著多于 ours。 | 方向正确，但“NSGA-II-DT保留的非支配解数量也更多”只说明 NSGA-II 多于 ours；若比较所有方法，SPEA2 解数更多。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:96` | “本文改进配置相对 legacy 的收益不主要来自 HV 绝对值，而来自更稳定的前沿分布、可复现实验改进”。 | `results/algorithm_comparison.json`：ours HV 0.030812 低于 legacy 0.031563；Spacing 0.007140 略低于 legacy 0.007226；runtime 58.27 s 低于 61.47 s。 | 需保守理解。数据支持“运行时间略短、Spacing 均值略低”，不支持泛化为明显前沿稳定性提升。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:118`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:121` | 边界表：ours_transform 与 direct_physical 的 Boundary ECR 均为 0.156，NSGA-II Overall ECR 和 HV 更高。 | `results/boundary_analysis.json`：ours_transform boundary 0.15625、direct 0.15625、NSGA-II overall 0.34722、HV 0.046746。 | 数字一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:133` | “直接物理空间搜索的Boundary ECR最高”。 | 同上：direct_physical 与 ours_transform 的 Boundary ECR 平均值相同，均为 0.15625。 | 该句应在定稿时改为“与坐标变换方法并列最高”或“同为最高”，避免暗示 direct 单独领先。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:150`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:154` | 调参 best_combo 表。 | `results/tune_results.json` 的 `best_combo`：legacy + crowding + `p_m=0` HV 0.052446；standard + crowding + `p_m=0.01` HV 0.045001。 | 表格数值一致；后续“推荐配置”必须解释为流程选择，不是该调参表中的单项 HV 最优。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:168`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:170` | 惯性权重表：standard HV 0.0397、adaptive HV 0.0383、legacy HV 0.0310。 | `results/tune_results.json` 的 `inertia_strategy`。 | 数字一致；`TongjiThesis-1.4.3/chapters/06_experiments.tex:175` 对 “standard HV 更高但 Spacing 并非最低” 的解释与数据一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:188`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:227` | 传播模型、坐标变换和目标函数消融表。 | `results/ablation_propagation.npz`、`results/ablation_transform.npz`、`results/ablation_normalization.npz`、`results/ablation_region.npz`、`results/ablation_radar_count.npz` 和 `results/ablation_summary.json`。 | 已有结构化结果基础；下一步应逐表核对论文中的消融数值是否与 `ablation_summary.json` 一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:254`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:259` | Paper-Aligned 汇总表：Pareto 7、ECR [0.780, 0.850]、相关系数 -0.923、耗时 156.3 s。 | `results/paper_aligned_results.json`：Pareto 7、ECR [0.780, 0.850]、相关系数 -0.9231、`elapsed_seconds=140.8056`。 | 主要指标一致；耗时与当前重跑结果不一致。若论文保留耗时，应改为当前 JSON 值或说明硬件/运行批次。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:291`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:295` | Challenging 汇总表：Pareto 10、ECR [0.031, 0.222]、相关系数 -0.968。 | `results/challenging_scene_results.json`：Pareto 10、ECR [0.0311, 0.2222]、相关系数 -0.9683。 | 与结构化 JSON 四舍五入后一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:313`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:314` | 跨场景相关系数：Paper-Aligned -0.923，Challenging -0.968。 | `results/paper_aligned_results.json` 与 `results/challenging_scene_results.json`。 | 方向和数值与结构化 JSON 一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:328`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:335` | `tradeoff_fixed` 图及“节点更多时范围整体上移”的解释。 | 当前只定位到 `figures/tradeoff_fixed.png` 和论文 PDF，未定位生成脚本与依赖数据。 | 证据链不足。若保留为结论图，应补生成脚本/数据；否则应降格为示意性说明。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:337`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:353` | 与代表性工作的能力维度比较，本文“优化效率”为高。 | 主要依赖方法设计和文献对照，不是同场景结构化实验。 | 可作为定性对照表，但不能替代同场景数据；“优化效率高”应谨慎，避免和多算法表中经典算法部分指标更强相冲突。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:373`--`TongjiThesis-1.4.3/chapters/06_experiments.tex:374` | “ECR 表示部署代价，`J_min` 表示最小观测性能”。 | 第 3 章和 `src/evaluation.py` 均把 ECR 作为覆盖有效率，内部最小化目标是 `f1=1-ECR`。 | 概念有偏差。定稿时应改为“ECR 表示覆盖有效性，`1-ECR` 表示覆盖损失/代价；`J_min` 表示最薄弱任务点压制强度”。 |

## 7. Ablation Table Numeric Audit

| 论文位置 | 论文当前数值/结论 | `results/ablation_summary.json` 当前证据 | 核对结论 |
|---|---|---|---|
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:188` | 异构模型：Pareto 解 11，ECR [0.036, 0.213]，r=-0.993。 | `propagation.hetero_ecr.n=17`，ECR [0.0089, 0.2044]，`hetero_r=-0.9706`。 | 不一致。表格应按新结果更新，或标明旧结果来源。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:189` | 统一模型：Pareto 解 12，ECR [0.022, 0.218]，r=-0.972。 | `propagation.uniform_ecr.n=18`，ECR [0.0178, 0.2089]，`uniform_r=-0.9733`。 | 相关系数接近，但解数和 ECR 范围不一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:194` | 统一传播模型与异构模型接近，异构模型主要改变贡献分配而非简单抬高指标。 | 当前 A1 显示两组 ECR 范围和相关性接近，但 `J_min` 数值尺度差别很大：`hetero_jmin` 最大约 `2.13e-6`，`uniform_jmin` 最大约 `1.30e-4`。 | 定性方向可保留，但应补充“物理量尺度发生明显变化”，避免只看 ECR 和相关系数。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:207` | 有坐标变换：Pareto 解 15，ECR [0.000, 0.200]，耗时 56.0 s。 | `transform.transform_ecr.n=17`，ECR [0.0089, 0.2000]；当前汇总 JSON 未保存耗时字段。 | 解数和 ECR 下界不一致；耗时无法由 JSON 核验。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:208` | 无坐标变换：Pareto 解 13，ECR [0.022, 0.204]，耗时 18.5 s。 | `transform.direct_ecr.n=18`，ECR [0.0267, 0.2133]；当前汇总 JSON 未保存耗时字段。 | 解数和 ECR 范围不一致；耗时无法由 JSON 核验。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:213` | 有坐标变换出现更低 ECR 极端解；无变换更快；坐标变换主要保留边界可达性。 | 当前 A2 显示有变换 ECR 下界更低，direct ECR 上界和均值更高；但耗时没有进入结构化 JSON。 | “出现更低 ECR 极端解”可由 JSON 支撑；“更快”需要把耗时字段保存到结果或引用运行日志。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:226` | 归一化 `f_2`：Pareto 解 14，ECR [0.013, 0.209]，r=-0.931。 | `normalization.norm_nsols=19`，ECR [0.0178, 0.2178]，`norm_r=-0.9617`。 | 不一致。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:227` | 原始 `1/J_min`：Pareto 解 19，ECR [0.009, 0.191]，r=-0.982。 | `normalization.raw_nsols=13`，ECR [0.0222, 0.2000]，`raw_r=-0.9374`。 | 不一致，且“谁的解更多”方向相反。 |
| `TongjiThesis-1.4.3/chapters/06_experiments.tex:232` | 原始 `1/J_min` 在 Challenging 场景下产生更多 Pareto 解，相关性绝对值更高。 | 当前 A3 显示归一化解数更多，且归一化相关性绝对值更高。 | 当前正文解释与新结果冲突，后续定稿必须重写。 |

## 8. Full-Thesis Narrative Boundary Audit

| 论文位置 | 当前叙述 | 当前证据 | 定稿边界 |
|---|---|---|---|
| `TongjiThesis-1.4.3/chapters/00_abstract.tex:4`--`TongjiThesis-1.4.3/chapters/00_abstract.tex:6` | 摘要称方法输出非支配部署方案，并在边界覆盖和部分解集质量指标上较原始配置改善。 | `results/boundary_analysis.json` 支持坐标变换与 direct_physical 的 Boundary ECR 同为 0.15625，高于 legacy 和 NSGA-II；`results/algorithm_comparison.json` 支持 ours 相对 legacy 运行时间更短、Spacing 均值略低，但 HV 与 ECRmax 不高于 legacy。 | 可保留“部分指标改善”，但必须理解为边界覆盖、运行时间和少量解集分布指标，不应扩展为全面性能提升。 |
| `TongjiThesis-1.4.3/chapters/00_abstract.tex:14` | 英文摘要称 the method improves boundary coverage and selected solution-set quality indicators. | 与中文摘要同源，证据同上。 | 英文边界与中文一致；后续若中文收窄，英文必须同步收窄。 |
| `TongjiThesis-1.4.3/chapters/02_intro.tex:11` | 绪论明确本文不证明 universally best，而是在同编码、同目标和同预算下比较。 | `results/algorithm_comparison.json` 显示 MOEA/D 的 HV、SPEA2 的 Spacing 和解数等指标优于 ours。 | 该限制是必要且正确的，应保留。 |
| `TongjiThesis-1.4.3/chapters/02_intro.tex:41` | 研究内容包含参数调优、消融实验和边界专项实验。 | 参数调优、边界和消融均已有结构化结果入口：`results/tune_results.json`、`results/boundary_analysis.json`、`results/ablation_summary.json`。 | “消融实验”作为已做模块可以保留；但论文表格数值仍需用 `ablation_summary.json` 逐项核对后再定稿。 |
| `TongjiThesis-1.4.3/chapters/03_theory.tex:156` | 理论章用“较低部署代价、数量较少或位置集中”等语言解释多目标权衡。 | 当前核心实验多数固定雷达/干扰节点数量，ECR 是覆盖有效率，内部代价目标是 `1-ECR`。 | 这段作为多目标直觉可以保留，但应避免把当前实验直接解释为节点数量成本优化。 |
| `TongjiThesis-1.4.3/chapters/04_model.tex:100`--`TongjiThesis-1.4.3/chapters/04_model.tex:126` | 模型章定义 `f_1=1-ECR`，`f_2=J_ref/(J_min+J_ref)`，并解释图表优先展示物理指标。 | `src/evaluation.py` 和实验图表均使用 ECR 与 `J_min` 对外解释，优化内部使用归一化目标。 | 该定义与当前实现方向一致，是后续修正“ECR=代价”表述的依据。 |
| `TongjiThesis-1.4.3/chapters/04_model.tex:156` | 模型章称 ECR 和 `J_min` 分别对应部署代价与最小观测性能。 | 同上，ECR 本身是覆盖有效性，不是部署代价；`1-ECR` 才是覆盖损失形式的最小化目标。 | 定稿时应改成“ECR 表示覆盖有效性，`1-ECR` 表示覆盖损失/代价方向；`J_min` 表示最薄弱任务点压制强度”。 |
| `TongjiThesis-1.4.3/chapters/05_algorithm.tex:178` | 算法章称 crowding 相对 random 在 Spacing 上取得 35.7% 至 54.0% 改善。 | `results/tune_results.json` 的 `gb_selection` 中 crowding Spacing 为 0.02235，高于 random 0.01338；`best_combo` 分组下 crowding 的 Spacing 改善为 -71.6%、-26.6%、44.5%、68.6%，并不稳定落在 35.7%--54.0%。 | 当前句子证据不足。后续应改为“crowding 在部分参数组合下降低 Spacing，但效果依赖惯性权重和变异率”，或重新跑实验后再给固定百分比。 |
| `TongjiThesis-1.4.3/chapters/05_algorithm.tex:249` | 算法章给出典型配置耗时 156.3 s。 | 当前 `results/paper_aligned_results.json` 记录同配置 `elapsed_seconds=140.8056`。 | 与当前结构化重跑不一致；后续应改为约 140.8 s，或明确 156.3 s 来自旧日志批次。 |
| `TongjiThesis-1.4.3/chapters/07_conclusion.tex:7` | 结论称 direct physical 在单一 Boundary ECR 上仍取得最高值。 | `results/boundary_analysis.json` 显示 direct_physical 与 ours_transform Boundary ECR 均为 0.15625。 | 应改为“与坐标变换方法并列最高”或“同为最高”。 |
| `TongjiThesis-1.4.3/chapters/07_conclusion.tex:9` | 结论总结传播模型消融。 | `results/ablation_summary.json` 显示异构与统一传播模型的相关系数分别约为 -0.971 和 -0.973，ECR 范围分别为 [0.009, 0.204] 与 [0.018, 0.209]。 | 可以保守表述为“传播模型改变物理量尺度和前沿分布，但本轮消融不支持必然提升单项指标”。 |
| `TongjiThesis-1.4.3/chapters/07_conclusion.tex:11` | 结论称相对 legacy 配置前沿分布更稳定。 | `results/algorithm_comparison.json` 显示 ours 相对 legacy 的 Spacing 仅略低，HV 和 ECRmax 低于 legacy，运行时间更短。 | 应收窄为“运行时间略短、Spacing 均值略低；整体 Pareto 质量未全面优于 legacy”。 |
| `TongjiThesis-1.4.3/chapters/07_conclusion.tex:13` | 结论称两个场景均观察到 ECR 与 `J_min` 负相关趋势。 | `results/paper_aligned_results.json` 和 `results/challenging_scene_results.json` 给出相关系数约 -0.923 和 -0.968。 | 可保留为“本文两个实验场景中观察到”，并继续避免外推为普遍定律。 |

## 9. Claim Support Map

| 潜在论文内容 | 当前证据 | 定稿建议 |
|---|---|---|
| 复杂区域可以通过凸分解和编码纳入优化 | `src/decomposition.py`、`src/mopso.py`、方法图 | 可保留，但要避免声称所有复杂区域都最优处理。 |
| 坐标变换减少非法采样并改善边界可达性 | `src/coordinate_transform.py`、`results/boundary_analysis.json` | 可保守表述为“改善部分边界可达性/边界覆盖表现”。 |
| 边界效应被完全消除 | 当前边界结果不支持 | 不建议保留该强表述。 |
| MOPSO-DT 在复杂区域双目标部署中能输出 Pareto 方案集 | `src/mopso.py`、`experiment_paper_aligned.py`、`experiment_challenging.py` | 可保留。 |
| 本文方法全面优于 NSGA-II/MOEA/D/SPEA2 | `results/algorithm_comparison.json` 不支持 | 不建议保留；应改为客观比较。 |
| ECR 与 `J_min` 存在负相关权衡 | paper-aligned 相关系数约 -0.9231，challenging 约 -0.968，多算法结果也多为负相关 | 可保留为“本文测试场景中观察到”。 |
| 推荐配置为 standard + crowding + p_m=0.01 | 当前 `results/tune_results.json` 显示 best combo 为 legacy + crowding + p_m=0.0 | 后续定稿前必须统一配置依据，避免把局部子实验结论泛化为全局推荐。 |
| 空地异构传播模型被实现 | `src/evaluation.py` 包含 A2G/G2G 和雷达方程相关函数 | 可描述实现；若要宣称带来提升，需要补充或定位对应实验。 |

## 10. Key Numbers From Current Validation

| 来源 | 当前结果 |
|---|---|
| `pytest` | 47 passed, 6 warnings |
| `quick_compare.py` | improved 运行时间更短、HV 略高，但 Pareto 解数量少于 baseline |
| `tune_mopso.py` | best combo: `legacy + crowding + p_m_base=0.0`, HV 约 0.05245 |
| `experiment_paper_aligned.py` | Pareto 解 7，ECR 0.7800--0.8500，相关系数约 -0.9231 |
| `experiment_challenging.py` | Pareto 解 10，ECR 0.0311--0.2222，相关系数约 -0.968 |
| `compare_algorithms.py` | MOEA/D 平均 HV 最高；SPEA2 Spacing 最低；ours 平均运行时间最短但非整体最优 |
| `boundary_analysis.py` | ours_transform 与 direct_physical 的 boundary ECR 均值同为 0.15625；NSGA-II overall ECR 和 HV 更高 |
| `ablation_core.py` | 当前结构化消融显示 A3 中归一化目标解数为 19，原始目标解数为 13；与论文现有表述方向相反 |

## 11. Evidence Risks

- `quick_compare.py` 输出具有随机波动，不能单独支撑固定百分比提升。
- `tune_mopso.py` 本次运行完成并写出结果，但外层日志捕获在超时点未正常返回；结果文件可用，命令状态需在报告中说明。
- `boundary_analysis.py` 结果文件已更新，但外层日志捕获超时，没有完整 stdout 日志。
- 部分 PDF 图来自模板目录，虽然与 PNG 或脚本意图一致，但 PDF 转换链路未全部在本次复现。
- 论文草稿中的强结论需要等后续定稿阶段逐句改写，本次不直接修改正文。
- Paper-Aligned 与 Challenging 单场景结果已补入 `results/` 下的结构化 JSON；后续风险转为“论文耗时和图像同步链路需统一”。
- `paper_aligned_results.png`、`paper_aligned_pareto.png` 和 `13_challenging_scene.png` 在根目录 `figures/` 与论文目录 `TongjiThesis-1.4.3/figures/` 中文件大小或哈希不完全一致，说明当前论文图可能经过单独同步、重绘或压缩；定稿前建议重新运行对应实验并统一输出位置。
- `paper_aligned_correlation.png` 在根目录和论文目录哈希一致，但论文引用的是 PDF，PDF 生成/同步链路仍应在最终归档前记录。
- `tradeoff_fixed.pdf` 当前能在论文目录中找到，但本轮扫描未定位生成脚本和依赖数据；若后续保留该图，应补充生成脚本或把图注改为仅作示意。
- `tools/generate_comparison_figures.py` 已改为默认输出到 `TongjiThesis-1.4.3/figures/`，并用临时目录验证可生成 5 张多算法/边界 PDF 图；后续正式重跑时可直接使用默认目录。
- `TongjiThesis-1.4.3/chapters/05_algorithm.tex:178` 中 crowding 相对 random 的固定百分比改善目前与 `results/tune_results.json` 不一致，是后续正文精修的优先项。
- 消融实验本轮已生成 `results/ablation_summary.json`，并已确认第 5 章三张消融表存在数值冲突；后续定稿应优先重写这些表格和对应解释。

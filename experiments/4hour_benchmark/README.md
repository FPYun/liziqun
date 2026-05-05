# 4-Hour MOPSO-DT CPU+GPU Hybrid Benchmark

全面评估 MOPSO-DT 算法的 4 部分实验套件，利用 CPU+GPU 混合加速。

## 快速开始

```bash
# 安装依赖
pip install -r ../../requirements.txt
pip install cupy-cuda12x  # 如有 NVIDIA GPU

# 快速测试 (~2 min, 验证脚本正确性)
python experiment_4hour.py --quick

# 完整运行 (~4h 墙钟)
python experiment_4hour.py
```

## 实验内容

| Part | 主题 | Runs | 墙钟 |
|------|------|------|------|
| 1 | 可扩展性分析 (J=10~120) | 15 | ~1.2h |
| 2 | 消融实验 (3组件贡献) | 36 | ~1.5h |
| 3 | 区域鲁棒性 (5种形状) | 20 | ~0.75h |
| 4 | 参数敏感性 (N_P/T_max/p_c) | 27 | ~0.5h |
| **总计** | | **98** | **~4h** |

## 输出

所有结果保存在当前目录下：
- `figures/` — 4 张可视化图表
- `results/` — 结构化 JSON + Markdown 报告
- `logs/` — 运行日志

## 详细文档

见 [experiment_plan.md](experiment_plan.md)

#!/usr/bin/env python3
"""
从源码自动生成论文三线表 LaTeX 文件。

读取 src/evaluation.py 中的 RadarConfig 和 src/mopso.py 中的 MOPSO_DT 默认参数，
生成 TongjiThesis-1.4.3/tables/ 下的 .tex 表格文件。

用法:
    python tools/generate_tables.py                    # 默认输出到 TongjiThesis-1.4.3/tables/
    python tools/generate_tables.py --output-dir OUT   # 指定输出目录
    python tools/generate_tables.py --dry-run          # 仅打印，不写文件

当源码中 RadarConfig 或 MOPSO_DT 默认参数发生变动时，重新运行此脚本即可同步更新表格。
"""

import ast
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 项目根目录 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "TongjiThesis-1.4.3" / "tables"


# ═══════════════════════════════════════════════════════════════
# AST 解析器：从 Python 源码提取 dataclass / __init__ 默认值
# ═══════════════════════════════════════════════════════════════

def parse_dataclass_defaults(filepath: Path, class_name: str) -> Dict[str, Any]:
    """解析 dataclass 类中各字段的默认值。

    Returns:
        {field_name: default_value}  不含默认值的字段不出现在结果中。
    """
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    defaults: Dict[str, Any] = {}

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue
        for item in node.body:
            if not (isinstance(item, ast.AnnAssign) and item.value is not None):
                continue
            name = _get_assign_name(item.target)
            if name is None:
                continue
            val = ast.literal_eval(item.value)
            defaults[name] = val
        break  # 只处理第一个同名类

    return defaults


def parse_init_defaults(filepath: Path, class_name: str) -> Dict[str, Any]:
    """解析类的 __init__ 方法参数默认值（仅 keyword-capable 参数）。

    Returns:
        {param_name: default_value}  self / *args / **kwargs 被过滤。
    """
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    result: Dict[str, Any] = {}

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue
        for sub in node.body:
            if not (isinstance(sub, ast.FunctionDef) and sub.name == "__init__"):
                continue
            args = sub.args
            # 定位有默认值的参数
            n_defaults = len(args.defaults)
            defaults_start = len(args.args) - n_defaults
            for i, arg in enumerate(args.args):
                if arg.arg in ("self",):
                    continue
                if i >= defaults_start:
                    try:
                        val = ast.literal_eval(args.defaults[i - defaults_start])
                    except ValueError:
                        val = ast.unparse(args.defaults[i - defaults_start])
                    result[arg.arg] = val
            break
        break

    return result


def _get_assign_name(target) -> Optional[str]:
    """从 AnnAssign target 提取变量名。"""
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


# ═══════════════════════════════════════════════════════════════
# 值 → LaTeX 格式化
# ═══════════════════════════════════════════════════════════════

def fmt_val(v: Any) -> str:
    """将 Python 值转换为 LaTeX 数学/文本形式。"""
    if isinstance(v, bool):
        return r"\surd" if v else r"$\times$"
    if isinstance(v, float):
        if v == 0.0:
            return "0"
        # 整数型 float（如 3000.0、60.0）直接显示整数
        if v == int(v) and v < 1e6:
            return str(int(v))
        if v >= 1000 or (0 < v < 0.001):
            # 科学计数法 → LaTeX（仅用于非整数的大数/小数）
            s = f"{v:.1e}"
            base, exp = s.split("e")
            exp = int(exp)
            base_f = float(base)
            if base_f == 1.0:
                return f"$10^{{{exp}}}$"
            return f"${base_f}\\times10^{{{exp}}}$"
        # 清理多余的零
        s = f"{v:.2f}".rstrip("0").rstrip(".")
        return s
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return v
    return str(v)


def fmt_default_for_table(val: Any) -> str:
    """用于表格'默认/数值'列的格式化。"""
    if isinstance(val, bool):
        return "是" if val else "否"
    if isinstance(val, (int, float)):
        return fmt_val(val)
    return str(val)


# ═══════════════════════════════════════════════════════════════
# 表格生成函数
# ═══════════════════════════════════════════════════════════════

def generate_tab_objectives() -> str:
    """表A：优化目标形式化定义（纯公式，不依赖参数）"""
    return r"""% 此文件由 tools/generate_tables.py 自动生成，请勿手动编辑
\begin{table}[h]
\centering
\caption{优化目标形式化定义}
\label{tab:objectives}
\begin{tabular}{ccp{5.5cm}cc}
\toprule
目标 & 函数表达式 & 物理含义 & 优化方向 & 取值范围 \\
\midrule
$f_1$ & $f_1 = 1 - \mathrm{ECR}$ & 覆盖效能损失：未达到探测阈值的任务点加权比例 & $\min$ & $[0, 1]$ \\
$f_2$ & $f_2 = \dfrac{J_{\mathrm{ref}}}{J_{\min} + J_{\mathrm{ref}}}$ & 压制效能损失：归一化后最小干扰功率密度的倒数映射 & $\min$ & $(0, 1)$ \\
\bottomrule
\end{tabular}
\end{table}
"""


def generate_tab_model_params(radar_defaults: Dict[str, Any]) -> str:
    """表B：系统模型与传播参数（从 RadarConfig 同步）"""
    # 简化指数模型参数
    simple_rows = [
        (r"最大探测概率", "$P_0$", radar_defaults.get("P0", "?")),
        (r"探测概率阈值", r"$P_{\mathrm{th}}$", radar_defaults.get("P_min", "?")),
        (r"衰减系数（标准场景）", r"$\beta$", radar_defaults.get("beta", "?")),
        (r"衰减系数（挑战场景）", r"$\beta$", 0.03),  # 实验侧硬编码值
        (r"最大探测距离", r"$R_{\max}$", radar_defaults.get("R_max", "?"), "km"),
        (r"空--地路径损耗指数", r"$\alpha_{\mathrm{air}}$", radar_defaults.get("alpha_air", "?")),
        (r"地--地路径损耗指数", r"$\alpha_{\mathrm{ground}}$", radar_defaults.get("alpha_ground", "?")),
    ]

    # 雷达方程模型参数
    equation_rows = [
        (r"雷达发射功率", "$P_t$", radar_defaults.get("P_t", "?"), "W"),
        (r"天线增益", "$G_t$", radar_defaults.get("G_t_dB", "?"), "dB"),
        (r"信号波长", r"$\lambda$", radar_defaults.get("wavelength", "?"), "m"),
        (r"目标雷达截面积", r"$\sigma$", radar_defaults.get("sigma", "?"), r"m$^2$"),
        (r"信号带宽", "$B$", radar_defaults.get("bandwidth", "?"), "MHz"),
        (r"检测因子", "$D_0$", radar_defaults.get("D0_dB", "?"), "dB"),
        (r"虚警概率", r"$P_{\mathrm{fa}}$", radar_defaults.get("P_fa", "?")),
        (r"干扰机发射功率", r"$P_t^{\mathrm{jam}}$", radar_defaults.get("jammer_P_t", "?"), "W"),
        (r"干扰机天线增益", r"$G_t^{\mathrm{jam}}$", radar_defaults.get("jammer_G_t_dB", "?"), "dB"),
    ]

    lines = [
        r"% 此文件由 tools/generate_tables.py 自动生成，请勿手动编辑",
        r"\begin{table}[h]",
        r"\centering",
        r"\caption{系统模型与传播参数}",
        r"\label{tab:model_params}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"参数 & 符号 & 数值 & 单位 \\",
        r"\midrule",
        r"\multicolumn{4}{c}{（a）简化指数衰减模型} \\",
        r"\midrule",
    ]

    for label, sym, val, *rest in simple_rows:
        unit = rest[0] if rest else "--"
        v = fmt_val(val)
        lines.append(f"{label} & {sym} & {v} & {unit} \\\\")

    lines.extend([
        r"\midrule",
        r"\multicolumn{4}{c}{（b）雷达方程模型} \\",
        r"\midrule",
    ])

    for label, sym, val, *rest in equation_rows:
        unit = rest[0] if rest else "--"
        v = fmt_val(val)
        # 带宽特殊处理：15e6 → 15 MHz
        if sym == "$B$" and isinstance(val, (int, float)) and val >= 1e6:
            v = f"{fmt_val(val / 1e6)}"
        lines.append(f"{label} & {sym} & {v} & {unit} \\\\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ])

    return "\n".join(lines)


def generate_tab_core_mechanisms() -> str:
    """表C：MOPSO-DT核心机制与设计选择（设计描述，不依赖参数）"""
    return r"""% 此文件由 tools/generate_tables.py 自动生成，请勿手动编辑
\begin{table}[h]
\centering
\caption{MOPSO-DT核心机制与设计选择}
\label{tab:core_mechanisms}
\begin{tabular}{llp{6cm}}
\toprule
核心机制 & 设计选择 & 解决的问题 \\
\midrule
粒子编码 & 混合变量：连续坐标 $+$ 二进制区域编码 & 同时优化雷达位置（连续空间）和子区域选择（离散空间） \\
连续变量更新 & 标准PSO速度--位置更新 & 在$[0,1]^2$归一化空间中高效搜索连续坐标 \\
二进制变量更新 & 交叉（继承$p_{\mathrm{best}}$/$g_{\mathrm{best}}$）$+$独立变异 & 以可控随机性选择最优子区域，平衡探索与利用 \\
惯性权重 & standard线性递减：$w=0.9\to0.4$ & 前期强全局探索，后期保证局部收敛精度 \\
全局最优选择 & crowding拥挤度加权轮盘赌 & 引导粒子向Pareto前沿稀疏区域移动，提升分布均匀性 \\
外部档案 & Pareto支配筛选 $+$ 拥挤距离截断 & 维护有限容量的高质量非支配解集，保证多样性 \\
约束处理 & 坐标变换$[0,1]^2$$\to$凸多边形物理空间 & 将任意多边形约束转为无约束归一化搜索，抑制边界效应 \\
性能加速 & Numba JIT $+$ CuPy GPU $+$ 多线程并行 & 将典型场景优化耗时从小时级降至分钟级 \\
\bottomrule
\end{tabular}
\end{table}
"""


def generate_tab_param_space(mopso_defaults: Dict[str, Any]) -> str:
    """表D：算法参数空间与推荐配置（从 MOPSO_DT 同步）"""
    # 源码默认值 ≠ 论文推荐值的参数，在此覆盖
    recommended_overrides = {
        "p_m_base": 0.01,       # 源码默认 0，实验验证推荐 0.01
        "select_gb": "crowding",  # 源码默认 random，实验验证推荐 crowding
    }

    def recv(param_name: str) -> Any:
        """获取推荐值：优先使用覆盖值，否则使用源码默认值"""
        if param_name in recommended_overrides:
            return recommended_overrides[param_name]
        return mopso_defaults.get(param_name, "?")

    param_data = [
        (
            r"粒子数 $N_P$",
            r"$\{20, 30, 50, 80\}$",
            recv("N_P"),
            r"高（$N_P{=}50$ 时 HV 最大，$N_P{=}80$ 收益递减）",
        ),
        (
            r"最大迭代 $T_{\max}$",
            r"$\{30, 50, 100, 500\}$",
            recv("T_max"),
            r"中（50 次后边际增益减小）",
        ),
        (
            r"惯性权重策略",
            r"\{legacy, standard, adaptive\}",
            recv("w_strategy"),
            r"中（比 legacy 提升 0.4\%，比 adaptive 提升 62\%）",
        ),
        (
            r"认知因子 $c_1$",
            r"$\{1.0, 1.5, 2.0, 2.5\}$",
            recv("c_1"),
            r"低（在合理范围内不敏感）",
        ),
        (
            r"社会因子 $c_2$",
            r"$\{1.0, 1.5, 2.0, 2.5\}$",
            recv("c_2"),
            r"低（在合理范围内不敏感）",
        ),
        (
            r"基础变异率 $p_m^{\mathrm{base}}$",
            r"$\{0, 0.01, 0.03, 0.05\}$",
            recv("p_m_base"),
            r"高（$p_m{=}0.01$ 比 $p_m{=}0$ 提升 35\%；$\ge 0.03$ 时退化）",
        ),
        (
            r"全局最优选择",
            r"\{random, crowding\}",
            recv("select_gb"),
            r"高（比 random 提升 5.9\% HV，Spacing 改善 36\%）",
        ),
        (
            r"档案容量",
            r"$\{50, 100, 200\}$",
            recv("archive_size"),
            r"低（${>}100$ 后边际效益递减）",
        ),
    ]

    lines = [
        r"% 此文件由 tools/generate_tables.py 自动生成，请勿手动编辑",
        r"\begin{table}[h]",
        r"\centering",
        r"\caption{MOPSO-DT参数空间与推荐配置}",
        r"\label{tab:param_space}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"参数 & 搜索/可选范围 & 推荐值 & HV影响程度 \\",
        r"\midrule",
    ]

    for label, search_range, default, impact in param_data:
        v = fmt_default_for_table(default)
        lines.append(f"{label} & {search_range} & {v} & {impact} \\\\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ])

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main(output_dir: Path, dry_run: bool = False):
    # 1. 从源码提取参数
    eval_path = SRC_DIR / "evaluation.py"
    mopso_path = SRC_DIR / "mopso.py"

    if not eval_path.exists():
        print(f"[错误] 找不到 {eval_path}")
        sys.exit(1)
    if not mopso_path.exists():
        print(f"[错误] 找不到 {mopso_path}")
        sys.exit(1)

    radar_defaults = parse_dataclass_defaults(eval_path, "RadarConfig")
    mopso_defaults = parse_init_defaults(mopso_path, "MOPSO_DT")

    print(f"[信息] 从 RadarConfig 读取 {len(radar_defaults)} 个参数")
    print(f"[信息] 从 MOPSO_DT 读取 {len(mopso_defaults)} 个参数")

    # 2. 生成表格
    generators = {
        "tab_objectives.tex": generate_tab_objectives,
        "tab_model_params.tex": lambda: generate_tab_model_params(radar_defaults),
        "tab_core_mechanisms.tex": generate_tab_core_mechanisms,
        "tab_param_space.tex": lambda: generate_tab_param_space(mopso_defaults),
    }

    if dry_run:
        print(f"\n[预览] 将写入 {output_dir}/")
        for fname, gen in generators.items():
            print(f"\n{'─' * 60}")
            print(f"  {fname}")
            print(f"{'─' * 60}")
            print(gen())
        return

    os.makedirs(output_dir, exist_ok=True)

    for fname, gen in generators.items():
        out_path = output_dir / fname
        content = gen()
        out_path.write_text(content, encoding="utf-8")
        print(f"[写入] {out_path}")

    print(f"\n[完成] 4 张表格已生成到 {output_dir}/")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="从源码生成论文三线表 LaTeX 文件"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"输出目录（默认: {DEFAULT_OUTPUT_DIR}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不写入文件",
    )
    args = parser.parse_args()
    main(args.output_dir, args.dry_run)

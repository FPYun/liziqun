"""
结构化实验运行框架

支持：
- M0→M4 里程碑式组织实验
- 自动生成 Markdown 报告和 JSON 结果
- 实验状态追踪
- 耗时统计

从 GitHub 版本 run_experiments.py 提取改进。
"""

import os
import time
import json
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional


class ExperimentRunner:
    """结构化实验运行器"""

    def __init__(self, results_dir='results', logs_dir='logs',
                  figures_dir='figures', verbose=True):
        self.results_dir = results_dir
        self.logs_dir = logs_dir
        self.figures_dir = figures_dir
        self.verbose = verbose

        for d in [results_dir, logs_dir, figures_dir]:
            os.makedirs(d, exist_ok=True)

        self.milestones: Dict[str, List[Dict]] = {}
        self.all_results: Dict[str, Dict] = {}

    def log(self, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{timestamp}] {message}"
        if self.verbose:
            print(line)
        with open(os.path.join(self.logs_dir, 'experiment.log'), 'a',
                  encoding='utf-8') as f:
            f.write(line + '\n')

    def add_milestone(self, milestone_id: str, name: str):
        """添加一个实验里程碑"""
        self.milestones[milestone_id] = []
        self.log(f"注册里程碑: {milestone_id} - {name}")

    def add_experiment(self, milestone_id: str, exp_id: str,
                        name: str, func: Callable, **kwargs):
        """向里程碑添加实验"""
        if milestone_id not in self.milestones:
            self.milestones[milestone_id] = []
        self.milestones[milestone_id].append({
            'id': exp_id, 'name': name, 'func': func, 'kwargs': kwargs
        })

    def run_experiment(self, exp_id: str, name: str,
                        func: Callable, **kwargs) -> Dict:
        """运行单个实验并返回结果"""
        self.log(f"  >>> 开始: {exp_id} - {name}")
        t0 = time.time()
        try:
            result = func(**kwargs)
            elapsed = time.time() - t0
            self.log(f"  <<< 完成: {exp_id} ({elapsed:.1f}s)")
            return {'status': 'success', 'result': result, 'time': elapsed,
                    'timestamp': datetime.now().isoformat()}
        except Exception as e:
            elapsed = time.time() - t0
            self.log(f"  <<< 失败: {exp_id} - {str(e)}")
            return {'status': 'failed', 'error': str(e), 'time': elapsed,
                    'timestamp': datetime.now().isoformat()}

    def run_milestone(self, milestone_id: str):
        """运行指定里程碑的所有实验"""
        if milestone_id not in self.milestones:
            self.log(f"警告: 里程碑 {milestone_id} 不存在")
            return

        exps = self.milestones[milestone_id]
        self.log(f"\n{'='*60}")
        self.log(f"执行里程碑: {milestone_id} ({len(exps)} 个实验)")
        self.log(f"{'='*60}")

        results = {}
        for exp in exps:
            results[exp['id']] = self.run_experiment(
                exp['id'], exp['name'], exp['func'], **exp['kwargs']
            )

        self.all_results[milestone_id] = results
        return results

    def run_all(self):
        """运行所有里程碑的所有实验"""
        self.log("=" * 60)
        self.log("开始执行所有实验")
        self.log("=" * 60)

        for milestone_id in self.milestones:
            self.run_milestone(milestone_id)

        self.generate_report()
        self.log("=" * 60)
        self.log("所有实验完成!")
        self.log("=" * 60)

    def generate_report(self) -> str:
        """生成 Markdown 实验报告"""
        report = "# 实验结果报告\n\n"
        report += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += "---\n\n"
        report += "## 结果汇总\n\n"

        total_success = 0
        total_failed = 0
        total_time = 0

        for milestone_id, results in self.all_results.items():
            report += f"### {milestone_id}\n\n"
            report += "| 实验 | 状态 | 耗时(s) |\n"
            report += "|------|------|--------|\n"

            for exp_id, result in results.items():
                status = "OK" if result['status'] == 'success' else "FAIL"
                time_str = f"{result['time']:.1f}" if 'time' in result else "-"
                report += f"| {exp_id} | {status} | {time_str} |\n"

                if result['status'] == 'success':
                    total_success += 1
                else:
                    total_failed += 1
                total_time += result.get('time', 0)

            report += "\n"

        report += "## 统计\n\n"
        report += f"| 指标 | 值 |\n"
        report += f"|------|----|\n"
        report += f"| 总实验数 | {total_success + total_failed} |\n"
        report += f"| 成功 | {total_success} |\n"
        report += f"| 失败 | {total_failed} |\n"
        report += f"| 总耗时 | {total_time:.1f}s ({total_time/60:.1f}min) |\n"

        # 保存报告
        report_path = os.path.join(self.results_dir, 'EXPERIMENT_REPORT.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        # 保存 JSON 详细结果
        json_path = os.path.join(self.results_dir, 'experiment_results.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_results, f, indent=2, default=str,
                      ensure_ascii=False)

        self.log(f"报告已保存: {report_path}")
        return report

    def get_passed_count(self) -> int:
        """获取通过实验数"""
        passed = 0
        for results in self.all_results.values():
            for r in results.values():
                if r['status'] == 'success':
                    passed += 1
        return passed

    def get_failed_count(self) -> int:
        """获取失败实验数"""
        failed = 0
        for results in self.all_results.values():
            for r in results.values():
                if r['status'] == 'failed':
                    failed += 1
        return failed

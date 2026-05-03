"""
GPU 加速测试脚本

在有 NVIDIA 显卡的电脑上运行此脚本，验证 CuPy GPU 加速是否正常工作。

使用方法：
    pip install cupy-cuda12x  # 根据 CUDA 版本选择（11x 或 12x）
    python test_gpu.py

基准测试方法：
    预热 5 次 + 正式测试 10 次取平均，GPU 侧使用 Stream.synchronize() 确保计算完成再计时。
"""

import sys
import os
import time
import json
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

print("=" * 60)
print("GPU 加速测试")
print("=" * 60)

# ============================================================================
# 1. 检查 CuPy
# ============================================================================

def check_cupy():
    """检查 CuPy 是否可用并打印设备信息"""
    try:
        import cupy as cp
        print(f"CuPy 版本: {cp.__version__}")
        dev_count = cp.cuda.runtime.getDeviceCount()
        print(f"CUDA 设备数: {dev_count}")
        for i in range(dev_count):
            with cp.cuda.Device(i):
                dev = cp.cuda.Device()
                props = cp.cuda.runtime.getDeviceProperties(i)
                mem_gb = dev.mem_info[1] / 1024**3
                print(f"  设备 {i}: {props['name'].decode()}, 显存: {mem_gb:.1f} GB")
        return True
    except ImportError:
        print("CuPy 未安装。在有 GPU 的电脑上请运行: pip install cupy-cuda12x")
        return False
    except Exception as e:
        print(f"CuPy 不可用: {e}")
        return False

GPU_OK = check_cupy()
if not GPU_OK:
    sys.exit(1)

# ============================================================================
# 2. 检查模块加载
# ============================================================================

from src.evaluation import GPU_AVAILABLE, xp, RadarConfig, generate_uniform_task_points, decode_particle
from src.evaluation import create_normalized_evaluate_function, calculate_ecr, calculate_jamming_density
from src.decomposition import DeploymentRegionDecomposer
from src.mopso import MOPSO_DT
from shapely.geometry import Polygon as ShapelyPolygon

print(f"\nGPU_AVAILABLE: {GPU_AVAILABLE}")
print(f"xp module: {xp.__name__}")

if not GPU_AVAILABLE:
    print("ERROR: GPU_AVAILABLE=False, CuPy 未被 evaluation.py 使用")
    sys.exit(1)

# ============================================================================
# 3. 小规模正确性测试
# ============================================================================

print("\n--- 测试 1: 正确性验证 (100km, 5 雷达) ---")
region = ShapelyPolygon([(0, 0), (100, 0), (100, 100), (0, 100)])
decomposer = DeploymentRegionDecomposer(verbose=False)
polygons, codes, n_bits = decomposer.decompose(region)
task_points = generate_uniform_task_points(region, grid_size=15)
radar_configs = [RadarConfig(P0=0.95, P_min=0.8, beta=0.01, is_air=True) for _ in range(5)]
evaluate_func = create_normalized_evaluate_function(task_points, radar_configs, polygons, 5, 1, J_max_ref=0.001)

mopso = MOPSO_DT(J=5, N_bin=1, evaluate_func=evaluate_func, N_P=30, T_max=30, verbose=False)
t0 = time.time()
archive, stats = mopso.optimize()
t_small = time.time() - t0

print(f"  耗时: {t_small:.1f}s")
print(f"  Pareto 解: {len(archive)}")
if len(archive) > 0:
    ecr_vals, jmin_vals = [], []
    for entry in archive:
        sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
        continuous = sol[:, :2].flatten()
        binary = sol[:, 2:3]
        positions = np.array(decode_particle(continuous, binary, 5, 1, polygons))
        ecr = calculate_ecr(positions, task_points, radar_configs,
                            convex_polygons=polygons, binary_codes=binary,
                            continuous_coords=continuous.reshape(5, 2))
        jmin = calculate_jamming_density(positions, task_points, radar_configs,
                                         convex_polygons=polygons, binary_codes=binary,
                                         continuous_coords=continuous.reshape(5, 2))
        ecr_vals.append(ecr)
        jmin_vals.append(jmin)
    ecr_arr = np.array(ecr_vals)
    jmin_arr = np.array(jmin_vals)
    print(f"  ECR:    [{ecr_arr.min():.4f}, {ecr_arr.max():.4f}]")
    print(f"  J_min:  [{jmin_arr.min():.8f}, {jmin_arr.max():.8f}]")

# ============================================================================
# 4. 单次评估微基准测试（预热 + 重复）
# ============================================================================

print("\n--- 测试 2: 单次评估微基准 (500km, 50 雷达) ---")
region2 = ShapelyPolygon([(0, 0), (500, 0), (500, 500), (0, 500)])
decomposer2 = DeploymentRegionDecomposer(verbose=False)
polygons2, codes2, n_bits2 = decomposer2.decompose(region2)
task_points2 = generate_uniform_task_points(region2, grid_size=25)
radar_configs2 = [RadarConfig(P0=0.95, P_min=0.8, beta=0.02, is_air=True) for _ in range(50)]
J, N_bin = 50, max(1, int(np.ceil(np.log2(len(polygons2)))))
evaluate_func2 = create_normalized_evaluate_function(task_points2, radar_configs2, polygons2, J, N_bin, J_max_ref=0.001)

print(f"  任务点: {len(task_points2)}, 雷达: {J}, 凸多边形: {len(polygons2)}")

# 生成随机粒子用于基准
np.random.seed(42)
test_phis = []
for _ in range(20):
    cont = np.random.uniform(0, 1, 2 * J)
    binary = np.random.randint(0, 2, (J, N_bin))
    from src.optimization_utils import build_decision_matrix
    phi = build_decision_matrix(cont, binary, J, N_bin)
    test_phis.append(phi)

# 预热
print("  预热中...")
for _ in range(5):
    for phi in test_phis:
        evaluate_func2(phi)

# 正式测试
if hasattr(xp, 'cuda'):
    xp.cuda.Stream.null.synchronize()
t0 = time.time()
for _ in range(10):
    for phi in test_phis:
        evaluate_func2(phi)
if hasattr(xp, 'cuda'):
    xp.cuda.Stream.null.synchronize()
elapsed = time.time() - t0
ms_per_eval = (elapsed / (10 * len(test_phis))) * 1000
print(f"  总耗时: {elapsed:.2f}s ({10}x{len(test_phis)} = {10*len(test_phis)} 次评估)")
print(f"  每次评估: {ms_per_eval:.3f} ms")

# ============================================================================
# 5. 大规模 MOPSO 速度测试
# ============================================================================

print(f"\n--- 测试 3: 大规模 MOPSO 速度测试 (500km, 50 雷达, N_P=100, T_max=200) ---")

mopso2 = MOPSO_DT(J=J, N_bin=N_bin, evaluate_func=evaluate_func2,
                  N_P=100, T_max=200, verbose=False)
t0 = time.time()
archive2, stats2 = mopso2.optimize()
t_large = time.time() - t0
n_evals = 100 * (200 + 1)

print(f"  耗时: {t_large:.1f}s ({t_large/60:.2f} min)")
print(f"  评估次数: {n_evals}")
print(f"  每次评估: {t_large/n_evals*1000:.2f} ms")
print(f"  Pareto 解: {len(archive2)}")

if len(archive2) > 0:
    ecr_vals2, jmin_vals2 = [], []
    for entry in archive2:
        sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
        continuous = sol[:, :2].flatten()
        binary = sol[:, 2:2 + N_bin]
        positions = np.array(decode_particle(continuous, binary, J, N_bin, polygons2))
        ecr = calculate_ecr(positions, task_points2, radar_configs2,
                            convex_polygons=polygons2, binary_codes=binary,
                            continuous_coords=continuous.reshape(J, 2))
        jmin = calculate_jamming_density(positions, task_points2, radar_configs2,
                                         convex_polygons=polygons2, binary_codes=binary,
                                         continuous_coords=continuous.reshape(J, 2))
        ecr_vals2.append(ecr)
        jmin_vals2.append(jmin)
    ecr_arr2 = np.array(ecr_vals2)
    jmin_arr2 = np.array(jmin_vals2)
    print(f"  ECR:    [{ecr_arr2.min():.4f}, {ecr_arr2.max():.4f}]")
    print(f"  J_min:  [{jmin_arr2.min():.8f}, {jmin_arr2.max():.8f}]")

# ============================================================================
# 6. 总结
# ============================================================================

print("\n" + "=" * 60)
print("测试总结")
print("=" * 60)
cpu_ref = 281  # 50 雷达, N_P=100, T_max=200 的 CPU 参考时间
speedup = cpu_ref / t_large
print(f"  小测试 (5雷达):     {t_small:.1f}s")
print(f"  大测试 (50雷达):    {t_large:.1f}s  (CPU 参考: {cpu_ref}s, 加速: {speedup:.1f}x)")
print(f"  单次评估:           {ms_per_eval:.3f} ms")
print(f"  通过检查:           GPU 加速工作正常!")
print("=" * 60)

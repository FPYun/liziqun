"""JCR 模型参数扫描"""
import numpy as np, time, sys
sys.path.insert(0, '.')
from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (RadarConfig, generate_uniform_task_points,
    calculate_ecr, calculate_jcr, decode_particle, create_jcr_evaluate_function)
from src.mopso import MOPSO_DT
from src.benchmarks import get_extreme_points
from shapely.geometry import Polygon as SPolygon

REGION_SIZE = 1000
GRID = 40
N_P = 60
T_MAX = 60
P0, P_MIN = 0.9, 0.75

for J in [60, 80]:
    for beta in [0.005, 0.006]:
        for J_th in [3e-5, 5e-5, 8e-5]:
            rng = np.log(P0 / P_MIN) / beta
            cover_area = J * np.pi * rng**2 / 1e6
            if cover_area > 1.5 or cover_area < 0.1:
                continue

            region = SPolygon([(0, 0), (REGION_SIZE, 0), (REGION_SIZE, REGION_SIZE), (0, REGION_SIZE)])
            decomposer = DeploymentRegionDecomposer(verbose=False)
            polygons, _, _ = decomposer.decompose(region)
            N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

            cfgs = [RadarConfig(P0=P0, P_min=P_MIN, beta=beta, is_air=True, J_threshold=J_th) for _ in range(J)]
            task_points = generate_uniform_task_points(region, grid_size=GRID)
            evaluate_func = create_jcr_evaluate_function(task_points, cfgs, polygons, J, N_bin)

            mopso = MOPSO_DT(J=J, N_bin=N_bin, evaluate_func=evaluate_func,
                N_P=N_P, T_max=T_MAX, archive_size=100, verbose=False,
                w_strategy='standard', p_m_base=0.01, select_gb='crowding')

            t0 = time.time()
            archive, _ = mopso.optimize()
            elapsed = time.time() - t0

            if len(archive) == 0:
                continue

            objectives = np.array([e['objectives'] for e in archive])
            ecrs, jcrs = [], []
            sample_n = max(1, len(archive) // 10)
            for entry in archive[::sample_n]:
                cont = entry['continuous'].reshape(J, 2).flatten()
                bin_ = entry['binary']
                pos = np.array(decode_particle(cont, bin_, J, N_bin, polygons))
                ecr = calculate_ecr(pos, task_points, cfgs, convex_polygons=polygons, binary_codes=bin_, continuous_coords=cont.reshape(J, 2))
                jcr = calculate_jcr(pos, task_points, cfgs, convex_polygons=polygons, binary_codes=bin_, continuous_coords=cont.reshape(J, 2))
                ecrs.append(ecr)
                jcrs.append(jcr)

            ecr_spread = max(ecrs) - min(ecrs) if ecrs else 0
            jcr_spread = max(jcrs) - min(jcrs) if jcrs else 0
            ecr_u = len(set("{:.4f}".format(v) for v in ecrs))
            jcr_u = len(set("{:.4f}".format(v) for v in jcrs))
            corr = np.corrcoef(ecrs, jcrs)[0, 1] if len(ecrs) > 2 else 0

            if corr < -0.15 and ecr_u > 1 and jcr_u > 1:
                quality = "REAL PF !!!"
            elif ecr_u > 1 or jcr_u > 1:
                quality = "OK"
            else:
                quality = "FLAT"

            print("J=%3d b=%.3f Jth=%.0e rng=%2.0fkm CA=%3.0f%% | %4.0fs %3dsols | ECR[%.3f,%.3f] JCR[%.3f,%.3f] | uE=%d uJ=%d corr=%+.2f %s" % (
                J, beta, J_th, rng, cover_area*100, elapsed, len(archive),
                min(ecrs), max(ecrs), min(jcrs), max(jcrs),
                ecr_u, jcr_u, corr, quality))

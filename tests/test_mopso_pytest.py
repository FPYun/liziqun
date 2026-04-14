"""
MOPSO-DT 的 pytest 测试套件

运行方式:
    pytest tests/test_mopso_pytest.py -v
    pytest tests/test_mopso_pytest.py -v --cov=src
"""

import numpy as np
import pytest
from unittest.mock import Mock, MagicMock
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.mopso import MOPSO_DT, Particle
from src.exceptions import (
    InvalidParameterError,
    EvaluationError,
    MOPSOError
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_evaluate_func():
    """模拟评估函数"""
    def evaluate(Phi):
        # 简单测试函数
        f1 = np.mean(Phi[:, 0])
        f2 = np.std(Phi[:, 1])
        return np.array([f1, f2])
    return evaluate


@pytest.fixture
def mopso_instance(mock_evaluate_func):
    """创建标准 MOPSO 实例"""
    return MOPSO_DT(
        J=3,
        N_bin=2,
        evaluate_func=mock_evaluate_func,
        N_P=20,
        T_max=50,
        verbose=False
    )


@pytest.fixture
def sample_particle():
    """创建示例粒子"""
    return Particle(
        position_continuous=np.array([0.5, 0.5, 0.3, 0.7, 0.2, 0.8]),
        velocity_continuous=np.zeros(6),
        position_binary=np.array([[1, 0], [0, 1], [1, 1]]),
        pb_continuous=np.array([0.5, 0.5, 0.3, 0.7, 0.2, 0.8]),
        pb_binary=np.array([[1, 0], [0, 1], [1, 1]])
    )


# ==================== 参数验证测试 ====================

class TestParameterValidation:
    """测试参数验证"""

    def test_invalid_J(self, mock_evaluate_func):
        """测试无效的雷达节点数"""
        with pytest.raises(InvalidParameterError) as exc_info:
            MOPSO_DT(J=0, N_bin=2, evaluate_func=mock_evaluate_func)
        assert "J" in str(exc_info.value)

    def test_invalid_N_bin(self, mock_evaluate_func):
        """测试无效的区域编码位数"""
        with pytest.raises(InvalidParameterError) as exc_info:
            MOPSO_DT(J=3, N_bin=-1, evaluate_func=mock_evaluate_func)
        assert "N_bin" in str(exc_info.value)

    def test_invalid_N_P(self, mock_evaluate_func):
        """测试无效的粒子数"""
        with pytest.raises(InvalidParameterError) as exc_info:
            MOPSO_DT(J=3, N_bin=2, evaluate_func=mock_evaluate_func, N_P=0)
        assert "N_P" in str(exc_info.value)

    def test_invalid_T_max(self, mock_evaluate_func):
        """测试无效的迭代次数"""
        with pytest.raises(InvalidParameterError) as exc_info:
            MOPSO_DT(J=3, N_bin=2, evaluate_func=mock_evaluate_func, T_max=-10)
        assert "T_max" in str(exc_info.value)

    def test_invalid_c1(self, mock_evaluate_func):
        """测试无效的认知因子"""
        with pytest.raises(InvalidParameterError) as exc_info:
            MOPSO_DT(J=3, N_bin=2, evaluate_func=mock_evaluate_func, c_1=10)
        assert "c_1" in str(exc_info.value)

    def test_invalid_p_c(self, mock_evaluate_func):
        """测试无效的交叉概率"""
        with pytest.raises(InvalidParameterError) as exc_info:
            MOPSO_DT(J=3, N_bin=2, evaluate_func=mock_evaluate_func, p_c=1.5)
        assert "p_c" in str(exc_info.value)


# ==================== 核心功能测试 ====================

class TestCoreFunctionality:
    """测试核心功能"""

    def test_initialization(self, mopso_instance):
        """测试粒子群初始化"""
        mopso_instance._initialize()

        assert len(mopso_instance.particles) == 20
        for particle in mopso_instance.particles:
            # 验证连续变量范围
            assert np.all(particle.position_continuous >= 0)
            assert np.all(particle.position_continuous <= 1)
            # 验证二进制变量
            assert np.all((particle.position_binary == 0) | (particle.position_binary == 1))
            # 验证速度为零
            assert np.all(particle.velocity_continuous == 0)

    def test_build_decision_matrix(self, mopso_instance):
        """测试决策变量矩阵构建"""
        continuous = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        binary = np.array([[1, 0], [0, 1], [1, 1]])

        Phi = mopso_instance._build_decision_matrix(continuous, binary)

        assert Phi.shape == (3, 4)  # (J, 2+N_bin)
        assert np.allclose(Phi[:, 0], [0.1, 0.3, 0.5])  # hat_x
        assert np.allclose(Phi[:, 1], [0.2, 0.4, 0.6])  # hat_y
        assert np.array_equal(Phi[:, 2:], binary)

    def test_dominates_coverage_better(self, mopso_instance):
        """测试覆盖率更优的支配关系"""
        obj1 = np.array([0.9, 0.3])  # 高覆盖率，低干扰
        obj2 = np.array([0.7, 0.4])  # 低覆盖率，高干扰

        assert mopso_instance._dominates(obj1, obj2) == True
        assert mopso_instance._dominates(obj2, obj1) == False

    def test_dominates_interference_better(self, mopso_instance):
        """测试干扰更优的支配关系"""
        obj1 = np.array([0.8, 0.2])  # 低干扰
        obj2 = np.array([0.8, 0.5])  # 高干扰

        assert mopso_instance._dominates(obj1, obj2) == True

    def test_dominates_equal(self, mopso_instance):
        """测试相等目标的非支配关系"""
        obj1 = np.array([0.8, 0.3])
        obj2 = np.array([0.8, 0.3])

        assert mopso_instance._dominates(obj1, obj2) == False

    def test_dominates_trade_off(self, mopso_instance):
        """测试权衡情况的非支配关系"""
        obj1 = np.array([0.9, 0.5])  # 高覆盖率但高干扰
        obj2 = np.array([0.7, 0.2])  # 低覆盖率但低干扰

        # 互不支配
        assert mopso_instance._dominates(obj1, obj2) == False
        assert mopso_instance._dominates(obj2, obj1) == False


# ==================== 拥挤度距离测试 ====================

class TestCrowdingDistance:
    """测试拥挤度距离计算"""

    def test_crowding_distance_calculation(self, mopso_instance):
        """测试拥挤度距离计算"""
        # 设置测试档案
        mopso_instance.archive = [
            {'objectives': np.array([0.0, 1.0])},
            {'objectives': np.array([0.25, 0.75])},
            {'objectives': np.array([0.5, 0.5])},
            {'objectives': np.array([0.75, 0.25])},
            {'objectives': np.array([1.0, 0.0])},
        ]

        distances = mopso_instance._calculate_crowding_distance()

        assert len(distances) == 5
        assert np.isinf(distances[0])  # 边界解
        assert np.isinf(distances[4])  # 边界解
        assert distances[2] > 0  # 中间解应有正距离

    def test_crowding_distance_two_solutions(self, mopso_instance):
        """测试只有两个解的情况"""
        mopso_instance.archive = [
            {'objectives': np.array([0.0, 1.0])},
            {'objectives': np.array([1.0, 0.0])},
        ]

        distances = mopso_instance._calculate_crowding_distance()

        assert len(distances) == 2
        assert np.isinf(distances[0])
        assert np.isinf(distances[1])


# ==================== 档案管理测试 ====================

class TestArchiveManagement:
    """测试档案管理"""

    def test_add_to_archive(self, mopso_instance):
        """测试添加到档案"""
        continuous = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        binary = np.array([[1, 0], [0, 1], [1, 1]])
        objectives = np.array([0.8, 0.2])

        mopso_instance._add_to_archive(continuous, binary, objectives)

        assert len(mopso_instance.archive) == 1
        assert np.array_equal(mopso_instance.archive[0]['continuous'], continuous)
        assert np.array_equal(mopso_instance.archive[0]['objectives'], objectives)

    def test_nondominated_sorting(self, mopso_instance):
        """测试非劣排序"""
        # 添加测试解（包含被支配的）
        mopso_instance.archive = [
            {'objectives': np.array([0.9, 0.1])},  # 非劣
            {'objectives': np.array([0.8, 0.2])},  # 被第一个支配
            {'objectives': np.array([0.7, 0.15])}, # 非劣
            {'objectives': np.array([0.95, 0.05])}, # 非劣，支配第一个
        ]

        mopso_instance._nondominated_sorting()

        # 应该只剩非劣解
        assert len(mopso_instance.archive) <= 3

    def test_maintain_archive_size_limit(self, mopso_instance):
        """测试档案大小限制"""
        mopso_instance.archive_size = 3

        # 添加超过限制的解
        for i in range(5):
            mopso_instance.archive.append({
                'objectives': np.array([i/5, 1-i/5]),
                'crowding_distance': 0.0
            })

        mopso_instance._maintain_archive()

        assert len(mopso_instance.archive) <= 3


# ==================== 参数计算测试 ====================

class TestParameterCalculation:
    """测试参数计算"""

    def test_inertia_weight_initial(self, mopso_instance):
        """测试初始惯性权重"""
        w = mopso_instance._calculate_inertia_weight(1)
        expected = -0.4 / 50 * 1 + 0.4
        assert abs(w - expected) < 1e-10

    def test_inertia_weight_final(self, mopso_instance):
        """测试最终惯性权重"""
        w = mopso_instance._calculate_inertia_weight(50)
        expected = -0.4 / 50 * 50 + 0.4
        assert abs(w - expected) < 1e-10

    def test_mutation_probability(self, mopso_instance):
        """测试变异概率计算"""
        w = 0.3
        p_m = mopso_instance._calculate_mutation_probability(w)
        expected = w / 20  # N_P = 20
        assert abs(p_m - expected) < 1e-10


# ==================== 评估函数测试 ====================

class TestEvaluation:
    """测试评估功能"""

    def test_evaluate_particle_success(self, mopso_instance, sample_particle):
        """测试正常评估"""
        objectives = mopso_instance._evaluate_particle(sample_particle, particle_idx=0)

        assert isinstance(objectives, np.ndarray)
        assert objectives.shape == (2,)

    def test_evaluate_particle_out_of_bounds(self, mopso_instance, sample_particle):
        """测试超出范围的坐标"""
        sample_particle.position_continuous[0] = 1.5  # 超出[0,1]

        with pytest.raises(EvaluationError) as exc_info:
            mopso_instance._evaluate_particle(sample_particle, particle_idx=0)

        assert "超出" in str(exc_info.value)

    def test_evaluate_particle_function_error(self, mopso_instance, sample_particle):
        """测试评估函数出错"""
        mopso_instance.evaluate_func = Mock(side_effect=Exception("计算错误"))

        with pytest.raises(EvaluationError) as exc_info:
            mopso_instance._evaluate_particle(sample_particle, particle_idx=0)

        assert "评估失败" in str(exc_info.value)


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试"""

    def test_full_optimization(self, mock_evaluate_func):
        """测试完整优化流程"""
        mopso = MOPSO_DT(
            J=2,
            N_bin=2,
            evaluate_func=mock_evaluate_func,
            N_P=10,
            T_max=20,
            archive_size=10,
            verbose=False
        )

        archive, stats = mopso.optimize()

        assert len(archive) > 0
        assert 'final_archive_size' in stats
        assert 'coverage_max' in stats
        assert 'interference_min' in stats

    def test_get_pareto_front(self, mock_evaluate_func):
        """测试获取Pareto前沿"""
        mopso = MOPSO_DT(
            J=2,
            N_bin=2,
            evaluate_func=mock_evaluate_func,
            N_P=10,
            T_max=10,
            verbose=False
        )

        mopso.optimize()
        continuous, binary, objectives = mopso.get_pareto_front()

        assert len(continuous) == len(binary) == len(objectives)
        if len(objectives) > 0:
            assert objectives.shape[1] == 2  # 两个目标


# ==================== 性能测试 ====================

@pytest.mark.slow
class TestPerformance:
    """性能测试（标记为慢测试）"""

    def test_large_scale_optimization(self, mock_evaluate_func):
        """测试大规模优化"""
        mopso = MOPSO_DT(
            J=20,
            N_bin=5,
            evaluate_func=mock_evaluate_func,
            N_P=100,
            T_max=100,
            verbose=False
        )

        import time
        start = time.time()
        archive, _ = mopso.optimize()
        elapsed = time.time() - start

        print(f"\n大规模优化耗时: {elapsed:.2f}s")
        assert elapsed < 60  # 应该在60秒内完成


# ==================== 主程序 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

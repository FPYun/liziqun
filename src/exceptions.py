"""
自定义异常模块

定义项目中使用的所有自定义异常类型
"""

from typing import Optional


class RadarDeploymentError(Exception):
    """雷达部署优化项目的基类异常"""
    pass


# ==================== 区域分解相关异常 ====================

class DecompositionError(RadarDeploymentError):
    """区域分解算法错误"""
    pass


class InvalidPolygonError(DecompositionError):
    """无效的多边形输入"""

    def __init__(self, message: str = "无效的多边形", details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}


class HoleEliminationError(DecompositionError):
    """空洞消除失败"""
    pass


class ConvexDecompositionError(DecompositionError):
    """凸分解失败"""
    pass


class ConnectivityError(DecompositionError):
    """连通性判断错误"""
    pass


class BinaryCodingError(DecompositionError):
    """二进制编码分配错误"""
    pass


# ==================== 坐标变换相关异常 ====================

class TransformError(RadarDeploymentError):
    """坐标变换错误"""
    pass


class NonConvexPolygonError(TransformError):
    """非凸多边形错误（坐标变换要求凸多边形）"""

    def __init__(self, message: str = "输入多边形必须是凸多边形"):
        super().__init__(message)


class OutOfBoundsError(TransformError):
    """坐标超出边界"""

    def __init__(self, value: float, bounds: tuple):
        message = f"值 {value} 超出边界 {bounds}"
        super().__init__(message)
        self.value = value
        self.bounds = bounds


class IntersectionError(TransformError):
    """垂直线交集计算错误"""
    pass


# ==================== MOPSO相关异常 ====================

class MOPSOError(RadarDeploymentError):
    """MOPSO优化错误"""
    pass


class InvalidParameterError(MOPSOError):
    """无效参数"""

    def __init__(self, param_name: str, value, expected: str):
        message = f"参数 '{param_name}' 的值 {value} 无效，期望: {expected}"
        super().__init__(message)
        self.param_name = param_name
        self.value = value
        self.expected = expected


class EvaluationError(MOPSOError):
    """目标函数评估错误"""

    def __init__(self, message: str = "评估函数执行失败", particle_idx: Optional[int] = None):
        super().__init__(message)
        self.particle_idx = particle_idx


class ArchiveError(MOPSOError):
    """外部档案操作错误"""
    pass


class ConvergenceError(MOPSOError):
    """算法未能收敛"""

    def __init__(self, message: str = "算法在最大迭代次数内未能收敛", iterations: Optional[int] = None):
        super().__init__(message)
        self.iterations = iterations


# ==================== 可视化相关异常 ====================

class VisualizationError(RadarDeploymentError):
    """可视化错误"""
    pass


class SaveFigureError(VisualizationError):
    """保存图像失败"""

    def __init__(self, filepath: str, reason: Optional[str] = None):
        message = f"无法保存图像到 {filepath}"
        if reason:
            message += f": {reason}"
        super().__init__(message)
        self.filepath = filepath


# ==================== 工具函数 ====================

def handle_exception(func):
    """
    异常处理装饰器

    捕获函数执行中的异常，转换为项目自定义异常
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RadarDeploymentError:
            # 已经是我们定义的异常，直接抛出
            raise
        except ValueError as e:
            raise InvalidPolygonError(f"输入值错误: {str(e)}")
        except TypeError as e:
            raise RadarDeploymentError(f"类型错误: {str(e)}")
        except Exception as e:
            raise RadarDeploymentError(f"未预期的错误: {str(e)}") from e

    return wrapper


# 使用示例
if __name__ == "__main__":
    try:
        # 模拟错误
        raise InvalidPolygonError(
            "多边形顶点不足",
            details={"n_vertices": 2, "min_required": 3}
        )
    except InvalidPolygonError as e:
        print(f"捕获异常: {e}")
        print(f"详情: {e.details}")

    try:
        raise InvalidParameterError("N_P", -5, "正整数")
    except InvalidParameterError as e:
        print(f"\n参数错误: {e}")
        print(f"参数名: {e.param_name}")
        print(f"输入值: {e.value}")
        print(f"期望值: {e.expected}")

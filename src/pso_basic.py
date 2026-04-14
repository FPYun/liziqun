"""
粒子群优化算法（PSO）实现
用于连续函数优化问题

使用方法：
    from pso import PSO, sphere, rosenbrock

    # 创建优化器
    pso = PSO(objective_func=sphere, dimensions=2, bounds=(-5, 5))

    # 执行优化
    best_position, best_value, history = pso.optimize()

    print(f"最佳位置: {best_position}")
    print(f"最佳适应度: {best_value}")
"""

import numpy as np
import time


class Particle:
    """粒子类，表示搜索空间中的一个候选解"""

    def __init__(self, dimensions, bounds):
        """
        初始化粒子

        参数:
            dimensions: 问题维度
            bounds: 边界，格式为(low, high)或每个维度的边界列表
        """
        # 解析边界
        if isinstance(bounds, (int, float)):
            self.bounds = [(bounds, bounds)] * dimensions
        elif len(bounds) == 2 and isinstance(bounds[0], (int, float)):
            # 所有维度使用相同的边界
            self.bounds = [bounds] * dimensions
        else:
            # 每个维度有独立的边界
            self.bounds = bounds

        # 初始化位置（在边界内随机生成）
        self.position = np.array([
            np.random.uniform(low, high) for low, high in self.bounds
        ])

        # 初始化速度为零
        self.velocity = np.zeros(dimensions)

        # 个体最佳位置和适应度
        self.best_position = self.position.copy()
        self.best_value = float('inf')

        # 当前位置的适应度
        self.value = float('inf')


class PSO:
    """粒子群优化器"""

    def __init__(self, objective_func, dimensions=2, n_particles=30,
                 max_iter=100, inertia=0.7298, cognitive=1.49618,
                 social=1.49618, bounds=(-10, 10),
                 boundary_strategy='reflect', verbose=True):
        """
        初始化PSO优化器

        参数:
            objective_func: 目标函数（需要最小化的函数）
            dimensions: 问题维度
            n_particles: 粒子数量
            max_iter: 最大迭代次数
            inertia: 惯性权重
            cognitive: 认知系数
            social: 社会系数
            bounds: 搜索空间边界，格式为(low, high)或列表
            boundary_strategy: 边界处理策略 ('reflect', 'absorb', 'clamp')
            verbose: 是否显示进度信息
        """
        self.objective_func = objective_func
        self.dimensions = dimensions
        self.n_particles = n_particles
        self.max_iter = max_iter
        self.inertia = inertia
        self.cognitive = cognitive
        self.social = social
        self.bounds = bounds
        self.boundary_strategy = boundary_strategy
        self.verbose = verbose

        # 解析边界格式
        if isinstance(bounds, (int, float)):
            self.bounds_list = [(bounds, bounds)] * dimensions
        elif len(bounds) == 2 and isinstance(bounds[0], (int, float)):
            self.bounds_list = [bounds] * dimensions
        else:
            self.bounds_list = bounds

        # 粒子群和全局最佳
        self.particles = []
        self.global_best_position = None
        self.global_best_value = float('inf')

        # 历史记录
        self.history = []

        # 记录开始时间
        self.start_time = None

    def optimize(self):
        """
        执行优化过程

        返回:
            best_position: 全局最佳位置
            best_value: 全局最佳适应度
            history: 每次迭代的最佳适应度历史
        """
        self.start_time = time.time()
        self._initialize_particles()

        if self.verbose:
            print(f"开始PSO优化（{self.dimensions}维，{self.n_particles}个粒子）")
            print(f"边界: {self.bounds}")
            print(f"策略: {self.boundary_strategy}")
            print("-" * 50)

        # 主优化循环
        for iteration in range(self.max_iter):
            # 更新所有粒子
            for particle in self.particles:
                self._update_particle(particle)

            # 评估所有粒子
            self._evaluate_particles()

            # 记录历史
            self.history.append(self.global_best_value)

            # 显示进度
            if self.verbose and iteration % 10 == 0:
                elapsed = time.time() - self.start_time
                print(f"迭代 {iteration:3d}/{self.max_iter}: "
                      f"最佳适应度 = {self.global_best_value:.8f} "
                      f"时间: {elapsed:.2f}s")

        # 优化完成
        elapsed = time.time() - self.start_time

        if self.verbose:
            print("-" * 50)
            print(f"优化完成！")
            print(f"总时间: {elapsed:.2f}秒")
            print(f"迭代次数: {self.max_iter}")
            print(f"最佳适应度: {self.global_best_value:.8f}")
            print(f"最佳位置: {self.global_best_position}")

        return self.global_best_position, self.global_best_value, self.history

    def _initialize_particles(self):
        """初始化粒子群"""
        self.particles = []

        for _ in range(self.n_particles):
            # 创建粒子
            particle = Particle(self.dimensions, self.bounds)

            # 计算初始适应度
            particle.value = self.objective_func(particle.position)
            particle.best_value = particle.value
            particle.best_position = particle.position.copy()

            # 更新全局最佳
            if particle.value < self.global_best_value:
                self.global_best_value = particle.value
                self.global_best_position = particle.position.copy()

            self.particles.append(particle)

    def _update_particle(self, particle):
        """更新单个粒子的速度和位置"""
        # 生成随机因子
        r1 = np.random.rand(self.dimensions)
        r2 = np.random.rand(self.dimensions)

        # 速度更新公式: v = w*v + c1*r1*(pbest - x) + c2*r2*(gbest - x)
        cognitive = self.cognitive * r1 * (particle.best_position - particle.position)
        social = self.social * r2 * (self.global_best_position - particle.position)
        particle.velocity = (self.inertia * particle.velocity +
                           cognitive + social)

        # 位置更新
        particle.position += particle.velocity

        # 边界处理
        self._apply_boundary(particle)

    def _apply_boundary(self, particle):
        """应用边界处理策略"""
        if self.boundary_strategy == 'reflect':
            # 反射边界：粒子超出边界时反射回来，速度减半
            for i in range(self.dimensions):
                low, high = self.bounds_list[i]

                if particle.position[i] < low:
                    particle.position[i] = 2 * low - particle.position[i]
                    particle.velocity[i] = -particle.velocity[i] * 0.5
                elif particle.position[i] > high:
                    particle.position[i] = 2 * high - particle.position[i]
                    particle.velocity[i] = -particle.velocity[i] * 0.5

        elif self.boundary_strategy == 'absorb':
            # 吸收边界：粒子超出边界时停留在边界上，速度归零
            for i in range(self.dimensions):
                low, high = self.bounds_list[i]

                if particle.position[i] < low:
                    particle.position[i] = low
                    particle.velocity[i] = 0
                elif particle.position[i] > high:
                    particle.position[i] = high
                    particle.velocity[i] = 0

        else:  # 'clamp' 或默认
            # 简单限制在边界内
            for i in range(self.dimensions):
                low, high = self.bounds_list[i]
                particle.position[i] = np.clip(particle.position[i], low, high)

    def _evaluate_particles(self):
        """评估所有粒子的适应度"""
        for particle in self.particles:
            # 计算适应度
            particle.value = self.objective_func(particle.position)

            # 更新个体最佳
            if particle.value < particle.best_value:
                particle.best_value = particle.value
                particle.best_position = particle.position.copy()

            # 更新全局最佳
            if particle.value < self.global_best_value:
                self.global_best_value = particle.value
                self.global_best_position = particle.position.copy()


# ============================================================================
# 常用测试函数
# ============================================================================

def sphere(x):
    """
    Sphere函数
    f(x) = Σ x_i^2
    最小值在 (0, 0, ..., 0)，最小值为 0
    """
    return np.sum(x**2)


def rosenbrock(x):
    """
    Rosenbrock函数（香蕉函数）
    f(x) = Σ [100*(x_{i+1} - x_i^2)^2 + (1 - x_i)^2]
    最小值在 (1, 1, ..., 1)，最小值为 0
    """
    return np.sum(100 * (x[1:] - x[:-1]**2)**2 + (1 - x[:-1])**2)


def rastrigin(x):
    """
    Rastrigin函数
    f(x) = A*n + Σ [x_i^2 - A*cos(2π*x_i)]，其中 A=10
    最小值在 (0, 0, ..., 0)，最小值为 0
    """
    A = 10
    return A * len(x) + np.sum(x**2 - A * np.cos(2 * np.pi * x))


def ackley(x):
    """
    Ackley函数
    多局部最小值的复杂函数
    最小值在 (0, 0, ..., 0)，最小值为 0
    """
    a = 20
    b = 0.2
    c = 2 * np.pi
    n = len(x)

    sum1 = np.sum(x**2)
    sum2 = np.sum(np.cos(c * x))

    return (-a * np.exp(-b * np.sqrt(sum1 / n)) -
            np.exp(sum2 / n) + a + np.exp(1))


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("粒子群优化算法（PSO）示例")
    print("=" * 60)

    # 示例1：优化Sphere函数（简单凸函数）
    print("\n1. 优化Sphere函数（2维）")
    print("-" * 40)

    pso = PSO(
        objective_func=sphere,
        dimensions=2,
        n_particles=20,
        max_iter=50,
        bounds=(-5, 5),
        boundary_strategy='reflect',
        verbose=True
    )

    best_pos, best_val, history = pso.optimize()
    print(f"\n结果:")
    print(f"  最佳位置: {best_pos}")
    print(f"  最佳适应度: {best_val:.10f}")
    print(f"  理论最优: [0, 0], 适应度: 0")

    # 示例2：优化Rosenbrock函数（非线性，较难）
    print("\n\n2. 优化Rosenbrock函数（2维）")
    print("-" * 40)

    pso = PSO(
        objective_func=rosenbrock,
        dimensions=2,
        n_particles=30,
        max_iter=100,
        bounds=(-5, 5),
        boundary_strategy='reflect',
        verbose=True
    )

    best_pos, best_val, history = pso.optimize()
    print(f"\n结果:")
    print(f"  最佳位置: {best_pos}")
    print(f"  最佳适应度: {best_val:.10f}")
    print(f"  理论最优: [1, 1], 适应度: 0")

    # 示例3：优化Rastrigin函数（多局部最小值）
    print("\n\n3. 优化Rastrigin函数（3维）")
    print("-" * 40)

    pso = PSO(
        objective_func=rastrigin,
        dimensions=3,
        n_particles=40,
        max_iter=80,
        bounds=(-5.12, 5.12),
        boundary_strategy='reflect',
        verbose=True
    )

    best_pos, best_val, history = pso.optimize()
    print(f"\n结果:")
    print(f"  最佳位置: {best_pos}")
    print(f"  最佳适应度: {best_val:.10f}")
    print(f"  理论最优: [0, 0, 0], 适应度: 0")

    print("\n" + "=" * 60)
    print("所有示例完成！")
    print("=" * 60)
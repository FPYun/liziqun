"""
Baseline multi-objective optimizers for fair MOPSO-DT comparison.

The baselines intentionally reuse the same mixed decision encoding and the same
evaluate_func(Phi) interface as MOPSO-DT. They are compact educational
implementations suitable for thesis experiments, not drop-in replacements for
specialized optimization libraries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import numpy as np

from .metrics import filter_nondominated, update_archive
from .optimization_utils import build_decision_matrix, calculate_crowding_distance, dominates


@dataclass
class Candidate:
    continuous: np.ndarray
    binary: np.ndarray
    objectives: np.ndarray | None = None


class BaseMOOptimizer:
    """Shared mixed-variable optimizer utilities."""

    method_name = "base"

    def __init__(
        self,
        J: int,
        N_bin: int,
        evaluate_func: Callable[[np.ndarray], np.ndarray],
        N_P: int = 50,
        T_max: int = 80,
        archive_size: int = 100,
        seed: int | None = None,
        p_c: float = 0.9,
        p_m: float = 0.01,
    ):
        self.J = J
        self.N_bin = N_bin
        self.evaluate_func = evaluate_func
        self.N_P = N_P
        self.T_max = T_max
        self.archive_size = archive_size
        self.seed = seed
        self.p_c = p_c
        self.p_m = p_m
        self.rng = np.random.default_rng(seed)
        self.evaluations = 0
        self.archive: List[Dict] = []

    @property
    def n_continuous(self) -> int:
        return 2 * self.J

    def _random_candidate(self) -> Candidate:
        return Candidate(
            continuous=self.rng.random(self.n_continuous),
            binary=self.rng.integers(0, 2, size=(self.J, self.N_bin), dtype=int),
        )

    def _evaluate(self, candidate: Candidate) -> Candidate:
        Phi = build_decision_matrix(candidate.continuous, candidate.binary, self.J, self.N_bin)
        candidate.objectives = np.asarray(self.evaluate_func(Phi), dtype=float)
        self.evaluations += 1
        return candidate

    def _entry(self, candidate: Candidate) -> Dict:
        return {
            "continuous": candidate.continuous.copy(),
            "binary": candidate.binary.copy(),
            "objectives": np.asarray(candidate.objectives, dtype=float).copy(),
        }

    def _evaluate_population(self, population: List[Candidate]) -> List[Candidate]:
        return [self._evaluate(candidate) for candidate in population]

    def _update_archive(self, population: List[Candidate]) -> None:
        self.archive = update_archive(self.archive, [self._entry(c) for c in population], self.archive_size)

    def _mutate(self, candidate: Candidate, continuous_sigma: float = 0.10) -> Candidate:
        continuous = candidate.continuous.copy()
        mutation_mask = self.rng.random(self.n_continuous) < self.p_m
        continuous[mutation_mask] += self.rng.normal(0.0, continuous_sigma, size=np.sum(mutation_mask))
        if not np.any(mutation_mask) and self.rng.random() < 0.25:
            idx = self.rng.integers(0, self.n_continuous)
            continuous[idx] += self.rng.normal(0.0, continuous_sigma)
        continuous = np.clip(continuous, 0.0, 1.0)

        binary = candidate.binary.copy()
        bit_mask = self.rng.random(binary.shape) < self.p_m
        binary[bit_mask] = 1 - binary[bit_mask]
        return Candidate(continuous=continuous, binary=binary)

    def _uniform_crossover(self, a: Candidate, b: Candidate) -> Tuple[Candidate, Candidate]:
        if self.rng.random() > self.p_c:
            return Candidate(a.continuous.copy(), a.binary.copy()), Candidate(b.continuous.copy(), b.binary.copy())

        alpha = self.rng.random(self.n_continuous)
        c1 = alpha * a.continuous + (1.0 - alpha) * b.continuous
        c2 = alpha * b.continuous + (1.0 - alpha) * a.continuous
        bit_mask = self.rng.random(a.binary.shape) < 0.5
        b1 = np.where(bit_mask, a.binary, b.binary)
        b2 = np.where(bit_mask, b.binary, a.binary)
        return Candidate(c1, b1), Candidate(c2, b2)

    def _stats(self, elapsed: float) -> Dict:
        return {
            "method": self.method_name,
            "seed": self.seed,
            "evaluations": int(self.evaluations),
            "runtime": float(elapsed),
            "archive_size": len(self.archive),
        }

    def optimize(self) -> Tuple[List[Dict], Dict]:
        raise NotImplementedError


class RandomSearchMO(BaseMOOptimizer):
    """Uniform random mixed-variable search."""

    method_name = "random"

    def optimize(self) -> Tuple[List[Dict], Dict]:
        start = time.time()
        for _ in range(self.T_max):
            population = self._evaluate_population([self._random_candidate() for _ in range(self.N_P)])
            self._update_archive(population)
        return self.archive, self._stats(time.time() - start)


class NSGA2_DT(BaseMOOptimizer):
    """NSGA-II style baseline with nondominated sorting and crowding selection."""

    method_name = "nsga2"

    def _binary_tournament(self, population: List[Candidate]) -> Candidate:
        a, b = self.rng.choice(len(population), size=2, replace=False)
        ca, cb = population[a], population[b]
        if dominates(ca.objectives, cb.objectives):
            return ca
        if dominates(cb.objectives, ca.objectives):
            return cb
        return ca if self.rng.random() < 0.5 else cb

    def _make_offspring(self, population: List[Candidate], n_children: int) -> List[Candidate]:
        children = []
        while len(children) < n_children:
            p1 = self._binary_tournament(population)
            p2 = self._binary_tournament(population)
            c1, c2 = self._uniform_crossover(p1, p2)
            children.append(self._mutate(c1))
            if len(children) < n_children:
                children.append(self._mutate(c2))
        return children

    def _select_population(self, population: List[Candidate]) -> List[Candidate]:
        objectives = np.array([c.objectives for c in population])
        remaining = set(range(len(population)))
        selected: List[Candidate] = []

        while remaining and len(selected) < self.N_P:
            current = sorted(remaining)
            sub_obj = objectives[current]
            front_local = filter_nondominated(sub_obj)
            front_indices = [current[i] for i in front_local]

            if len(selected) + len(front_indices) <= self.N_P:
                selected.extend(population[i] for i in front_indices)
            else:
                front_obj = objectives[front_indices]
                distances = calculate_crowding_distance(front_obj)
                finite = distances[np.isfinite(distances)]
                finite_max = float(np.max(finite)) if len(finite) else 1.0
                distances = np.where(np.isfinite(distances), distances, finite_max * 10.0)
                order = np.argsort(distances)[::-1]
                need = self.N_P - len(selected)
                selected.extend(population[front_indices[i]] for i in order[:need])
            remaining.difference_update(front_indices)
        return selected

    def optimize(self) -> Tuple[List[Dict], Dict]:
        start = time.time()
        population = self._evaluate_population([self._random_candidate() for _ in range(self.N_P)])
        self._update_archive(population)

        for _ in range(max(0, self.T_max - 1)):
            offspring = self._evaluate_population(self._make_offspring(population, self.N_P))
            self._update_archive(offspring)
            population = self._select_population(population + offspring)

        return self.archive, self._stats(time.time() - start)


class MOEAD_DT(BaseMOOptimizer):
    """MOEA/D style baseline using Tchebycheff scalar subproblems."""

    method_name = "moead"

    def _weights(self) -> np.ndarray:
        if self.N_P == 1:
            return np.array([[0.5, 0.5]])
        grid = np.linspace(0.0, 1.0, self.N_P)
        return np.column_stack([grid, 1.0 - grid])

    def _scalar_value(self, objectives: np.ndarray, weight: np.ndarray, ideal: np.ndarray) -> float:
        safe_weight = np.maximum(weight, 1e-3)
        return float(np.max(safe_weight * np.abs(objectives - ideal)))

    def optimize(self) -> Tuple[List[Dict], Dict]:
        start = time.time()
        weights = self._weights()
        population = self._evaluate_population([self._random_candidate() for _ in range(self.N_P)])
        ideal = np.min(np.array([c.objectives for c in population]), axis=0)
        self._update_archive(population)

        for _ in range(max(0, self.T_max - 1)):
            new_population = list(population)
            for i in range(self.N_P):
                p_idx = self.rng.choice(self.N_P, size=2, replace=False)
                child_a, _ = self._uniform_crossover(population[p_idx[0]], population[p_idx[1]])
                child = self._evaluate(self._mutate(child_a))
                ideal = np.minimum(ideal, child.objectives)

                current_value = self._scalar_value(population[i].objectives, weights[i], ideal)
                child_value = self._scalar_value(child.objectives, weights[i], ideal)
                if child_value <= current_value:
                    new_population[i] = child
            population = new_population
            self._update_archive(population)

        return self.archive, self._stats(time.time() - start)


class SPEA2_DT(BaseMOOptimizer):
    """SPEA2 style baseline with strength fitness and density truncation."""

    method_name = "spea2"

    def _fitness(self, population: List[Candidate]) -> np.ndarray:
        objectives = np.array([c.objectives for c in population])
        n = len(population)
        strength = np.zeros(n)
        raw = np.zeros(n)
        for i in range(n):
            for j in range(n):
                if i != j and dominates(objectives[i], objectives[j]):
                    strength[i] += 1
        for i in range(n):
            for j in range(n):
                if i != j and dominates(objectives[j], objectives[i]):
                    raw[i] += strength[j]

        distances = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                distances[i, j] = np.linalg.norm(objectives[i] - objectives[j])
        distances.sort(axis=1)
        k = max(1, int(np.sqrt(n)))
        density = 1.0 / (distances[:, min(k, n - 1)] + 2.0)
        return raw + density

    def _select_population(self, population: List[Candidate]) -> List[Candidate]:
        fitness = self._fitness(population)
        elite = [population[i] for i in np.where(fitness < 1.0)[0]]
        if len(elite) >= self.N_P:
            objectives = np.array([c.objectives for c in elite])
            distances = calculate_crowding_distance(objectives)
            finite = distances[np.isfinite(distances)]
            finite_max = float(np.max(finite)) if len(finite) else 1.0
            distances = np.where(np.isfinite(distances), distances, finite_max * 10.0)
            order = np.argsort(distances)[::-1]
            return [elite[i] for i in order[: self.N_P]]

        order = np.argsort(fitness)
        selected = list(elite)
        selected_ids = {id(candidate) for candidate in selected}
        for idx in order:
            if len(selected) >= self.N_P:
                break
            if id(population[idx]) not in selected_ids:
                selected.append(population[idx])
                selected_ids.add(id(population[idx]))
        return selected

    def _tournament_by_fitness(self, population: List[Candidate], fitness: np.ndarray) -> Candidate:
        a, b = self.rng.choice(len(population), size=2, replace=False)
        return population[a] if fitness[a] <= fitness[b] else population[b]

    def optimize(self) -> Tuple[List[Dict], Dict]:
        start = time.time()
        population = self._evaluate_population([self._random_candidate() for _ in range(self.N_P)])
        self._update_archive(population)

        for _ in range(max(0, self.T_max - 1)):
            fitness = self._fitness(population)
            mating_pool = []
            while len(mating_pool) < self.N_P:
                mating_pool.append(self._tournament_by_fitness(population, fitness))

            offspring = []
            for i in range(0, self.N_P, 2):
                p1 = mating_pool[i]
                p2 = mating_pool[(i + 1) % self.N_P]
                c1, c2 = self._uniform_crossover(p1, p2)
                offspring.append(self._mutate(c1))
                if len(offspring) < self.N_P:
                    offspring.append(self._mutate(c2))
            offspring = self._evaluate_population(offspring[: self.N_P])
            self._update_archive(offspring)
            population = self._select_population(population + offspring)

        return self.archive, self._stats(time.time() - start)

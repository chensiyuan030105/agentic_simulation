from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    from scipy.spatial import cKDTree
except Exception:  # noqa: BLE001
    cKDTree = None


@dataclass(frozen=True)
class SphWorldConfig:
    bounds: tuple[float, float, float]
    frames: int
    fps: int
    dt: float
    substeps_per_frame: int


@dataclass(frozen=True)
class SphFluidConfig:
    particle_spacing: float
    initial_block_min: tuple[float, float, float]
    initial_block_max: tuple[float, float, float]


@dataclass(frozen=True)
class SphSolverConfig:
    rest_density: float
    smoothing_length: float
    gas_constant: float
    viscosity: float
    gravity: tuple[float, float, float]
    boundary_damping: float
    max_velocity: float


@dataclass(frozen=True)
class SphSceneConfig:
    run_name: str
    seed: int
    world: SphWorldConfig
    fluid: SphFluidConfig
    solver: SphSolverConfig


@dataclass(frozen=True)
class SphSimulationResult:
    positions: np.ndarray
    velocities: np.ndarray
    densities: np.ndarray
    pressures: np.ndarray
    events: list[dict]


def parse_sph_scene_config(data: dict[str, Any]) -> SphSceneConfig:
    run_name = str(data.get("run_name", "sph_dambreak_001"))
    seed = int(data.get("seed", 0))

    world_data = _require_mapping(data, "world")
    world = SphWorldConfig(
        bounds=_require_vec3(world_data, "bounds"),
        frames=int(world_data.get("frames", 120)),
        fps=int(world_data.get("fps", 24)),
        dt=float(world_data.get("dt", 0.0015)),
        substeps_per_frame=int(world_data.get("substeps_per_frame", 4)),
    )
    if min(world.bounds) <= 0.0 or world.frames <= 1 or world.fps <= 0 or world.dt <= 0.0:
        raise ValueError("world bounds, frames, fps, and dt must be positive")
    if world.substeps_per_frame <= 0:
        raise ValueError("world.substeps_per_frame must be positive")

    fluid_data = _require_mapping(data, "fluid")
    fluid = SphFluidConfig(
        particle_spacing=float(fluid_data.get("particle_spacing", 0.055)),
        initial_block_min=_require_vec3(fluid_data, "initial_block_min"),
        initial_block_max=_require_vec3(fluid_data, "initial_block_max"),
    )
    if fluid.particle_spacing <= 0.0:
        raise ValueError("fluid.particle_spacing must be positive")

    solver_data = _require_mapping(data, "solver")
    solver = SphSolverConfig(
        rest_density=float(solver_data.get("rest_density", 1000.0)),
        smoothing_length=float(solver_data.get("smoothing_length", 0.075)),
        gas_constant=float(solver_data.get("gas_constant", 55.0)),
        viscosity=float(solver_data.get("viscosity", 0.035)),
        gravity=_require_vec3(solver_data, "gravity"),
        boundary_damping=float(solver_data.get("boundary_damping", 0.45)),
        max_velocity=float(solver_data.get("max_velocity", 3.0)),
    )
    if solver.rest_density <= 0.0 or solver.smoothing_length <= 0.0:
        raise ValueError("solver.rest_density and smoothing_length must be positive")

    return SphSceneConfig(run_name=run_name, seed=seed, world=world, fluid=fluid, solver=solver)


def run_sph_simulation(scene: SphSceneConfig) -> SphSimulationResult:
    rng = np.random.default_rng(scene.seed)
    positions = initialize_dambreak_particles(scene)
    positions += rng.uniform(-0.003, 0.003, size=positions.shape)
    positions = np.clip(positions, 0.5 * scene.fluid.particle_spacing, np.asarray(scene.world.bounds) - 0.5 * scene.fluid.particle_spacing)
    velocities = np.zeros_like(positions)

    particle_count = positions.shape[0]
    frames = scene.world.frames
    out_positions = np.zeros((frames, particle_count, 3), dtype=np.float32)
    out_velocities = np.zeros_like(out_positions)
    out_densities = np.zeros((frames, particle_count), dtype=np.float32)
    out_pressures = np.zeros_like(out_densities)

    mass = scene.solver.rest_density * scene.fluid.particle_spacing**3
    radius = 0.45 * scene.fluid.particle_spacing
    gravity = np.asarray(scene.solver.gravity, dtype=np.float64)
    bounds = np.asarray(scene.world.bounds, dtype=np.float64)

    for frame in range(frames):
        densities, pressures, neighbors = compute_density_pressure(positions, scene, mass)
        out_positions[frame] = positions.astype(np.float32)
        out_velocities[frame] = velocities.astype(np.float32)
        out_densities[frame] = densities.astype(np.float32)
        out_pressures[frame] = pressures.astype(np.float32)

        if frame == frames - 1:
            break
        for _ in range(scene.world.substeps_per_frame):
            densities, pressures, neighbors = compute_density_pressure(positions, scene, mass)
            accelerations = compute_accelerations(positions, velocities, densities, pressures, neighbors, scene, mass)
            accelerations += gravity[None, :]
            velocities += scene.world.dt * accelerations
            speeds = np.linalg.norm(velocities, axis=1)
            too_fast = speeds > scene.solver.max_velocity
            if np.any(too_fast):
                velocities[too_fast] *= (scene.solver.max_velocity / speeds[too_fast])[:, None]
            positions += scene.world.dt * velocities
            apply_box_boundary(positions, velocities, bounds=bounds, radius=radius, damping=scene.solver.boundary_damping)

    return SphSimulationResult(
        positions=out_positions,
        velocities=out_velocities,
        densities=out_densities,
        pressures=out_pressures,
        events=[{"frame": 0, "type": "dambreak_initialized", "particle_count": int(particle_count)}],
    )


def initialize_dambreak_particles(scene: SphSceneConfig) -> np.ndarray:
    spacing = scene.fluid.particle_spacing
    mins = np.asarray(scene.fluid.initial_block_min, dtype=np.float64)
    maxs = np.asarray(scene.fluid.initial_block_max, dtype=np.float64)
    axes = [np.arange(mins[axis], maxs[axis] + 0.5 * spacing, spacing, dtype=np.float64) for axis in range(3)]
    grid = np.meshgrid(*axes, indexing="ij")
    return np.column_stack([component.reshape(-1) for component in grid])


def compute_density_pressure(
    positions: np.ndarray,
    scene: SphSceneConfig,
    mass: float,
) -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
    if cKDTree is not None:
        return compute_density_pressure_pairs(positions, scene, mass)
    neighbors = build_neighbor_lists(positions, scene.solver.smoothing_length)
    h = scene.solver.smoothing_length
    densities = np.zeros(positions.shape[0], dtype=np.float64)
    for i, item_neighbors in enumerate(neighbors):
        for j in item_neighbors:
            r2 = float(np.sum((positions[i] - positions[j]) ** 2))
            densities[i] += mass * poly6_kernel(r2, h)
    densities = np.maximum(densities, 0.35 * scene.solver.rest_density)
    pressures = scene.solver.gas_constant * np.maximum(densities - scene.solver.rest_density, 0.0)
    return densities, pressures, neighbors


def compute_density_pressure_pairs(
    positions: np.ndarray,
    scene: SphSceneConfig,
    mass: float,
) -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
    h = scene.solver.smoothing_length
    tree = cKDTree(positions)
    pairs = np.asarray(list(tree.query_pairs(h)), dtype=np.int64)
    densities = np.full(positions.shape[0], mass * poly6_kernel(0.0, h), dtype=np.float64)
    if pairs.size:
        diffs = positions[pairs[:, 0]] - positions[pairs[:, 1]]
        r2 = np.sum(diffs * diffs, axis=1)
        values = mass * poly6_kernel_array(r2, h)
        np.add.at(densities, pairs[:, 0], values)
        np.add.at(densities, pairs[:, 1], values)
    densities = np.maximum(densities, 0.35 * scene.solver.rest_density)
    pressures = scene.solver.gas_constant * np.maximum(densities - scene.solver.rest_density, 0.0)
    return densities, pressures, [pairs]


def compute_accelerations(
    positions: np.ndarray,
    velocities: np.ndarray,
    densities: np.ndarray,
    pressures: np.ndarray,
    neighbors: list[list[int]],
    scene: SphSceneConfig,
    mass: float,
) -> np.ndarray:
    if neighbors and isinstance(neighbors[0], np.ndarray):
        return compute_accelerations_pairs(positions, velocities, densities, pressures, neighbors[0], scene, mass)
    h = scene.solver.smoothing_length
    acc = np.zeros_like(positions)
    for i, item_neighbors in enumerate(neighbors):
        pressure_force = np.zeros(3, dtype=np.float64)
        viscosity_force = np.zeros(3, dtype=np.float64)
        for j in item_neighbors:
            if i == j:
                continue
            rij = positions[i] - positions[j]
            r = float(np.linalg.norm(rij))
            if r <= 1.0e-12 or r >= h:
                continue
            grad = spiky_gradient(rij, r, h)
            pressure_force += -mass * (pressures[i] + pressures[j]) / (2.0 * densities[j]) * grad
            viscosity_force += (
                scene.solver.viscosity
                * mass
                * (velocities[j] - velocities[i])
                / densities[j]
                * viscosity_laplacian(r, h)
            )
        acc[i] = (pressure_force + viscosity_force) / densities[i]
    return acc


def compute_accelerations_pairs(
    positions: np.ndarray,
    velocities: np.ndarray,
    densities: np.ndarray,
    pressures: np.ndarray,
    pairs: np.ndarray,
    scene: SphSceneConfig,
    mass: float,
) -> np.ndarray:
    acc = np.zeros_like(positions)
    if pairs.size == 0:
        return acc

    h = scene.solver.smoothing_length
    i = pairs[:, 0]
    j = pairs[:, 1]
    rij = positions[i] - positions[j]
    r = np.linalg.norm(rij, axis=1)
    valid = (r > 1.0e-12) & (r < h)
    if not np.any(valid):
        return acc

    i = i[valid]
    j = j[valid]
    rij = rij[valid]
    r = r[valid]

    grad = spiky_gradient_array(rij, r, h)
    pressure_scale_i = -mass * (pressures[i] + pressures[j]) / (2.0 * densities[j])
    pressure_scale_j = -mass * (pressures[j] + pressures[i]) / (2.0 * densities[i])
    pressure_i = pressure_scale_i[:, None] * grad
    pressure_j = pressure_scale_j[:, None] * -grad

    lap = viscosity_laplacian_array(r, h)
    viscosity_i = scene.solver.viscosity * mass * (velocities[j] - velocities[i]) / densities[j, None] * lap[:, None]
    viscosity_j = scene.solver.viscosity * mass * (velocities[i] - velocities[j]) / densities[i, None] * lap[:, None]

    np.add.at(acc, i, (pressure_i + viscosity_i) / densities[i, None])
    np.add.at(acc, j, (pressure_j + viscosity_j) / densities[j, None])
    return acc


def build_neighbor_lists(positions: np.ndarray, h: float) -> list[list[int]]:
    cell_ids = np.floor(positions / h).astype(np.int64)
    grid: dict[tuple[int, int, int], list[int]] = {}
    for idx, cell in enumerate(cell_ids):
        grid.setdefault(tuple(int(v) for v in cell), []).append(idx)

    neighbors: list[list[int]] = []
    h2 = h * h
    offsets = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)]
    for idx, cell in enumerate(cell_ids):
        item: list[int] = []
        base = tuple(int(v) for v in cell)
        for offset in offsets:
            bucket = grid.get((base[0] + offset[0], base[1] + offset[1], base[2] + offset[2]), [])
            for candidate in bucket:
                if float(np.sum((positions[idx] - positions[candidate]) ** 2)) < h2:
                    item.append(candidate)
        neighbors.append(item)
    return neighbors


def apply_box_boundary(
    positions: np.ndarray,
    velocities: np.ndarray,
    bounds: np.ndarray,
    radius: float,
    damping: float,
) -> None:
    low = radius
    high = bounds - radius
    for axis in range(3):
        below = positions[:, axis] < low
        if np.any(below):
            positions[below, axis] = low
            velocities[below, axis] = np.maximum(0.0, -velocities[below, axis] * damping)
        above = positions[:, axis] > high[axis]
        if np.any(above):
            positions[above, axis] = high[axis]
            velocities[above, axis] = np.minimum(0.0, -velocities[above, axis] * damping)


def poly6_kernel(r2: float, h: float) -> float:
    if r2 >= h * h:
        return 0.0
    return 315.0 / (64.0 * np.pi * h**9) * (h * h - r2) ** 3


def poly6_kernel_array(r2: np.ndarray, h: float) -> np.ndarray:
    values = np.zeros_like(r2, dtype=np.float64)
    mask = r2 < h * h
    values[mask] = 315.0 / (64.0 * np.pi * h**9) * (h * h - r2[mask]) ** 3
    return values


def spiky_gradient(rij: np.ndarray, r: float, h: float) -> np.ndarray:
    return -45.0 / (np.pi * h**6) * (h - r) ** 2 * rij / r


def spiky_gradient_array(rij: np.ndarray, r: np.ndarray, h: float) -> np.ndarray:
    scale = -45.0 / (np.pi * h**6) * (h - r) ** 2 / r
    return scale[:, None] * rij


def viscosity_laplacian(r: float, h: float) -> float:
    if r >= h:
        return 0.0
    return 45.0 / (np.pi * h**6) * (h - r)


def viscosity_laplacian_array(r: np.ndarray, h: float) -> np.ndarray:
    values = np.zeros_like(r, dtype=np.float64)
    mask = r < h
    values[mask] = 45.0 / (np.pi * h**6) * (h - r[mask])
    return values


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"'{key}' must be a mapping")
    return value


def _require_vec3(data: dict[str, Any], key: str) -> tuple[float, float, float]:
    value = data.get(key)
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"'{key}' must be a length-3 list")
    return float(value[0]), float(value[1]), float(value[2])

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import require_number_pair


@dataclass(frozen=True)
class FluidWorldConfig:
    grid: tuple[int, int]
    extent: tuple[float, float]
    frames: int
    fps: int
    dt: float


@dataclass(frozen=True)
class FluidSolverConfig:
    wave_speed: float
    damping: float
    height_clip: float


@dataclass(frozen=True)
class FluidDisturbanceConfig:
    id: str
    type: str
    center: tuple[float, float]
    amplitude: float
    sigma: float


@dataclass(frozen=True)
class FluidObstacleConfig:
    id: str
    type: str
    center: tuple[float, float]
    radius: float


@dataclass(frozen=True)
class FluidSceneConfig:
    run_name: str
    seed: int
    world: FluidWorldConfig
    solver: FluidSolverConfig
    initial_disturbances: tuple[FluidDisturbanceConfig, ...]
    obstacles: tuple[FluidObstacleConfig, ...]


@dataclass(frozen=True)
class FluidSimulationResult:
    height: np.ndarray
    velocity: np.ndarray
    mask: np.ndarray
    events: list[dict]


def parse_fluid_scene_config(data: dict[str, Any]) -> FluidSceneConfig:
    run_name = str(data.get("run_name", "fluid_001"))
    seed = int(data.get("seed", 0))

    world_data = data.get("world")
    if not isinstance(world_data, dict):
        raise ValueError("'world' must be a mapping")
    grid_value = world_data.get("grid", [96, 96])
    if not isinstance(grid_value, (list, tuple)) or len(grid_value) != 2:
        raise ValueError("world.grid must be a length-2 list")
    world = FluidWorldConfig(
        grid=(int(grid_value[0]), int(grid_value[1])),
        extent=require_number_pair(world_data, "extent"),
        frames=int(world_data.get("frames", 180)),
        fps=int(world_data.get("fps", 24)),
        dt=float(world_data.get("dt", 0.035)),
    )
    if min(world.grid) < 8:
        raise ValueError("world.grid entries must be at least 8")
    if world.frames <= 2 or world.fps <= 0 or world.dt <= 0.0:
        raise ValueError("world.frames, world.fps, and world.dt must be positive")

    solver_data = data.get("solver", {})
    if not isinstance(solver_data, dict):
        raise ValueError("'solver' must be a mapping")
    solver = FluidSolverConfig(
        wave_speed=float(solver_data.get("wave_speed", 2.4)),
        damping=float(solver_data.get("damping", 0.01)),
        height_clip=float(solver_data.get("height_clip", 0.6)),
    )

    disturbance_items = data.get("initial_disturbances", [])
    if not isinstance(disturbance_items, list):
        raise ValueError("'initial_disturbances' must be a list")
    disturbances = tuple(_parse_disturbance(item, idx) for idx, item in enumerate(disturbance_items))

    obstacle_items = data.get("obstacles", [])
    if not isinstance(obstacle_items, list):
        raise ValueError("'obstacles' must be a list")
    obstacles = tuple(_parse_obstacle(item, idx) for idx, item in enumerate(obstacle_items))

    return FluidSceneConfig(
        run_name=run_name,
        seed=seed,
        world=world,
        solver=solver,
        initial_disturbances=disturbances,
        obstacles=obstacles,
    )


def run_fluid_simulation(scene: FluidSceneConfig) -> FluidSimulationResult:
    rows, cols = scene.world.grid
    frames = int(scene.world.frames)
    xx, yy = make_grid(scene)
    mask = make_solid_mask(scene, xx, yy)
    height = np.zeros((frames, rows, cols), dtype=np.float64)
    velocity = np.zeros_like(height)

    height[0] = initial_height(scene, xx, yy)
    height[0][mask] = 0.0
    free = ~mask
    initial_mass = float(height[0][free].sum())
    velocity[0] = 0.0
    height[1] = height[0].copy()

    dx = float(scene.world.extent[0]) / float(cols - 1)
    dy = float(scene.world.extent[1]) / float(rows - 1)
    c2dt2 = float(scene.solver.wave_speed) ** 2 * float(scene.world.dt) ** 2
    damping = float(scene.solver.damping)
    clip = abs(float(scene.solver.height_clip))

    for frame in range(1, frames - 1):
        lap = laplacian(height[frame], dx=dx, dy=dy, mask=mask)
        next_height = (2.0 - damping) * height[frame] - (1.0 - damping) * height[frame - 1] + c2dt2 * lap
        next_height[mask] = 0.0
        next_height = np.clip(next_height, -clip, clip)
        mass_error = float(next_height[free].sum()) - initial_mass
        next_height[free] -= mass_error / float(np.sum(free))
        height[frame + 1] = next_height
        velocity[frame] = (height[frame + 1] - height[frame - 1]) / (2.0 * float(scene.world.dt))
    velocity[-1] = (height[-1] - height[-2]) / float(scene.world.dt)

    return FluidSimulationResult(
        height=height.astype(np.float32),
        velocity=velocity.astype(np.float32),
        mask=mask.astype(bool),
        events=[{"frame": 0, "type": "initial_disturbance", "count": len(scene.initial_disturbances)}],
    )


def make_grid(scene: FluidSceneConfig) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = scene.world.grid
    width, height = scene.world.extent
    x = np.linspace(-0.5 * width, 0.5 * width, cols, dtype=np.float64)
    y = np.linspace(-0.5 * height, 0.5 * height, rows, dtype=np.float64)
    return np.meshgrid(x, y)


def initial_height(scene: FluidSceneConfig, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
    out = np.zeros_like(xx, dtype=np.float64)
    for disturbance in scene.initial_disturbances:
        if disturbance.type != "gaussian":
            raise ValueError(f"Unsupported disturbance type: {disturbance.type}")
        cx, cy = disturbance.center
        sigma2 = max(1.0e-8, float(disturbance.sigma) ** 2)
        rr2 = (xx - float(cx)) ** 2 + (yy - float(cy)) ** 2
        out += float(disturbance.amplitude) * np.exp(-0.5 * rr2 / sigma2)
    return out


def make_solid_mask(scene: FluidSceneConfig, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
    mask = np.zeros_like(xx, dtype=bool)
    for obstacle in scene.obstacles:
        if obstacle.type != "circle":
            raise ValueError(f"Unsupported obstacle type: {obstacle.type}")
        cx, cy = obstacle.center
        mask |= (xx - float(cx)) ** 2 + (yy - float(cy)) ** 2 <= float(obstacle.radius) ** 2
    return mask


def laplacian(field: np.ndarray, dx: float, dy: float, mask: np.ndarray) -> np.ndarray:
    padded = np.pad(field, pad_width=1, mode="edge")
    lap = (
        (padded[1:-1, 2:] - 2.0 * field + padded[1:-1, :-2]) / (dx * dx)
        + (padded[2:, 1:-1] - 2.0 * field + padded[:-2, 1:-1]) / (dy * dy)
    )
    lap[mask] = 0.0
    return lap


def _parse_disturbance(item: Any, index: int) -> FluidDisturbanceConfig:
    if not isinstance(item, dict):
        raise ValueError(f"disturbance #{index} must be a mapping")
    return FluidDisturbanceConfig(
        id=str(item.get("id", f"disturbance_{index}")),
        type=str(item.get("type", "gaussian")),
        center=require_number_pair(item, "center"),
        amplitude=float(item.get("amplitude", 0.2)),
        sigma=float(item.get("sigma", 0.5)),
    )


def _parse_obstacle(item: Any, index: int) -> FluidObstacleConfig:
    if not isinstance(item, dict):
        raise ValueError(f"obstacle #{index} must be a mapping")
    return FluidObstacleConfig(
        id=str(item.get("id", f"obstacle_{index}")),
        type=str(item.get("type", "circle")),
        center=require_number_pair(item, "center"),
        radius=float(item.get("radius", 0.5)),
    )

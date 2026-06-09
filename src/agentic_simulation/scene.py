from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import require_color, require_number_pair


@dataclass(frozen=True)
class WorldConfig:
    size: tuple[float, float]
    frames: int
    fps: int
    dt: float
    boundary_margin: float


@dataclass(frozen=True)
class PolicyConfig:
    goal_tolerance: float
    obstacle_influence: float
    obstacle_strength: float
    separation_radius: float
    separation_strength: float
    damping: float


@dataclass(frozen=True)
class AgentConfig:
    id: str
    start: tuple[float, float]
    goal: tuple[float, float]
    radius: float
    speed: float
    color: tuple[float, float, float]


@dataclass(frozen=True)
class ObstacleConfig:
    id: str
    type: str
    center: tuple[float, float]
    radius: float


@dataclass(frozen=True)
class SceneConfig:
    run_name: str
    seed: int
    world: WorldConfig
    policy: PolicyConfig
    agents: tuple[AgentConfig, ...]
    obstacles: tuple[ObstacleConfig, ...]


def parse_scene_config(data: dict[str, Any]) -> SceneConfig:
    run_name = str(data.get("run_name", "demo_001"))
    seed = int(data.get("seed", 0))

    world_data = data.get("world")
    if not isinstance(world_data, dict):
        raise ValueError("'world' must be a mapping")
    world = WorldConfig(
        size=require_number_pair(world_data, "size"),
        frames=int(world_data.get("frames", 240)),
        fps=int(world_data.get("fps", 24)),
        dt=float(world_data.get("dt", 1.0 / 24.0)),
        boundary_margin=float(world_data.get("boundary_margin", 0.5)),
    )
    if world.frames <= 1:
        raise ValueError("world.frames must be greater than 1")
    if world.fps <= 0 or world.dt <= 0:
        raise ValueError("world.fps and world.dt must be positive")

    policy_data = data.get("policy", {})
    if not isinstance(policy_data, dict):
        raise ValueError("'policy' must be a mapping")
    policy = PolicyConfig(
        goal_tolerance=float(policy_data.get("goal_tolerance", 0.35)),
        obstacle_influence=float(policy_data.get("obstacle_influence", 2.0)),
        obstacle_strength=float(policy_data.get("obstacle_strength", 2.0)),
        separation_radius=float(policy_data.get("separation_radius", 1.0)),
        separation_strength=float(policy_data.get("separation_strength", 1.0)),
        damping=float(policy_data.get("damping", 0.1)),
    )

    agent_items = data.get("agents")
    if not isinstance(agent_items, list) or not agent_items:
        raise ValueError("'agents' must be a non-empty list")
    agents = tuple(_parse_agent(item, index) for index, item in enumerate(agent_items))

    obstacle_items = data.get("obstacles", [])
    if not isinstance(obstacle_items, list):
        raise ValueError("'obstacles' must be a list")
    obstacles = tuple(_parse_obstacle(item, index) for index, item in enumerate(obstacle_items))

    return SceneConfig(
        run_name=run_name,
        seed=seed,
        world=world,
        policy=policy,
        agents=agents,
        obstacles=obstacles,
    )


def _parse_agent(item: Any, index: int) -> AgentConfig:
    if not isinstance(item, dict):
        raise ValueError(f"agent #{index} must be a mapping")
    return AgentConfig(
        id=str(item.get("id", f"agent_{index}")),
        start=require_number_pair(item, "start"),
        goal=require_number_pair(item, "goal"),
        radius=float(item.get("radius", 0.3)),
        speed=float(item.get("speed", 1.0)),
        color=require_color(item, "color"),
    )


def _parse_obstacle(item: Any, index: int) -> ObstacleConfig:
    if not isinstance(item, dict):
        raise ValueError(f"obstacle #{index} must be a mapping")
    obstacle_type = str(item.get("type", "circle"))
    if obstacle_type != "circle":
        raise ValueError(f"Unsupported obstacle type: {obstacle_type}")
    return ObstacleConfig(
        id=str(item.get("id", f"obstacle_{index}")),
        type=obstacle_type,
        center=require_number_pair(item, "center"),
        radius=float(item.get("radius", 1.0)),
    )

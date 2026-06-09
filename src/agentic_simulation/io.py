from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from .metrics import compute_metrics
from .scene import AgentConfig, ObstacleConfig, SceneConfig
from .simulation import SimulationResult


def write_run_outputs(
    output_dir: str | Path,
    scene: SceneConfig,
    result: SimulationResult,
    config_path: str | Path,
) -> dict[str, Path]:
    """Write a complete simulation run bundle."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scene_path = output_dir / "scene.json"
    traj_path = output_dir / "trajectories.npz"
    events_path = output_dir / "events.jsonl"
    metrics_path = output_dir / "metrics.json"
    manifest_path = output_dir / "manifest.json"

    _write_json(scene_path, scene_to_payload(scene))
    np.savez_compressed(
        traj_path,
        positions=result.positions.astype(np.float32),
        orientations=result.orientations.astype(np.float32),
        velocities=result.velocities.astype(np.float32),
        actions=result.actions.astype(np.float32),
    )
    _write_events(events_path, result.events)

    metrics = compute_metrics(scene=scene, result=result)
    _write_json(metrics_path, metrics)

    manifest = {
        "run_name": scene.run_name,
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "config_path": str(Path(config_path).resolve()),
        "seed": int(scene.seed),
        "frames": int(scene.world.frames),
        "fps": int(scene.world.fps),
        "git_commit": _git_commit(),
        "outputs": {
            "scene": scene_path.name,
            "trajectories": traj_path.name,
            "events": events_path.name,
            "metrics": metrics_path.name,
        },
    }
    _write_json(manifest_path, manifest)

    return {
        "scene": scene_path,
        "trajectories": traj_path,
        "events": events_path,
        "metrics": metrics_path,
        "manifest": manifest_path,
    }


def scene_to_payload(scene: SceneConfig) -> dict:
    return {
        "run_name": scene.run_name,
        "seed": int(scene.seed),
        "world": {
            "size": list(scene.world.size),
            "frames": int(scene.world.frames),
            "fps": int(scene.world.fps),
            "dt": float(scene.world.dt),
            "boundary_margin": float(scene.world.boundary_margin),
        },
        "policy": {
            "goal_tolerance": float(scene.policy.goal_tolerance),
            "obstacle_influence": float(scene.policy.obstacle_influence),
            "obstacle_strength": float(scene.policy.obstacle_strength),
            "separation_radius": float(scene.policy.separation_radius),
            "separation_strength": float(scene.policy.separation_strength),
            "damping": float(scene.policy.damping),
        },
        "agents": [_agent_payload(agent) for agent in scene.agents],
        "obstacles": [_obstacle_payload(obstacle) for obstacle in scene.obstacles],
    }


def _agent_payload(agent: AgentConfig) -> dict:
    return {
        "id": agent.id,
        "type": "sphere_agent",
        "start": list(agent.start),
        "goal": list(agent.goal),
        "radius": float(agent.radius),
        "speed": float(agent.speed),
        "color": list(agent.color),
    }


def _obstacle_payload(obstacle: ObstacleConfig) -> dict:
    return {
        "id": obstacle.id,
        "type": obstacle.type,
        "center": list(obstacle.center),
        "radius": float(obstacle.radius),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_events(path: Path, events: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:  # noqa: BLE001
        return None
    return result.stdout.strip() or None

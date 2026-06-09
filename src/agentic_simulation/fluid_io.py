from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from .fluid import FluidObstacleConfig, FluidSceneConfig, FluidSimulationResult
from .fluid_metrics import compute_fluid_metrics


def write_fluid_run_outputs(
    output_dir: str | Path,
    scene: FluidSceneConfig,
    result: FluidSimulationResult,
    config_path: str | Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scene_path = output_dir / "fluid_scene.json"
    fields_path = output_dir / "fields.npz"
    events_path = output_dir / "events.jsonl"
    metrics_path = output_dir / "metrics.json"
    manifest_path = output_dir / "manifest.json"

    _write_json(scene_path, fluid_scene_to_payload(scene))
    np.savez_compressed(
        fields_path,
        height=result.height.astype(np.float32),
        velocity=result.velocity.astype(np.float32),
        mask=result.mask.astype(bool),
    )
    _write_events(events_path, result.events)
    _write_json(metrics_path, compute_fluid_metrics(scene, result))
    _write_json(
        manifest_path,
        {
            "run_name": scene.run_name,
            "kind": "fluid_height_field",
            "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "config_path": str(Path(config_path).resolve()),
            "seed": int(scene.seed),
            "frames": int(scene.world.frames),
            "fps": int(scene.world.fps),
            "git_commit": _git_commit(),
            "outputs": {
                "scene": scene_path.name,
                "fields": fields_path.name,
                "events": events_path.name,
                "metrics": metrics_path.name,
            },
        },
    )
    return {
        "scene": scene_path,
        "fields": fields_path,
        "events": events_path,
        "metrics": metrics_path,
        "manifest": manifest_path,
    }


def fluid_scene_to_payload(scene: FluidSceneConfig) -> dict:
    return {
        "run_name": scene.run_name,
        "seed": int(scene.seed),
        "world": {
            "grid": list(scene.world.grid),
            "extent": list(scene.world.extent),
            "frames": int(scene.world.frames),
            "fps": int(scene.world.fps),
            "dt": float(scene.world.dt),
        },
        "solver": {
            "wave_speed": float(scene.solver.wave_speed),
            "damping": float(scene.solver.damping),
            "height_clip": float(scene.solver.height_clip),
        },
        "initial_disturbances": [
            {
                "id": d.id,
                "type": d.type,
                "center": list(d.center),
                "amplitude": float(d.amplitude),
                "sigma": float(d.sigma),
            }
            for d in scene.initial_disturbances
        ],
        "obstacles": [_obstacle_payload(obstacle) for obstacle in scene.obstacles],
    }


def _obstacle_payload(obstacle: FluidObstacleConfig) -> dict:
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

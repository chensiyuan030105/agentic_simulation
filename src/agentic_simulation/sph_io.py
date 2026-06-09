from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from .sph import SphSceneConfig, SphSimulationResult
from .sph_metrics import compute_sph_metrics


def write_sph_run_outputs(
    output_dir: str | Path,
    scene: SphSceneConfig,
    result: SphSimulationResult,
    config_path: str | Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scene_path = output_dir / "sph_scene.json"
    particles_path = output_dir / "particles.npz"
    events_path = output_dir / "events.jsonl"
    metrics_path = output_dir / "metrics.json"
    manifest_path = output_dir / "manifest.json"

    _write_json(scene_path, sph_scene_to_payload(scene))
    np.savez_compressed(
        particles_path,
        positions=result.positions.astype(np.float32),
        velocities=result.velocities.astype(np.float32),
        densities=result.densities.astype(np.float32),
        pressures=result.pressures.astype(np.float32),
    )
    _write_events(events_path, result.events)
    _write_json(metrics_path, compute_sph_metrics(scene, result))
    _write_json(
        manifest_path,
        {
            "run_name": scene.run_name,
            "kind": "sph_dambreak",
            "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "config_path": str(Path(config_path).resolve()),
            "seed": int(scene.seed),
            "frames": int(scene.world.frames),
            "fps": int(scene.world.fps),
            "particle_count": int(result.positions.shape[1]),
            "git_commit": _git_commit(),
            "outputs": {
                "scene": scene_path.name,
                "particles": particles_path.name,
                "events": events_path.name,
                "metrics": metrics_path.name,
            },
        },
    )
    return {
        "scene": scene_path,
        "particles": particles_path,
        "events": events_path,
        "metrics": metrics_path,
        "manifest": manifest_path,
    }


def sph_scene_to_payload(scene: SphSceneConfig) -> dict:
    return {
        "run_name": scene.run_name,
        "seed": int(scene.seed),
        "world": {
            "bounds": list(scene.world.bounds),
            "frames": int(scene.world.frames),
            "fps": int(scene.world.fps),
            "dt": float(scene.world.dt),
            "substeps_per_frame": int(scene.world.substeps_per_frame),
        },
        "fluid": {
            "particle_spacing": float(scene.fluid.particle_spacing),
            "initial_block_min": list(scene.fluid.initial_block_min),
            "initial_block_max": list(scene.fluid.initial_block_max),
        },
        "solver": {
            "rest_density": float(scene.solver.rest_density),
            "smoothing_length": float(scene.solver.smoothing_length),
            "gas_constant": float(scene.solver.gas_constant),
            "viscosity": float(scene.solver.viscosity),
            "gravity": list(scene.solver.gravity),
            "boundary_damping": float(scene.solver.boundary_damping),
            "max_velocity": float(scene.solver.max_velocity),
        },
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_events(path: Path, events: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def _git_commit() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True)
    except Exception:  # noqa: BLE001
        return None
    return result.stdout.strip() or None

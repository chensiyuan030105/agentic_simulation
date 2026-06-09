from __future__ import annotations

import numpy as np

from .sph import SphSceneConfig, SphSimulationResult


def compute_sph_metrics(scene: SphSceneConfig, result: SphSimulationResult) -> dict:
    positions = result.positions.astype(np.float64)
    velocities = result.velocities.astype(np.float64)
    densities = result.densities.astype(np.float64)
    bounds = np.asarray(scene.world.bounds, dtype=np.float64)
    speeds = np.linalg.norm(velocities, axis=2)
    center_of_mass = positions.mean(axis=1)
    min_pos = positions.min(axis=(0, 1))
    max_pos = positions.max(axis=(0, 1))
    return {
        "frame_count": int(positions.shape[0]),
        "particle_count": int(positions.shape[1]),
        "bounds": list(scene.world.bounds),
        "mean_density": float(densities.mean()),
        "min_density": float(densities.min()),
        "max_density": float(densities.max()),
        "max_speed": float(speeds.max()),
        "mean_speed_final": float(speeds[-1].mean()),
        "center_of_mass_start": center_of_mass[0].tolist(),
        "center_of_mass_final": center_of_mass[-1].tolist(),
        "position_min": min_pos.tolist(),
        "position_max": max_pos.tolist(),
        "outside_bounds_count": int(np.sum((positions < 0.0) | (positions > bounds[None, None, :]))),
    }

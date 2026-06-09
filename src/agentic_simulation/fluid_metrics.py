from __future__ import annotations

import numpy as np

from .fluid import FluidSceneConfig, FluidSimulationResult


def compute_fluid_metrics(scene: FluidSceneConfig, result: FluidSimulationResult) -> dict:
    height = result.height.astype(np.float64)
    free = ~result.mask
    masses = height[:, free].sum(axis=1)
    abs_mean = max(abs(float(masses.mean())), 1.0e-12)
    max_abs = np.max(np.abs(height[:, free]), axis=1)
    rms = np.sqrt(np.mean(height[:, free] * height[:, free], axis=1))
    return {
        "frame_count": int(height.shape[0]),
        "grid": list(scene.world.grid),
        "free_cell_count": int(np.sum(free)),
        "solid_cell_count": int(np.sum(result.mask)),
        "mass_mean": float(masses.mean()),
        "mass_min": float(masses.min()),
        "mass_max": float(masses.max()),
        "mass_range": float(masses.max() - masses.min()),
        "mass_relative_range": float((masses.max() - masses.min()) / abs_mean),
        "mass_endpoint_drift": float(masses[-1] - masses[0]),
        "mass_endpoint_relative_drift": float((masses[-1] - masses[0]) / abs_mean),
        "height_max_abs_over_time": float(max_abs.max()),
        "height_rms_mean": float(rms.mean()),
        "height_rms_final": float(rms[-1]),
    }

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .policies import compute_steering
from .scene import SceneConfig


@dataclass(frozen=True)
class SimulationResult:
    positions: np.ndarray
    orientations: np.ndarray
    velocities: np.ndarray
    actions: np.ndarray
    events: list[dict]


def run_simulation(scene: SceneConfig) -> SimulationResult:
    """Run a deterministic multi-agent arena simulation."""
    frames = int(scene.world.frames)
    agent_count = len(scene.agents)
    positions_2d = np.zeros((frames, agent_count, 2), dtype=np.float64)
    velocities_2d = np.zeros_like(positions_2d)
    actions = np.zeros((frames, agent_count, 4), dtype=np.float64)
    events: list[dict] = []
    reached = [False] * agent_count

    positions_2d[0] = np.asarray([agent.start for agent in scene.agents], dtype=np.float64)
    velocities_2d[0] = 0.0

    for frame in range(frames - 1):
        desired, action_frame = compute_steering(
            positions=positions_2d[frame],
            velocities=velocities_2d[frame],
            agents=scene.agents,
            obstacles=scene.obstacles,
            policy=scene.policy,
            world=scene.world,
        )
        actions[frame] = action_frame
        velocities_2d[frame + 1] = desired
        positions_2d[frame + 1] = positions_2d[frame] + desired * float(scene.world.dt)
        positions_2d[frame + 1] = _clamp_to_world(positions_2d[frame + 1], scene)

        for agent_idx, agent in enumerate(scene.agents):
            if reached[agent_idx]:
                continue
            dist = float(np.linalg.norm(positions_2d[frame + 1, agent_idx] - np.asarray(agent.goal)))
            if dist <= float(scene.policy.goal_tolerance):
                reached[agent_idx] = True
                events.append(
                    {
                        "frame": frame + 1,
                        "type": "goal_reached",
                        "agent": agent.id,
                        "distance": dist,
                    }
                )
    actions[-1] = actions[-2]

    positions = _lift_positions(positions_2d, scene)
    velocities = _lift_vectors(velocities_2d)
    orientations = _orientations_from_velocity(velocities_2d)
    return SimulationResult(
        positions=positions.astype(np.float32),
        orientations=orientations.astype(np.float32),
        velocities=velocities.astype(np.float32),
        actions=actions.astype(np.float32),
        events=events,
    )


def _clamp_to_world(positions: np.ndarray, scene: SceneConfig) -> np.ndarray:
    half = np.asarray(scene.world.size, dtype=np.float64) * 0.5
    margin = float(scene.world.boundary_margin)
    low = -half + margin
    high = half - margin
    return np.clip(positions, low[None, :], high[None, :])


def _lift_positions(positions_2d: np.ndarray, scene: SceneConfig) -> np.ndarray:
    out = np.zeros((positions_2d.shape[0], positions_2d.shape[1], 3), dtype=np.float64)
    out[:, :, 0] = positions_2d[:, :, 0]
    out[:, :, 1] = positions_2d[:, :, 1]
    for idx, agent in enumerate(scene.agents):
        out[:, idx, 2] = float(agent.radius)
    return out


def _lift_vectors(vectors_2d: np.ndarray) -> np.ndarray:
    out = np.zeros((vectors_2d.shape[0], vectors_2d.shape[1], 3), dtype=np.float64)
    out[:, :, 0] = vectors_2d[:, :, 0]
    out[:, :, 1] = vectors_2d[:, :, 1]
    return out


def _orientations_from_velocity(velocities_2d: np.ndarray) -> np.ndarray:
    """Return z-axis yaw quaternions as (w, x, y, z)."""
    out = np.zeros((velocities_2d.shape[0], velocities_2d.shape[1], 4), dtype=np.float64)
    out[:, :, 0] = 1.0
    speeds = np.linalg.norm(velocities_2d, axis=2)
    mask = speeds > 1.0e-8
    yaw = np.zeros_like(speeds)
    yaw[mask] = np.arctan2(velocities_2d[:, :, 1][mask], velocities_2d[:, :, 0][mask])
    out[:, :, 0] = np.cos(0.5 * yaw)
    out[:, :, 3] = np.sin(0.5 * yaw)
    return out

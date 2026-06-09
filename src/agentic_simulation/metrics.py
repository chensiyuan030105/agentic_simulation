from __future__ import annotations

import numpy as np

from .scene import SceneConfig
from .simulation import SimulationResult


def compute_metrics(scene: SceneConfig, result: SimulationResult) -> dict:
    """Compute lightweight diagnostics for a completed run."""
    positions_xy = result.positions[:, :, :2].astype(np.float64)
    velocities_xy = result.velocities[:, :, :2].astype(np.float64)
    goals = np.asarray([agent.goal for agent in scene.agents], dtype=np.float64)

    final_delta = positions_xy[-1] - goals[None, :, :]
    final_distances = np.linalg.norm(final_delta[0], axis=1)
    speed = np.linalg.norm(velocities_xy, axis=2)
    path_lengths = np.sum(
        np.linalg.norm(positions_xy[1:] - positions_xy[:-1], axis=2),
        axis=0,
    )

    reached_agents = {
        str(event["agent"])
        for event in result.events
        if event.get("type") == "goal_reached"
    }

    return {
        "frame_count": int(result.positions.shape[0]),
        "agent_count": int(result.positions.shape[1]),
        "event_count": int(len(result.events)),
        "goal_reached_count": int(len(reached_agents)),
        "path_length_mean": float(np.mean(path_lengths)),
        "path_length_max": float(np.max(path_lengths)),
        "speed_mean": float(np.mean(speed)),
        "speed_max": float(np.max(speed)),
        "final_goal_distance_mean": float(np.mean(final_distances)),
        "final_goal_distance_max": float(np.max(final_distances)),
        "per_agent": [
            {
                "id": agent.id,
                "path_length": float(path_lengths[idx]),
                "final_goal_distance": float(final_distances[idx]),
                "reached_goal": agent.id in reached_agents,
            }
            for idx, agent in enumerate(scene.agents)
        ],
    }

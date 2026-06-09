from __future__ import annotations

import numpy as np

from .scene import AgentConfig, ObstacleConfig, PolicyConfig, WorldConfig


def normalized(vec: np.ndarray, eps: float = 1.0e-12) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= eps:
        return np.zeros_like(vec, dtype=np.float64)
    return np.asarray(vec, dtype=np.float64) / norm


def compute_steering(
    positions: np.ndarray,
    velocities: np.ndarray,
    agents: tuple[AgentConfig, ...],
    obstacles: tuple[ObstacleConfig, ...],
    policy: PolicyConfig,
    world: WorldConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute desired planar velocities and diagnostic action channels."""
    agent_count = len(agents)
    desired = np.zeros((agent_count, 2), dtype=np.float64)
    actions = np.zeros((agent_count, 4), dtype=np.float64)

    for idx, agent in enumerate(agents):
        pos = positions[idx]
        goal = np.asarray(agent.goal, dtype=np.float64)
        to_goal = goal - pos
        goal_dir = normalized(to_goal)
        goal_velocity = goal_dir * float(agent.speed)

        obstacle_push = _obstacle_avoidance(pos, obstacles, policy)
        separation_push = _agent_separation(idx, positions, policy)
        boundary_push = _boundary_avoidance(pos, world)

        target_velocity = goal_velocity + obstacle_push + separation_push + boundary_push
        target_speed = float(np.linalg.norm(target_velocity))
        max_speed = float(agent.speed) * 1.35
        if target_speed > max_speed:
            target_velocity = target_velocity / target_speed * max_speed

        desired[idx] = (1.0 - float(policy.damping)) * target_velocity + float(policy.damping) * velocities[idx]
        actions[idx, 0] = float(np.linalg.norm(goal_velocity))
        actions[idx, 1] = float(np.linalg.norm(obstacle_push))
        actions[idx, 2] = float(np.linalg.norm(separation_push))
        actions[idx, 3] = float(np.linalg.norm(boundary_push))

    return desired, actions


def _obstacle_avoidance(
    pos: np.ndarray,
    obstacles: tuple[ObstacleConfig, ...],
    policy: PolicyConfig,
) -> np.ndarray:
    push = np.zeros(2, dtype=np.float64)
    influence = max(1.0e-6, float(policy.obstacle_influence))
    for obstacle in obstacles:
        center = np.asarray(obstacle.center, dtype=np.float64)
        delta = pos - center
        dist = float(np.linalg.norm(delta))
        clearance = dist - float(obstacle.radius)
        if clearance >= influence:
            continue
        strength = (influence - clearance) / influence
        if dist <= 1.0e-8:
            direction = np.array([1.0, 0.0], dtype=np.float64)
        else:
            direction = delta / dist
        push += direction * float(policy.obstacle_strength) * strength * strength
    return push


def _agent_separation(idx: int, positions: np.ndarray, policy: PolicyConfig) -> np.ndarray:
    push = np.zeros(2, dtype=np.float64)
    radius = max(1.0e-6, float(policy.separation_radius))
    for other_idx, other_pos in enumerate(positions):
        if other_idx == idx:
            continue
        delta = positions[idx] - other_pos
        dist = float(np.linalg.norm(delta))
        if dist <= 1.0e-8 or dist >= radius:
            continue
        strength = (radius - dist) / radius
        push += delta / dist * float(policy.separation_strength) * strength
    return push


def _boundary_avoidance(pos: np.ndarray, world: WorldConfig) -> np.ndarray:
    half = np.asarray(world.size, dtype=np.float64) * 0.5
    margin = max(1.0e-6, float(world.boundary_margin))
    push = np.zeros(2, dtype=np.float64)
    for axis in range(2):
        low = -half[axis] + margin
        high = half[axis] - margin
        if pos[axis] < low:
            push[axis] += (low - pos[axis]) / margin
        elif pos[axis] > high:
            push[axis] -= (pos[axis] - high) / margin
    return push

# Agentic Simulation

This workspace is intended for building agent-driven simulation scenes and rendering them with Blender 5.1. The first goal is not to implement a complex simulator immediately, but to establish a clean pipeline that separates simulation, data export, and rendering.

## Current Status

The first deterministic demo is implemented. It simulates four sphere agents moving in a 2D arena with circular obstacles, goal seeking, obstacle avoidance, and inter-agent separation. The simulation writes a structured run bundle that can be inspected from Python and rendered by Blender 5.1 when a Blender executable is available.

Blender is not currently available on this machine through `blender` in `PATH`, so the simulation side has been validated locally and the render script is prepared for Blender 5.1 execution once `blender_executable` is set.

## Quick Start

Install the small Python-side dependency set:

```bash
pip install -r requirements.txt
```

Run the demo simulation:

```bash
python scripts/run_sim.py \
  --config configs/sim/basic_scene.yaml \
  --out outputs/runs/demo_001
```

Inspect the generated run bundle:

```bash
python scripts/inspect_run.py outputs/runs/demo_001
```

Expected array shapes:

```text
positions     (240, 4, 3)
orientations  (240, 4, 4)
velocities    (240, 4, 3)
actions       (240, 4, 4)
```

Render with Blender 5.1 after updating `configs/render/blender_5_1.yaml` or passing `--blender`:

```bash
python scripts/render_run.py outputs/runs/demo_001 \
  --config configs/render/blender_5_1.yaml \
  --blender /path/to/blender-5.1/blender
```

## Core Idea

The project should be split into two independent layers:

1. Simulation layer
   - Generates agent states, trajectories, events, and metrics.
   - Does not import or depend on Blender.
   - Writes stable intermediate data formats.

2. Blender render layer
   - Reads simulation outputs.
   - Builds a Blender scene, assigns materials, inserts animation keyframes, configures camera and lighting, then renders video.
   - Does not rerun simulation logic.

This separation keeps the project reproducible and makes it easier to swap policies, simulation rules, render styles, or future physics engines without rewriting the whole pipeline.

## Recommended Pipeline

```text
YAML config
  -> Python simulation
  -> scene.json + trajectories.npz + events.jsonl + metrics.json
  -> Blender 5.1 background render
  -> scene.blend + preview.mp4 + optional frames
```

Example command shape:

```bash
python scripts/run_sim.py \
  --config configs/sim/basic_scene.yaml \
  --out outputs/runs/demo_001

/path/to/blender-5.1/blender --background --factory-startup \
  --python blender/render_scene.py -- \
  --config configs/render/blender_5_1.yaml \
  --run outputs/runs/demo_001
```

The executable path is intentionally configurable rather than hard-coded.

## Proposed Directory Layout

```text
agentic_simulation/
  README.md
  prompts.txt

  configs/
    sim/
      basic_scene.yaml
    render/
      blender_5_1.yaml

  src/
    agentic_simulation/
      __init__.py
      config.py
      scene.py
      agents.py
      policies.py
      simulation.py
      io.py
      metrics.py

  scripts/
    run_sim.py
    inspect_run.py
    render_run.py

  blender/
    render_scene.py
    materials.py
    camera.py
    geometry.py

  assets/
    models/
    textures/
    hdri/

  outputs/
    runs/
      <run_name>/
        scene.json
        trajectories.npz
        events.jsonl
        metrics.json
        manifest.json
        preview.mp4
        scene.blend
```

## Intermediate Data Formats

### `scene.json`

Stores static scene information: world size, frame settings, agents, obstacles, and goals.

```json
{
  "world": {
    "size": [20, 20],
    "fps": 24,
    "frames": 240
  },
  "agents": [
    {
      "id": "agent_0",
      "type": "sphere_agent",
      "radius": 0.25,
      "color": [0.2, 0.5, 1.0]
    }
  ],
  "obstacles": [],
  "goals": []
}
```

### `trajectories.npz`

Stores dense per-frame simulation arrays.

```text
positions:     (T, A, 3)
orientations:  (T, A, 4)  # quaternion, optional for simple sphere agents
actions:       (T, A, K)  # optional policy/action values
states:        optional extra state channels
```

### `events.jsonl`

Stores sparse events that occur during simulation.

```json
{"frame": 35, "type": "goal_reached", "agent": "agent_0"}
```

### `manifest.json`

Records run metadata for reproducibility.

Useful fields:

```json
{
  "run_name": "demo_001",
  "created_at": "2026-06-09 12:16:50 CST",
  "config_path": "configs/sim/basic_scene.yaml",
  "seed": 0,
  "frames": 240,
  "fps": 24,
  "git_commit": "..."
}
```

## Implemented First Demo

The implemented starter scene intentionally avoids complex physics. It contains:

- A flat 2D arena represented in 3D.
- Multiple sphere or capsule agents.
- Static obstacles.
- Goal markers.
- Simple policies such as seek, avoid, arrive, and flock.
- Colored path trails in Blender.
- One orbit or angled camera view.

This is enough to validate the full simulation-to-render pipeline without being blocked by rigid-body contact, mesh deformation, or external simulators. The current policy combines goal seeking, circular obstacle avoidance, inter-agent separation, boundary clamping, and velocity damping.

## Simulation Module Responsibilities

The simulation package should own:

- Config loading and validation.
- Scene construction.
- Agent state representation.
- Policy evaluation.
- Time stepping.
- Collision or boundary handling if needed.
- Metric computation.
- Writing `scene.json`, `trajectories.npz`, `events.jsonl`, and `manifest.json`.

The simulation layer should not import `bpy`.

## Blender Render Module Responsibilities

The Blender scripts should own:

- Clearing the default scene.
- Reading `scene.json` and `trajectories.npz`.
- Creating ground, agents, obstacles, goals, and trails.
- Assigning materials.
- Inserting keyframes for agent motion.
- Configuring camera, lights, render engine, resolution, and FPS.
- Saving `.blend` files.
- Rendering `.mp4` videos or image sequences.

The render layer should not contain policy or simulation logic.

## Blender 5.1 Render Strategy

For the first version, use object transform keyframes:

```text
for each agent:
  create mesh object
  for each frame:
    set object.location
    insert location keyframe
```

Recommended visual elements:

- Agents as UV spheres or capsules.
- Goals as small emissive markers or rings.
- Obstacles as simple cubes/cylinders.
- Motion trails as Blender curves.
- Ground as a large plane with subtle grid material.
- Camera in a fixed angled view or orbit view.

For later versions:

- Deforming objects can use shape keys or mesh caches.
- Large particle/agent systems can use instancing or Geometry Nodes.
- Physics-heavy scenes can use external simulation engines and keep Blender as a renderer.

## Render Config Shape

```yaml
blender_executable: /path/to/blender-5.1/blender
engine: EEVEE
fps: 24
width: 1920
height: 1080

camera:
  mode: orbit
  target: [0, 0, 0]
  distance: 18
  elevation: 55

output:
  save_blend: true
  render_mp4: true
```

## Engineering Rules

- Keep simulation and rendering independent.
- Keep random seeds explicit.
- Keep all generated run outputs under `outputs/runs/<run_name>/`.
- Use structured data formats instead of ad hoc text parsing.
- Make Blender executable path configurable.
- Save enough metadata to reproduce each run.
- Start with a simple deterministic demo before adding physics or learned policies.

## Suggested Next Implementation Order

Completed:

1. Add config files and Python package skeleton.
2. Implement a simple arena scene and deterministic agent policy.
3. Export `scene.json`, `trajectories.npz`, `events.jsonl`, `metrics.json`, and `manifest.json`.
4. Implement a Blender script that can render those outputs.
5. Add a run manifest and basic metrics.

Next:

1. Install or configure Blender 5.1 and run the first actual render.
2. Add richer policies, obstacles, and interactions.
3. Add optional image-sequence rendering for debugging.
4. Add camera presets and visual style presets.
5. Add more advanced rendering and optional physics engines.

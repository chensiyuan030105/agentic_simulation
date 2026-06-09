# Agentic Simulation

This workspace is intended for building agent-driven simulation scenes and rendering them with Blender 5.1. The first goal is not to implement a complex simulator immediately, but to establish a clean pipeline that separates simulation, data export, and rendering.

## Current Status

The first deterministic agent demo is implemented. It simulates four sphere agents moving in a 2D arena with circular obstacles, goal seeking, obstacle avoidance, and inter-agent separation. The simulation writes a structured run bundle that can be inspected from Python and rendered by Blender 5.1.

A second independent fluid demo is also implemented. It uses a deterministic 2D height-field wave solver with circular solid obstacles, exports dense water fields, computes mass-conservation metrics, and renders the animated water surface in Blender with shape keys.

A third SPH dam-break demo is implemented for a `1 x 1 x 1` box. It uses a small deterministic CPU WCSPH-style particle simulator, exports particle trajectories, and renders the particles as animated water spheres in Blender.

Blender 5.1.0 has been downloaded and validated at:

```text
/ssd/data/ForSiyuan/tools/blender-5.1.0-linux-x64/blender
```

The local system was missing `libxkbcommon.so.0`, so the render config prepends Anaconda's library directory through `LD_LIBRARY_PATH`:

```text
/ssd/data/anaconda3/lib
```

The agent demo has been rendered successfully once, producing `scene.blend` and `preview.mp4` under `outputs/runs/demo_001/`. The fluid and SPH demos produce the same render artifact names under `outputs/runs/fluid_001/` and `outputs/runs/sph_dambreak_001/`.

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

Render with Blender 5.1:

```bash
python scripts/render_run.py outputs/runs/demo_001 \
  --config configs/render/blender_5_1.yaml
```

The configured render output is:

```text
outputs/runs/demo_001/scene.blend
outputs/runs/demo_001/preview.mp4
```

## Fluid Demo

Run the fluid simulation:

```bash
python scripts/run_fluid.py \
  --config configs/sim/fluid_scene.yaml \
  --out outputs/runs/fluid_001
```

Inspect the generated run bundle and conservation metrics:

```bash
python scripts/inspect_fluid.py outputs/runs/fluid_001
```

Expected array shapes:

```text
height    (180, 96, 96)
velocity  (180, 96, 96)
mask      (96, 96)
```

Render the water surface with Blender 5.1:

```bash
python scripts/render_fluid_run.py outputs/runs/fluid_001 \
  --config configs/render/blender_5_1.yaml
```

The configured fluid render output is:

```text
outputs/runs/fluid_001/scene.blend
outputs/runs/fluid_001/preview.mp4
```

The current fluid solver is a visual height-field wave model, not a full Navier-Stokes solver. It applies a per-step free-surface mass correction so the discrete total water height remains stable. In the default scene, the inspected mass range is about `6.35e-07`, with relative range about `3.59e-08`.

## SPH Dam-Break Demo

Run the SPH simulation:

```bash
python scripts/run_sph.py \
  --config configs/sim/sph_dambreak.yaml \
  --out outputs/runs/sph_dambreak_001
```

Inspect the generated run bundle:

```bash
python scripts/inspect_sph.py outputs/runs/sph_dambreak_001
```

Expected array shapes for the default run:

```text
positions   (120, 396, 3)
velocities  (120, 396, 3)
densities   (120, 396)
pressures   (120, 396)
```

Render with Blender 5.1:

```bash
python scripts/render_sph_run.py outputs/runs/sph_dambreak_001 \
  --config configs/render/blender_5_1.yaml
```

The configured SPH render output is:

```text
outputs/runs/sph_dambreak_001/scene.blend
outputs/runs/sph_dambreak_001/preview.mp4
```

The current SPH solver is a compact CPU implementation intended for scene prototyping, not a production fluid solver. It uses uniform-grid neighbor search, Poly6 density estimation, Spiky pressure forces, viscosity, gravity, and damped collision against the six walls of the unit box. The default run has `396` particles, `120` frames, and no out-of-bounds particles.

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
Agent YAML config
  -> Python agent simulation
  -> scene.json + trajectories.npz + events.jsonl + metrics.json
  -> Blender 5.1 background render
  -> scene.blend + preview.mp4 + optional frames

Fluid YAML config
  -> Python height-field simulation
  -> fluid_scene.json + fields.npz + events.jsonl + metrics.json
  -> Blender 5.1 background render
  -> scene.blend + preview.mp4 + optional frames

SPH YAML config
  -> Python WCSPH-style particle simulation
  -> sph_scene.json + particles.npz + events.jsonl + metrics.json
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
      fluid_scene.yaml
      sph_dambreak.yaml
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
      fluid.py
      fluid_io.py
      fluid_metrics.py
      sph.py
      sph_io.py
      sph_metrics.py

  scripts/
    run_sim.py
    inspect_run.py
    render_run.py
    run_fluid.py
    inspect_fluid.py
    render_fluid_run.py
    run_sph.py
    inspect_sph.py
    render_sph_run.py

  blender/
    render_scene.py
    render_fluid.py
    render_sph.py
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

### `fluid_scene.json`

Stores static fluid-scene information: grid size, world extent, frame settings, solver settings, initial disturbances, and obstacles.

### `fields.npz`

Stores dense per-frame fluid arrays.

```text
height:    (T, H, W)  # water surface displacement
velocity:  (T, H, W)  # estimated vertical velocity
mask:      (H, W)     # solid obstacle cells
```

### `sph_scene.json`

Stores static SPH scene information: unit-box bounds, frame settings, initial water block, particle spacing, and solver parameters.

### `particles.npz`

Stores dense per-frame SPH particle arrays.

```text
positions:   (T, N, 3)
velocities:  (T, N, 3)
densities:   (T, N)
pressures:   (T, N)
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
blender_executable: /ssd/data/ForSiyuan/tools/blender-5.1.0-linux-x64/blender
library_paths:
  - /ssd/data/anaconda3/lib
engine: EEVEE
fps: 24
width: 1920
height: 1080

camera:
  mode: fixed
  location: [0.0, -18.0, 15.0]
  target: [0, 0, 0]
  focal_length: 45.0

output:
  save_blend: true
  render_mp4: true
  blend_name: scene.blend
  video_name: preview.mp4
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

1. Improve the first rendered scene visually after inspecting `preview.mp4`.
2. Add richer policies, obstacles, and interactions.
3. Add optional image-sequence rendering for debugging.
4. Add camera presets and visual style presets.
5. Add more advanced rendering and optional physics engines.

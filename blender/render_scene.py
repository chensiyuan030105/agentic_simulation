from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from camera import create_camera
from geometry import clear_scene, create_agent, create_cylinder, create_ground, create_polyline_curve
from materials import make_emissive_material, make_material


def _argv_after_double_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an agentic simulation run with Blender 5.1.")
    parser.add_argument("--config", type=Path, required=True, help="Render YAML config.")
    parser.add_argument("--run", type=Path, required=True, help="Run directory containing scene.json and trajectories.npz.")
    parser.add_argument("--video-out", type=Path, default=None, help="Optional explicit MP4 output path.")
    parser.add_argument("--blend-out", type=Path, default=None, help="Optional explicit .blend output path.")
    return parser.parse_args(_argv_after_double_dash())


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except Exception as exc:  # noqa: BLE001
        raise ImportError("PyYAML is required inside Blender's Python environment.") from exc
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configure_render(config: dict, run_dir: Path, video_out: Path) -> None:
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.render.fps = int(config.get("fps", 24))
    scene.render.resolution_x = int(config.get("width", 1920))
    scene.render.resolution_y = int(config.get("height", 1080))
    scene.render.resolution_percentage = 100
    scene.render.use_file_extension = True
    scene.render.film_transparent = False

    engine = str(config.get("engine", "EEVEE")).upper()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if engine == "EEVEE" else "CYCLES"

    video_out.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(video_out.with_suffix(""))
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.color = (0.93, 0.94, 0.96)
    del run_dir


def add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(0.0, 0.0, 8.0))
    sun = bpy.context.object
    sun.name = "Sun"
    sun.data.energy = 2.0
    sun.rotation_euler = (0.7, 0.0, 0.55)

    bpy.ops.object.light_add(type="AREA", location=(0.0, -6.0, 8.0))
    area = bpy.context.object
    area.name = "Key_Area"
    area.data.energy = 450.0
    area.data.size = 6.0


def animate_agents(scene_payload: dict, positions: np.ndarray, orientations: np.ndarray, style: dict) -> None:
    show_trails = bool(style.get("show_trails", True))
    trail_width = float(style.get("trail_width", 0.035))
    agents = scene_payload["agents"]
    frame_count = int(positions.shape[0])
    bpy.context.scene.frame_end = frame_count

    for agent_idx, agent in enumerate(agents):
        color = tuple(float(v) for v in agent.get("color", [0.2, 0.5, 1.0]))
        radius = float(agent.get("radius", 0.3))
        material = make_material(f"mat_{agent['id']}", color=color, roughness=0.32)
        obj = create_agent(str(agent["id"]), radius=radius, material=material)

        for frame_idx in range(frame_count):
            obj.location = tuple(float(v) for v in positions[frame_idx, agent_idx])
            quat = orientations[frame_idx, agent_idx]
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))
            obj.keyframe_insert(data_path="location", frame=frame_idx + 1)
            obj.keyframe_insert(data_path="rotation_quaternion", frame=frame_idx + 1)

        if show_trails:
            trail_points = positions[:, agent_idx].copy()
            trail_points[:, 2] = np.maximum(trail_points[:, 2] * 0.35, 0.08)
            trail_mat = make_material(f"trail_{agent['id']}", color=color, roughness=0.7)
            create_polyline_curve(f"trail_{agent['id']}", trail_points, trail_mat, bevel_depth=trail_width)


def create_static_scene(scene_payload: dict, style: dict) -> None:
    world = scene_payload["world"]
    world_size = tuple(float(v) for v in world.get("size", [20.0, 20.0]))
    ground_color = tuple(float(v) for v in style.get("ground_color", [0.82, 0.84, 0.86]))
    obstacle_color = tuple(float(v) for v in style.get("obstacle_color", [0.16, 0.16, 0.18]))
    goal_color = tuple(float(v) for v in style.get("goal_color", [0.95, 0.95, 0.95]))

    create_ground(world_size, make_material("Ground_Material", ground_color, roughness=0.55))
    obstacle_mat = make_material("Obstacle_Material", obstacle_color, roughness=0.35)
    goal_mat = make_emissive_material("Goal_Material", goal_color, strength=0.65)

    for obstacle in scene_payload.get("obstacles", []):
        center = obstacle.get("center", [0.0, 0.0])
        create_cylinder(
            name=str(obstacle.get("id", "obstacle")),
            radius=float(obstacle.get("radius", 1.0)),
            depth=0.42,
            location=(float(center[0]), float(center[1]), 0.21),
            material=obstacle_mat,
        )

    for agent in scene_payload.get("agents", []):
        goal = agent.get("goal", [0.0, 0.0])
        create_cylinder(
            name=f"goal_{agent['id']}",
            radius=max(0.16, float(agent.get("radius", 0.3)) * 0.75),
            depth=0.08,
            location=(float(goal[0]), float(goal[1]), 0.04),
            material=goal_mat,
        )


def set_linear_interpolation() -> None:
    for obj in bpy.data.objects:
        anim = obj.animation_data
        if anim is None or anim.action is None:
            continue
        for fcurve in anim.action.fcurves:
            for point in fcurve.keyframe_points:
                point.interpolation = "LINEAR"


def main() -> None:
    args = parse_args()
    config = load_yaml(args.config.expanduser().resolve())
    run_dir = args.run.expanduser().resolve()
    scene_payload = read_json(run_dir / "scene.json")
    with np.load(run_dir / "trajectories.npz") as bundle:
        positions = np.asarray(bundle["positions"], dtype=np.float32)
        orientations = np.asarray(bundle["orientations"], dtype=np.float32)

    output_cfg = config.get("output", {}) if isinstance(config.get("output", {}), dict) else {}
    video_out = args.video_out or (run_dir / str(output_cfg.get("video_name", "preview.mp4")))
    blend_out = args.blend_out or (run_dir / str(output_cfg.get("blend_name", "scene.blend")))

    clear_scene()
    configure_render(config=config, run_dir=run_dir, video_out=video_out.expanduser().resolve())
    create_static_scene(scene_payload, config.get("style", {}))
    animate_agents(scene_payload, positions, orientations, config.get("style", {}))
    add_lights()
    create_camera(config.get("camera", {}))
    set_linear_interpolation()

    if bool(output_cfg.get("save_blend", True)):
        blend_out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_out.expanduser().resolve()))
    if bool(output_cfg.get("render_mp4", True)):
        bpy.ops.render.render(animation=True)

    print("render complete")
    print(f"run_dir  : {run_dir}")
    print(f"blend    : {blend_out}")
    print(f"video    : {video_out}")


if __name__ == "__main__":
    main()

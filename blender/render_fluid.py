from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from camera import create_camera
from geometry import clear_scene, create_cylinder, create_ground
from materials import make_material


def _argv_after_double_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a height-field fluid simulation with Blender 5.1.")
    parser.add_argument("--config", type=Path, required=True, help="Render JSON or YAML config.")
    parser.add_argument("--run", type=Path, required=True, help="Run directory containing fluid_scene.json and fields.npz.")
    parser.add_argument("--video-out", type=Path, default=None, help="Optional explicit MP4 output path.")
    parser.add_argument("--blend-out", type=Path, default=None, help="Optional explicit .blend output path.")
    return parser.parse_args(_argv_after_double_dash())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return read_json(path)
    try:
        import yaml
    except Exception as exc:  # noqa: BLE001
        raise ImportError("Use scripts/render_fluid_run.py so YAML is converted to JSON first.") from exc
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected config mapping in {path}")
    return data


def configure_render(config: dict, video_out: Path, frame_count: int) -> None:
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = int(frame_count)
    scene.render.fps = int(config.get("fps", 24))
    scene.render.resolution_x = int(config.get("width", 1920))
    scene.render.resolution_y = int(config.get("height", 1080))
    scene.render.resolution_percentage = 100
    scene.render.use_file_extension = True
    scene.render.film_transparent = False

    engine = str(config.get("engine", "EEVEE")).upper()
    available_engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
    if engine == "EEVEE":
        scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available_engines else "BLENDER_EEVEE"
    else:
        scene.render.engine = "CYCLES"

    video_out.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(video_out.with_suffix(""))
    if hasattr(scene.render.image_settings, "media_type"):
        scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.color = (0.92, 0.94, 0.97)


def build_surface_mesh(scene_payload: dict, height: np.ndarray, mask: np.ndarray, material) -> bpy.types.Object:
    rows, cols = height.shape[1], height.shape[2]
    extent_x, extent_y = [float(v) for v in scene_payload["world"].get("extent", [10.0, 10.0])]
    xs = np.linspace(-0.5 * extent_x, 0.5 * extent_x, cols, dtype=np.float64)
    ys = np.linspace(-0.5 * extent_y, 0.5 * extent_y, rows, dtype=np.float64)
    xx, yy = np.meshgrid(xs, ys)
    verts = np.column_stack([xx.reshape(-1), yy.reshape(-1), height[0].reshape(-1)])

    faces: list[tuple[int, int, int]] = []
    for row in range(rows - 1):
        for col in range(cols - 1):
            if bool(mask[row, col] or mask[row + 1, col] or mask[row, col + 1] or mask[row + 1, col + 1]):
                continue
            v00 = row * cols + col
            v01 = v00 + 1
            v10 = (row + 1) * cols + col
            v11 = v10 + 1
            faces.append((v00, v10, v11))
            faces.append((v00, v11, v01))

    mesh = bpy.data.meshes.new("Water_Surface_Mesh")
    mesh.from_pydata(verts.tolist(), [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    obj = bpy.data.objects.new("Water_Surface", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    _add_shape_keys(obj, xx=xx, yy=yy, height=height)
    _animate_shape_keys(obj, frame_count=height.shape[0])
    return obj


def _add_shape_keys(obj: bpy.types.Object, xx: np.ndarray, yy: np.ndarray, height: np.ndarray) -> None:
    obj.shape_key_add(name="Basis", from_mix=False)
    frame_count = int(height.shape[0])
    for frame_idx in range(1, frame_count):
        key = obj.shape_key_add(name=f"F{frame_idx:04d}", from_mix=False)
        coords = np.column_stack([xx.reshape(-1), yy.reshape(-1), height[frame_idx].reshape(-1)]).astype(np.float32)
        key.data.foreach_set("co", coords.reshape(-1))


def _animate_shape_keys(obj: bpy.types.Object, frame_count: int) -> None:
    shape_data = obj.data.shape_keys
    if shape_data is None:
        raise RuntimeError("Water surface has no shape keys")
    if shape_data.animation_data:
        shape_data.animation_data_clear()

    keys = list(shape_data.key_blocks)[1:]
    for key in keys:
        key.value = 0.0

    for idx, key in enumerate(keys, start=1):
        peak = idx + 1
        key.value = 0.0
        key.keyframe_insert(data_path="value", frame=peak - 1)
        key.value = 1.0
        key.keyframe_insert(data_path="value", frame=peak)
        if idx < len(keys):
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=peak + 1)
        key.value = 0.0

    if shape_data.animation_data and shape_data.animation_data.action:
        for fcurve in _iter_action_fcurves(shape_data.animation_data.action):
            for point in fcurve.keyframe_points:
                point.interpolation = "LINEAR"


def _iter_action_fcurves(action_data):
    if hasattr(action_data, "fcurves"):
        for fcurve in action_data.fcurves:
            yield fcurve
        return
    if not hasattr(action_data, "layers"):
        return
    for layer in action_data.layers:
        for strip in layer.strips:
            if hasattr(strip, "channelbags"):
                bags = strip.channelbags
            elif hasattr(strip, "channelbag") and strip.channelbag is not None:
                bags = (strip.channelbag,)
            else:
                bags = ()
            for bag in bags:
                for fcurve in bag.fcurves:
                    yield fcurve


def create_static_scene(scene_payload: dict, style: dict) -> None:
    extent = tuple(float(v) for v in scene_payload["world"].get("extent", [10.0, 10.0]))
    ground_color = tuple(float(v) for v in style.get("ground_color", [0.72, 0.74, 0.76]))
    obstacle_color = tuple(float(v) for v in style.get("obstacle_color", [0.12, 0.12, 0.14]))
    create_ground(extent, make_material("Fluid_Ground_Material", ground_color, roughness=0.58))
    obstacle_mat = make_material("Fluid_Obstacle_Material", obstacle_color, roughness=0.34)

    for obstacle in scene_payload.get("obstacles", []):
        center = obstacle.get("center", [0.0, 0.0])
        create_cylinder(
            name=str(obstacle.get("id", "obstacle")),
            radius=float(obstacle.get("radius", 1.0)),
            depth=0.8,
            location=(float(center[0]), float(center[1]), 0.4),
            material=obstacle_mat,
        )


def add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(0.0, 0.0, 8.0))
    sun = bpy.context.object
    sun.name = "Fluid_Sun"
    sun.data.energy = 2.2
    sun.rotation_euler = (0.8, 0.0, 0.45)

    bpy.ops.object.light_add(type="AREA", location=(0.0, -5.0, 7.5))
    area = bpy.context.object
    area.name = "Fluid_Key_Area"
    area.data.energy = 520.0
    area.data.size = 6.5


def _normalize_video_output(video_out: Path) -> None:
    candidates = sorted(video_out.parent.glob(f"{video_out.stem}*.{video_out.suffix.lstrip('.')}"))
    candidates = [path for path in candidates if path != video_out]
    if not candidates:
        return
    newest = max(candidates, key=lambda path: path.stat().st_mtime)
    if video_out.exists():
        video_out.unlink()
    shutil.move(str(newest), str(video_out))


def main() -> None:
    args = parse_args()
    config = load_config(args.config.expanduser().resolve())
    run_dir = args.run.expanduser().resolve()
    scene_payload = read_json(run_dir / "fluid_scene.json")
    with np.load(run_dir / "fields.npz") as bundle:
        height = np.asarray(bundle["height"], dtype=np.float32)
        mask = np.asarray(bundle["mask"], dtype=bool)

    output_cfg = config.get("fluid_output", config.get("output", {}))
    output_cfg = output_cfg if isinstance(output_cfg, dict) else {}
    video_out = args.video_out or (run_dir / str(output_cfg.get("video_name", "fluid_preview.mp4")))
    blend_out = args.blend_out or (run_dir / str(output_cfg.get("blend_name", "fluid_scene.blend")))

    clear_scene()
    configure_render(config=config, video_out=video_out.expanduser().resolve(), frame_count=height.shape[0])
    create_static_scene(scene_payload, config.get("fluid_style", config.get("style", {})))
    water_color = tuple(float(v) for v in config.get("fluid_style", {}).get("water_color", [0.06, 0.36, 0.72]))
    water_mat = make_material("Water_Material", water_color, roughness=0.08)
    build_surface_mesh(scene_payload=scene_payload, height=height, mask=mask, material=water_mat)
    add_lights()
    create_camera(config.get("fluid_camera", config.get("camera", {})))

    if bool(output_cfg.get("save_blend", True)):
        blend_out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_out.expanduser().resolve()))
    if bool(output_cfg.get("render_mp4", True)):
        bpy.ops.render.render(animation=True)
        _normalize_video_output(video_out.expanduser().resolve())

    print("fluid render complete")
    print(f"run_dir  : {run_dir}")
    print(f"blend    : {blend_out}")
    print(f"video    : {video_out}")


if __name__ == "__main__":
    main()

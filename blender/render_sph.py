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
from geometry import clear_scene


def _argv_after_double_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a 3D SPH dam-break simulation with Blender 5.1.")
    parser.add_argument("--config", type=Path, required=True, help="Render JSON config.")
    parser.add_argument("--run", type=Path, required=True, help="Run directory containing sph_scene.json and particles.npz.")
    parser.add_argument("--video-out", type=Path, default=None, help="Optional explicit MP4 output path.")
    parser.add_argument("--blend-out", type=Path, default=None, help="Optional explicit .blend output path.")
    return parser.parse_args(_argv_after_double_dash())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    world.color = (0.93, 0.94, 0.96)


def make_principled_material(
    name: str,
    color: tuple[float, float, float],
    alpha: float = 1.0,
    roughness: float = 0.25,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    material.diffuse_color = (float(color[0]), float(color[1]), float(color[2]), float(alpha))
    if alpha < 1.0:
        material.blend_method = "BLEND"
        material.use_screen_refraction = True
        material.show_transparent_back = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = (float(color[0]), float(color[1]), float(color[2]), float(alpha))
        principled.inputs["Alpha"].default_value = float(alpha)
        principled.inputs["Roughness"].default_value = float(roughness)
        if "Metallic" in principled.inputs:
            principled.inputs["Metallic"].default_value = 0.0
    return material


def create_container(bounds: tuple[float, float, float], material: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5 * bounds[0], 0.5 * bounds[1], 0.5 * bounds[2]))
    obj = bpy.context.object
    obj.name = "Unit_Box_Container"
    obj.dimensions = bounds
    obj.data.materials.append(material)
    modifier = obj.modifiers.new("Container_Wire", "WIREFRAME")
    modifier.thickness = 0.01
    modifier.use_even_offset = True
    return obj


def create_floor(bounds: tuple[float, float, float], material: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5 * bounds[0], 0.5 * bounds[1], -0.015))
    obj = bpy.context.object
    obj.name = "SPH_Floor"
    obj.dimensions = (float(bounds[0]), float(bounds[1]), 0.03)
    obj.data.materials.append(material)
    return obj


def create_particle_objects(positions: np.ndarray, radius: float, material: bpy.types.Material) -> list[bpy.types.Object]:
    particle_count = int(positions.shape[1])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=radius, location=(0.0, 0.0, 0.0))
    template = bpy.context.object
    template.name = "SPH_Particle_Template"
    template.data.name = "SPH_Particle_Mesh"
    template.data.materials.append(material)

    particles: list[bpy.types.Object] = []
    for idx in range(particle_count):
        if idx == 0:
            obj = template
        else:
            obj = bpy.data.objects.new(f"SPH_Particle_{idx:04d}", template.data)
            bpy.context.collection.objects.link(obj)
        obj.name = f"SPH_Particle_{idx:04d}"
        particles.append(obj)
    return particles


def create_particle_cloud_mesh(positions: np.ndarray, radius: float, material: bpy.types.Material) -> bpy.types.Object:
    offsets, base_faces = _octahedron_particle_template(radius)
    frame_count, particle_count = int(positions.shape[0]), int(positions.shape[1])
    verts_per_particle = offsets.shape[0]

    verts = (positions[0, :, None, :] + offsets[None, :, :]).reshape(-1, 3)
    faces: list[tuple[int, int, int]] = []
    for particle_idx in range(particle_count):
        base = particle_idx * verts_per_particle
        for face in base_faces:
            faces.append((base + face[0], base + face[1], base + face[2]))

    mesh = bpy.data.meshes.new("SPH_Particle_Cloud_Mesh")
    mesh.from_pydata(verts.tolist(), [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    obj = bpy.data.objects.new("SPH_Particle_Cloud", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)

    obj.shape_key_add(name="Basis", from_mix=False)
    for frame_idx in range(1, frame_count):
        key = obj.shape_key_add(name=f"F{frame_idx:04d}", from_mix=False)
        coords = (positions[frame_idx, :, None, :] + offsets[None, :, :]).reshape(-1, 3).astype(np.float32)
        key.data.foreach_set("co", coords.reshape(-1))
    _animate_shape_keys(obj, frame_count=frame_count)
    return obj


def _octahedron_particle_template(radius: float) -> tuple[np.ndarray, tuple[tuple[int, int, int], ...]]:
    r = float(radius)
    offsets = np.asarray(
        [
            [r, 0.0, 0.0],
            [-r, 0.0, 0.0],
            [0.0, r, 0.0],
            [0.0, -r, 0.0],
            [0.0, 0.0, r],
            [0.0, 0.0, -r],
        ],
        dtype=np.float32,
    )
    faces = (
        (4, 0, 2),
        (4, 2, 1),
        (4, 1, 3),
        (4, 3, 0),
        (5, 2, 0),
        (5, 1, 2),
        (5, 3, 1),
        (5, 0, 3),
    )
    return offsets, faces


def _animate_shape_keys(obj: bpy.types.Object, frame_count: int) -> None:
    shape_data = obj.data.shape_keys
    if shape_data is None:
        raise RuntimeError("SPH particle cloud has no shape keys")
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


def animate_particles(objects: list[bpy.types.Object], positions: np.ndarray) -> None:
    frame_count = int(positions.shape[0])
    for frame_idx in range(frame_count):
        blender_frame = frame_idx + 1
        for particle_idx, obj in enumerate(objects):
            obj.location = tuple(float(v) for v in positions[frame_idx, particle_idx])
            obj.keyframe_insert(data_path="location", frame=blender_frame)

    for obj in objects:
        if obj.animation_data and obj.animation_data.action:
            for fcurve in _iter_action_fcurves(obj.animation_data.action):
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


def add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(0.0, 0.0, 3.0))
    sun = bpy.context.object
    sun.name = "SPH_Sun"
    sun.data.energy = 1.8
    sun.rotation_euler = (0.7, 0.0, 0.55)

    bpy.ops.object.light_add(type="AREA", location=(0.45, -1.2, 1.7))
    area = bpy.context.object
    area.name = "SPH_Key_Area"
    area.data.energy = 420.0
    area.data.size = 2.0


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
    config = read_json(args.config.expanduser().resolve())
    run_dir = args.run.expanduser().resolve()
    scene_payload = read_json(run_dir / "sph_scene.json")
    with np.load(run_dir / "particles.npz") as bundle:
        positions = np.asarray(bundle["positions"], dtype=np.float32)

    output_cfg = config.get("sph_output", config.get("output", {}))
    output_cfg = output_cfg if isinstance(output_cfg, dict) else {}
    video_out = args.video_out or (run_dir / str(output_cfg.get("video_name", "preview.mp4")))
    blend_out = args.blend_out or (run_dir / str(output_cfg.get("blend_name", "scene.blend")))
    style = config.get("sph_style", {}) if isinstance(config.get("sph_style", {}), dict) else {}

    bounds = tuple(float(v) for v in scene_payload["world"].get("bounds", [1.0, 1.0, 1.0]))
    spacing = float(scene_payload.get("fluid", {}).get("particle_spacing", 0.05))
    particle_radius = float(style.get("particle_radius", 0.45 * spacing))
    object_threshold = int(style.get("object_particle_threshold", 1500))

    clear_scene()
    configure_render(config=config, video_out=video_out.expanduser().resolve(), frame_count=positions.shape[0])
    floor_mat = make_principled_material("SPH_Floor_Material", (0.78, 0.80, 0.82), alpha=1.0, roughness=0.55)
    box_mat = make_principled_material("SPH_Box_Material", (0.10, 0.12, 0.14), alpha=0.42, roughness=0.45)
    water_mat = make_principled_material("SPH_Water_Material", (0.05, 0.38, 0.78), alpha=0.72, roughness=0.12)
    create_floor(bounds, floor_mat)
    create_container(bounds, box_mat)
    if positions.shape[1] <= object_threshold:
        particles = create_particle_objects(positions, radius=particle_radius, material=water_mat)
        animate_particles(particles, positions)
    else:
        create_particle_cloud_mesh(positions, radius=particle_radius, material=water_mat)
    add_lights()
    create_camera(
        config.get(
            "sph_camera",
            {
                "location": [1.55, -2.05, 1.35],
                "target": [0.5, 0.45, 0.35],
                "focal_length": 55.0,
            },
        )
    )

    if bool(output_cfg.get("save_blend", True)):
        blend_out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_out.expanduser().resolve()))
    if bool(output_cfg.get("render_mp4", True)):
        bpy.ops.render.render(animation=True)
        _normalize_video_output(video_out.expanduser().resolve())

    print("sph render complete")
    print(f"run_dir  : {run_dir}")
    print(f"blend    : {blend_out}")
    print(f"video    : {video_out}")


if __name__ == "__main__":
    main()

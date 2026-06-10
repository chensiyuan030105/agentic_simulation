from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import bpy


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
    parser = argparse.ArgumentParser(description="Bake and render a Mantaflow liquid dam-break scene.")
    parser.add_argument("--config", type=Path, required=True, help="Runtime JSON config.")
    parser.add_argument("--out", type=Path, required=True, help="Output run directory.")
    return parser.parse_args(_argv_after_double_dash())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configure_render(render_config: dict, video_out: Path, frame_count: int, fps: int) -> None:
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = int(frame_count)
    scene.render.fps = int(fps)
    scene.render.resolution_x = int(render_config.get("width", 1920))
    scene.render.resolution_y = int(render_config.get("height", 1080))
    scene.render.resolution_percentage = 100
    scene.render.use_file_extension = True
    scene.render.film_transparent = False

    engine = str(render_config.get("engine", "EEVEE")).upper()
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
        material.show_transparent_back = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = (float(color[0]), float(color[1]), float(color[2]), float(alpha))
        principled.inputs["Alpha"].default_value = float(alpha)
        principled.inputs["Roughness"].default_value = float(roughness)
        if "Metallic" in principled.inputs:
            principled.inputs["Metallic"].default_value = 0.0
        if "Transmission Weight" in principled.inputs:
            principled.inputs["Transmission Weight"].default_value = 0.25
        if "IOR" in principled.inputs:
            principled.inputs["IOR"].default_value = 1.333
    return material


def create_domain(bounds: tuple[float, float, float], sim_config: dict, cache_dir: Path, water_material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5 * bounds[0], 0.5 * bounds[1], 0.5 * bounds[2]))
    domain = bpy.context.object
    domain.name = "Mantaflow_Liquid_Domain"
    domain.dimensions = bounds
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = domain.modifiers.new("Mantaflow_Liquid", "FLUID")
    mod.fluid_type = "DOMAIN"
    settings = mod.domain_settings
    settings.domain_type = "LIQUID"
    solver = sim_config.get("solver", {}) if isinstance(sim_config.get("solver", {}), dict) else {}
    settings.resolution_max = int(solver.get("resolution_max", 96))
    settings.time_scale = float(solver.get("time_scale", 1.0))
    settings.cfl_condition = float(solver.get("cfl_condition", 4.0))
    settings.timesteps_min = int(solver.get("timesteps_min", 1))
    settings.timesteps_max = int(solver.get("timesteps_max", 4))
    settings.flip_ratio = float(solver.get("flip_ratio", 0.97))
    settings.use_mesh = True
    settings.particle_radius = float(solver.get("particle_radius", 1.0))
    settings.mesh_particle_radius = float(solver.get("mesh_particle_radius", 1.35))
    settings.mesh_smoothen_pos = int(solver.get("mesh_smoothen_pos", 2))
    settings.mesh_smoothen_neg = int(solver.get("mesh_smoothen_neg", 2))
    settings.use_collision_border_front = True
    settings.use_collision_border_back = True
    settings.use_collision_border_left = True
    settings.use_collision_border_right = True
    settings.use_collision_border_bottom = True
    settings.use_collision_border_top = False
    settings.cache_type = "ALL"
    settings.cache_frame_start = 1
    settings.cache_frame_end = int(sim_config.get("world", {}).get("frames", 120))
    settings.cache_directory = str(cache_dir)
    domain.data.materials.append(water_material)
    return domain


def create_flow_block(sim_config: dict) -> bpy.types.Object:
    liquid = sim_config.get("liquid", {}) if isinstance(sim_config.get("liquid", {}), dict) else {}
    mins = tuple(float(v) for v in liquid.get("block_min", [0.06, 0.06, 0.04]))
    maxs = tuple(float(v) for v in liquid.get("block_max", [0.38, 0.74, 0.58]))
    dims = tuple(maxs[i] - mins[i] for i in range(3))
    loc = tuple(0.5 * (mins[i] + maxs[i]) for i in range(3))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    flow = bpy.context.object
    flow.name = "Initial_Water_Block_Flow"
    flow.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = flow.modifiers.new("Mantaflow_Flow", "FLUID")
    mod.fluid_type = "FLOW"
    settings = mod.flow_settings
    settings.flow_type = "LIQUID"
    settings.flow_behavior = "GEOMETRY"
    settings.flow_source = "MESH"
    settings.use_initial_velocity = False
    flow.hide_render = True
    flow.hide_viewport = True
    return flow


def create_visual_container(bounds: tuple[float, float, float], material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5 * bounds[0], 0.5 * bounds[1], 0.5 * bounds[2]))
    obj = bpy.context.object
    obj.name = "Visual_Unit_Box"
    obj.dimensions = bounds
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    wire = obj.modifiers.new("Visual_Wire", "WIREFRAME")
    wire.thickness = 0.006
    wire.use_even_offset = True
    return obj


def create_floor(bounds: tuple[float, float, float], material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5 * bounds[0], 0.5 * bounds[1], -0.02))
    obj = bpy.context.object
    obj.name = "Mantaflow_Floor"
    obj.dimensions = (bounds[0] * 1.15, bounds[1] * 1.15, 0.04)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(0.0, 0.0, 3.0))
    sun = bpy.context.object
    sun.name = "Mantaflow_Sun"
    sun.data.energy = 1.8
    sun.rotation_euler = (0.75, 0.0, 0.5)

    bpy.ops.object.light_add(type="AREA", location=(0.55, -1.2, 1.7))
    area = bpy.context.object
    area.name = "Mantaflow_Key_Area"
    area.data.energy = 520.0
    area.data.size = 2.2


def bake_fluid(domain: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    domain.select_set(True)
    bpy.context.view_layer.objects.active = domain
    bpy.ops.fluid.bake_all()


def _normalize_video_output(video_out: Path) -> None:
    candidates = sorted(video_out.parent.glob(f"{video_out.stem}*.{video_out.suffix.lstrip('.')}"))
    candidates = [path for path in candidates if path != video_out]
    if not candidates:
        return
    newest = max(candidates, key=lambda path: path.stat().st_mtime)
    if video_out.exists():
        video_out.unlink()
    shutil.move(str(newest), str(video_out))


def write_manifest(out_dir: Path, sim_config: dict, render_config: dict) -> None:
    payload = {
        "run_name": sim_config.get("run_name", "mantaflow_dambreak_001"),
        "kind": "blender_mantaflow_liquid",
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "frames": int(sim_config.get("world", {}).get("frames", 120)),
        "fps": int(sim_config.get("world", {}).get("fps", 24)),
        "resolution_max": int(sim_config.get("solver", {}).get("resolution_max", 96)),
        "outputs": {"blend": "scene.blend", "video": "preview.mp4"},
        "render_engine": render_config.get("engine", "EEVEE"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "mantaflow_scene.json").write_text(json.dumps(sim_config, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    runtime_config = read_json(args.config.expanduser().resolve())
    sim_config = runtime_config["sim"]
    render_config = runtime_config["render"]
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "mantaflow_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    world = sim_config.get("world", {}) if isinstance(sim_config.get("world", {}), dict) else {}
    bounds = tuple(float(v) for v in world.get("bounds", [1.0, 1.0, 1.0]))
    frames = int(world.get("frames", 120))
    fps = int(world.get("fps", 24))
    output_cfg = sim_config.get("render", {}) if isinstance(sim_config.get("render", {}), dict) else {}
    video_out = out_dir / str(output_cfg.get("video_name", "preview.mp4"))
    blend_out = out_dir / str(output_cfg.get("blend_name", "scene.blend"))

    clear_scene()
    configure_render(render_config, video_out=video_out, frame_count=frames, fps=fps)
    water_mat = make_principled_material("Mantaflow_Water", (0.04, 0.34, 0.78), alpha=0.72, roughness=0.04)
    box_mat = make_principled_material("Mantaflow_Box", (0.08, 0.10, 0.12), alpha=0.45, roughness=0.2)
    floor_mat = make_principled_material("Mantaflow_Floor_Material", (0.78, 0.80, 0.82), alpha=1.0, roughness=0.55)
    domain = create_domain(bounds, sim_config, cache_dir=cache_dir, water_material=water_mat)
    create_flow_block(sim_config)
    create_floor(bounds, floor_mat)
    create_visual_container(bounds, box_mat)
    add_lights()
    create_camera(
        render_config.get(
            "mantaflow_camera",
            {"location": [1.55, -2.05, 1.35], "target": [0.5, 0.45, 0.35], "focal_length": 55.0},
        )
    )
    write_manifest(out_dir, sim_config, render_config)

    print("baking mantaflow liquid")
    bake_fluid(domain)

    if bool(output_cfg.get("save_blend", True)):
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))
    if bool(output_cfg.get("render_mp4", True)):
        bpy.ops.render.render(animation=True)
        _normalize_video_output(video_out)

    print("mantaflow render complete")
    print(f"run_dir  : {out_dir}")
    print(f"blend    : {blend_out}")
    print(f"video    : {video_out}")


if __name__ == "__main__":
    main()

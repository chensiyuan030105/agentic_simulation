from __future__ import annotations

import mathutils
import bpy


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = mathutils.Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_camera(config: dict) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = tuple(float(v) for v in config.get("location", [0.0, -18.0, 15.0]))
    camera_data.lens = float(config.get("focal_length", 45.0))
    look_at(camera, tuple(float(v) for v in config.get("target", [0.0, 0.0, 0.0])))
    bpy.context.scene.camera = camera
    return camera

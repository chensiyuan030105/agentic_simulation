from __future__ import annotations

import bpy


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def create_ground(size: tuple[float, float], material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.04))
    obj = bpy.context.object
    obj.name = "Ground"
    obj.dimensions = (float(size[0]), float(size[1]), 0.08)
    obj.data.materials.append(material)
    return obj


def create_cylinder(name: str, radius: float, depth: float, location: tuple[float, float, float], material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=float(radius), depth=float(depth), location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def create_agent(name: str, radius: float, material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=float(radius), location=(0.0, 0.0, float(radius)))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def create_polyline_curve(name: str, points, material, bevel_depth: float) -> bpy.types.Object:
    curve = bpy.data.curves.new(name=name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = float(bevel_depth)
    curve.bevel_resolution = 3
    poly = curve.splines.new("POLY")
    poly.points.add(len(points) - 1)
    for point, co in zip(poly.points, points):
        point.co = (float(co[0]), float(co[1]), float(co[2]), 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj

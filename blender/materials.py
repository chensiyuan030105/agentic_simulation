from __future__ import annotations

import bpy


def make_material(name: str, color: tuple[float, float, float], roughness: float = 0.45):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled is None:
        return material
    principled.inputs["Base Color"].default_value = (float(color[0]), float(color[1]), float(color[2]), 1.0)
    principled.inputs["Roughness"].default_value = float(roughness)
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    return material


def make_emissive_material(name: str, color: tuple[float, float, float], strength: float = 1.0):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    emission = nodes.new(type="ShaderNodeEmission")
    emission.inputs["Color"].default_value = (float(color[0]), float(color[1]), float(color[2]), 1.0)
    emission.inputs["Strength"].default_value = float(strength)
    output = nodes.new(type="ShaderNodeOutputMaterial")
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material

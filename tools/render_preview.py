"""Render a quick isometric preview PNG of an IFC file, headless, through Bonsai.

    blender.exe -b --python tools/render_preview.py -- model.ifc out.png [--top] [--hide IfcRoof,IfcCovering]

Used to check conversions visually. Runs fully offline.
"""

import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
ifc_path, out_png = Path(args[0]), Path(args[1])
top = "--top" in args
hide = tuple(args[args.index("--hide") + 1].split(",")) if "--hide" in args else ()

bpy.ops.bim.load_project(filepath=str(ifc_path))

for o in bpy.data.objects:  # Bonsai names objects "IfcClass/Name"
    if hide and o.name.split("/")[0] in hide:
        o.hide_render = True
meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data.vertices and not o.hide_render]
if not meshes:
    print("PREVIEW: no mesh objects")
    sys.exit(1)
points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector(min(p[i] for p in points) for i in range(3))
hi = Vector(max(p[i] for p in points) for i in range(3))
center, size = (lo + hi) / 2, max((hi - lo).length, 1.0)

cam_data = bpy.data.cameras.new("preview_cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size * 1.05
cam_data.clip_end = size * 10
cam = bpy.data.objects.new("preview_cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
direction = Vector((0, 0, 1)) if top else Vector((1, -1, 0.8)).normalized()
cam.location = center + direction * size * 2
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

scene = bpy.context.scene
scene.camera = cam
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.render.resolution_x, scene.render.resolution_y = 1400, 1000
scene.render.filepath = str(out_png)
bpy.ops.render.render(write_still=True)
print(f"PREVIEW: {len(meshes)} meshes -> {out_png}")

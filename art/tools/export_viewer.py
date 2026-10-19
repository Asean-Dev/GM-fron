"""Exports the "GM Town" Blender scene for the web viewer in art/viewer/.

Run inside Blender after build_town.py, with p pointing at this file in your clone:
    p = "/path/to/GM-fron/art/tools/export_viewer.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_export", "__file__": p})

Writes into art/viewer/:
  town.glb        Draco-compressed model (everything except the ground, grass and helper meshes)
  town-glb.txt    the same bytes as base64; the viewer loads this because the artifact host won't serve .glb
  grassmask.png   4 px per cell over [-45, 145]^2, white where grass may grow
  walkable.txt    copy of art/maps/town/walkable.txt for the cell readout
"""

import base64
import os
import shutil

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "viewer")
MASK_X0, MASK_SIZE, MASK_PPU = -45.0, 190.0, 4
SKIP = {"Ground", "GroundOuter", "GrassMask"}


def export_model(sc):
    path = os.path.join(OUT, "town.glb")
    for ob in sc.objects:
        ob.select_set(ob.type == "MESH" and ob.name not in SKIP)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, use_active_scene=True,
                              export_apply=True, export_cameras=False, export_lights=False, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7)
    for ob in sc.objects:
        ob.select_set(False)
    with open(path, "rb") as src, open(os.path.join(OUT, "town-glb.txt"), "wb") as dst:
        dst.write(base64.b64encode(src.read()))


def export_grass_mask():
    """Raycasts down onto the flat GrassMask mesh build_town.py made from every road, wall and footprint."""
    mask = bpy.data.objects["GrassMask"]
    bvh = BVHTree.FromObject(mask, bpy.context.evaluated_depsgraph_get())
    w = int(MASK_SIZE * MASK_PPU)
    px = [0.0] * (w * w * 4)
    down = Vector((0, 0, -1))
    for j in range(w):
        y = MASK_X0 + (j + 0.5) / MASK_PPU
        for i in range(w):
            x = MASK_X0 + (i + 0.5) / MASK_PPU
            v = 0.0 if bvh.ray_cast(Vector((x, y, 5.0)), down, 10.0)[0] else 1.0
            k = (j * w + i) * 4
            px[k] = px[k + 1] = px[k + 2] = v
            px[k + 3] = 1.0
    img = bpy.data.images.get("GM_GrassMask") or bpy.data.images.new("GM_GrassMask", w, w, alpha=False)
    if tuple(img.size) != (w, w):
        img.scale(w, w)
    img.pixels.foreach_set(px)
    img.filepath_raw = os.path.join(OUT, "grassmask.png")
    img.file_format = "PNG"
    img.save()


def export():
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.data.scenes["GM Town"]
    bpy.context.window.scene = sc
    export_model(sc)
    export_grass_mask()
    shutil.copy(os.path.join(HERE, "..", "maps", "town", "walkable.txt"), os.path.join(OUT, "walkable.txt"))
    print("GM viewer files written to", os.path.normpath(OUT))


export()

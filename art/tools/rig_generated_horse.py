"""Turns an AI-generated horse mesh (Hyper3D Rodin, made from the model sheet) into the game horse.

Run inside Blender after importing the generated asset, with p pointing at this file in your clone:
    p = "/path/to/GM-fron/art/tools/rig_generated_horse.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_rig", "__file__": p, "SOURCE": "RodinHorse"})

SOURCE is the imported object's name. The script:
  1. moves it into its own scene "GM Horse Gen" and joins it into one mesh
  2. turns it to face -Y, scales it to the sheet's 1.49 m height and stands it on the origin
  3. decimates it to about TARGET_TRIS triangles, keeping its UVs and texture
  4. measures the legs, belly, back, head and tail, fits build_horse.py's 24-bone skeleton to them,
     skins with automatic weights and adds the same Idle / Graze / Walk / Gallop actions
  5. renders previews and exports art/models/horse/generated/horse.glb (+ horse.blend)
"""

import math
import os

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = "GM Horse Gen"
HEIGHT = 1.49          # ear tips, from the sheet's scale bar
TARGET_TRIS = 14000
SOURCE = globals().get("SOURCE", "RodinHorse")

# Reuse the skeleton, skinning, animation, preview and export code from the scripted horse.
_lib_path = os.path.join(HERE, "build_horse.py")
lib = {"__name__": "gm_horse_lib", "__file__": _lib_path, "STEPS": []}
exec(compile(open(_lib_path).read(), _lib_path, "exec"), lib)
lib["OUT"] = os.path.join(lib["OUT"], "generated")
lib["SCENE"] = SCENE


def collect_source():
    src = bpy.data.objects[SOURCE]
    meshes = [src] if src.type == "MESH" else [o for o in src.children_recursive if o.type == "MESH"]
    old = bpy.data.scenes.get(SCENE)
    if old is not None and old is not bpy.context.window.scene:
        for ob in list(old.collection.all_objects):
            if ob not in meshes and ob is not src:
                bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.scenes.remove(old)
    sc = bpy.data.scenes.new(SCENE)
    coll = bpy.data.collections.new("HorseGen")
    sc.collection.children.link(coll)
    for ob in meshes:
        world = ob.matrix_world.copy()
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
        ob.parent = None
        ob.matrix_world = world
    if src.type != "MESH" and src.name in bpy.data.objects:
        bpy.data.objects.remove(src, do_unlink=True)
    bpy.context.window.scene = sc
    # Bake transforms into the vertices and join into one mesh.
    for ob in meshes:
        ob.data = ob.data.copy()
        ob.data.transform(ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=meshes[0], object=meshes[0], selected_objects=meshes, selected_editable_objects=meshes):
            bpy.ops.object.join()
    horse = meshes[0]
    horse.name = "HorseGenBody"
    return sc, coll, horse


def orient_and_scale(ob):
    me = ob.data
    co = [v.co.copy() for v in me.vertices]
    mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    size = mx - mn
    # The body runs along the longer horizontal axis; the head end is the one that reaches highest.
    axis = 0 if size.x > size.y else 1
    lo_end = [c for c in co if c[axis] < mn[axis] + size[axis] * 0.25]
    hi_end = [c for c in co if c[axis] > mx[axis] - size[axis] * 0.25]
    head_high = max(c.z for c in hi_end) > max(c.z for c in lo_end)
    # Rotate so the head points to -Y.
    if axis == 0:
        rot = Matrix.Rotation(math.radians(-90 if head_high else 90), 4, "Z")   # +X head -> -Y
    else:
        rot = Matrix.Rotation(math.pi, 4, "Z") if head_high else Matrix.Identity(4)
    me.transform(rot)
    co = [v.co for v in me.vertices]
    mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    s = HEIGHT / (mx.z - mn.z)
    centre = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    me.transform(Matrix.Scale(s, 4) @ Matrix.Translation(-centre))
    me.update()


def weld(ob):
    """Hyper3D splits its mesh into separate pieces along every UV seam. Join them before simplifying: simplified
    piece by piece, the seams stop lining up and the surface cracks open. UVs are per face corner, so they stay."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def decimate(ob):
    weld(ob)
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if tris <= TARGET_TRIS:
        return tris
    mod = ob.modifiers.new("Decimate", "DECIMATE")
    mod.ratio = TARGET_TRIS / tris
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.validate(clean_customdata=False)
    return sum(len(p.vertices) - 2 for p in me.polygons)


def measure(ob):
    """Landmarks for fitting the skeleton: leg columns, belly, back, head and tail tip."""
    co = [v.co for v in ob.data.vertices]
    feet = [c for c in co if c.z < 0.12]
    mid_y = sorted(c.y for c in feet)[len(feet) // 2]
    front = [c for c in feet if c.y < mid_y]
    hind = [c for c in feet if c.y >= mid_y]
    avg = lambda pts, f: sum(f(p) for p in pts) / max(1, len(pts))
    fy, hy = avg(front, lambda p: p.y), avg(hind, lambda p: p.y)
    fx, hx = avg(front, lambda p: abs(p.x)), avg(hind, lambda p: abs(p.x))
    cy = (fy + hy) / 2
    middle = [c for c in co if abs(c.y - cy) < 0.08 and abs(c.x) < 0.1]
    belly, back = min(c.z for c in middle), max(c.z for c in middle)
    head_pts = [c for c in co if c.y < fy - 0.15 and c.z > 0.62 * HEIGHT]
    head = Vector((0, avg(head_pts, lambda p: p.y), avg(head_pts, lambda p: p.z)))
    tip = max(co, key=lambda c: c.y)
    return {"fy": fy, "hy": hy, "fx": fx, "hx": hx, "belly": belly, "back": back, "head": head, "tail_tip": Vector((0, tip.y, tip.z))}


def fit_bones(m):
    """Maps the template skeleton onto the measured horse: legs and body by an affine fit, then the
    neck and head pulled to the measured head, and the tail stretched to the measured tail tip."""
    t_fy, t_hy, t_belly, t_back = -0.33, 0.37, 0.46, 0.94
    ly = (m["hy"] - m["fy"]) / (t_hy - t_fy)
    zb = (m["back"] - 0.0) / t_back

    def affine(p, leg_side=None):
        x, y, z = p
        if leg_side == "F":
            x = math.copysign(m["fx"], x) if x else 0.0
        elif leg_side == "B":
            x = math.copysign(m["hx"], x) if x else 0.0
        return Vector((x, m["fy"] + (y - t_fy) * ly, z * zb))

    t_head = Vector((0, -0.68, 1.19))
    head_shift = m["head"] - affine(t_head)
    t_tail_root, t_tail_tip = Vector((0, 0.53, 0.92)), Vector((0, 0.74, 0.25))
    root = affine(t_tail_root)
    pull = {"neck1": (0.0, 0.5), "neck2": (0.5, 1.0), "head": (1.0, 1.0), "ear.L": (1.0, 1.0), "ear.R": (1.0, 1.0)}
    fitted = []
    for name, head_pt, tail_pt, parent in lib["BONES"]:
        side = "F" if ".F" in name else "B" if ".B" in name else None
        h, t = affine(head_pt, side), affine(tail_pt, side)
        if name in pull:
            h += head_shift * pull[name][0]
            t += head_shift * pull[name][1]
        if name.startswith("tail"):
            # Re-lay the tail chain from the fitted root to the measured tip.
            f0 = (Vector(head_pt) - t_tail_root).length / (t_tail_tip - t_tail_root).length
            f1 = (Vector(tail_pt) - t_tail_root).length / (t_tail_tip - t_tail_root).length
            h, t = root.lerp(m["tail_tip"], f0), root.lerp(m["tail_tip"], f1)
        fitted.append((name, tuple(h), tuple(t), parent))
    return fitted


def skin_via_proxy(rig, ob):
    """Generated meshes are rarely watertight, so heat weighting fails on them. Weight a voxel-remeshed
    (watertight) copy instead, then copy those weights onto the real mesh by nearest surface."""
    proxy = ob.copy()
    proxy.data = ob.data.copy()
    proxy.name = "HorseSkinProxy"
    ob.users_collection[0].objects.link(proxy)

    def remesh(o):
        # Thicken first: where the surface has gaps (welded seams, cut-off pieces) the voxel remesh would
        # otherwise keep only the small closed parts and the whole body would lose its weights.
        t = o.modifiers.new("Thicken", "SOLIDIFY")
        t.thickness, t.offset = 0.03, 0.0
        r = o.modifiers.new("Remesh", "REMESH")
        r.mode, r.voxel_size = "VOXEL", 0.015
    lib["bake"](proxy, remesh)
    lib["skin"](rig, proxy, [], [])
    for g in proxy.vertex_groups:
        if g.name not in ob.vertex_groups:
            ob.vertex_groups.new(name=g.name)
    dt = ob.modifiers.new("Weights", "DATA_TRANSFER")
    dt.object = proxy
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=dt.name)
    bpy.data.objects.remove(proxy, do_unlink=True)
    fill_unweighted(ob, rig)
    ob.parent = rig
    arm = ob.modifiers.new("Armature", "ARMATURE")
    arm.object = rig


def keep_legs_to_legs(ob, m):
    """Automatic weights let the leg bones reach the stirrups and straps hanging beside the barrel, so the
    legs dragged them along. On the flanks between the front and hind legs, leg bones lose their influence
    and the body bones keep it; the legs themselves and the belly seam keep their automatic weights."""
    legs = {g.index for g in ob.vertex_groups if g.name.startswith(("leg_", "hoof."))}
    spine = ob.vertex_groups["spine"]
    between = (m["fy"] + 0.15, m["hy"] - 0.15)
    cleaned = 0
    for v in ob.data.vertices:
        co = v.co
        if not (co.z > 0.3 and abs(co.x) > 0.18 and between[0] < co.y < between[1]):
            continue
        drop = [g.group for g in v.groups if g.group in legs]
        if not drop:
            continue
        keep = sum(g.weight for g in v.groups if g.group not in legs)
        for gi in drop:
            ob.vertex_groups[gi].remove([v.index])
        if keep < 1e-4:
            spine.add([v.index], 1.0, "REPLACE")
        cleaned += 1
    return cleaned


def fill_unweighted(ob, rig):
    """Thin bits (claws, tips) can lose all weight on the proxy and then stay put while the body moves.
    Give each such vertex fully to the nearest deforming bone."""
    from mathutils.geometry import intersect_point_line
    bones = [b for b in rig.data.bones if b.use_deform]
    segs = [(b.name, b.head_local, b.tail_local) for b in bones]
    groups = {name: (ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)) for name, _, _ in segs}
    fixed = 0
    for v in ob.data.vertices:
        if sum(g.weight for g in v.groups) > 0.05:
            continue
        def dist(seg):
            _, h, t = seg
            p, f = intersect_point_line(v.co, h, t)
            return (v.co - (h if f < 0 else t if f > 1 else p)).length
        name = min(segs, key=dist)[0]
        groups[name].add([v.index], 1.0, "REPLACE")
        fixed += 1
    return fixed


def rest_pose(rig, mute):
    for tr in rig.animation_data.nla_tracks:
        tr.mute = mute
    for pb in rig.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)


def run():
    existing = bpy.data.objects.get("HorseGenBody")
    if existing is not None and SCENE in bpy.data.scenes:
        # Re-rig the mesh that is already cleaned up, instead of importing again.
        sc, coll, horse = bpy.data.scenes[SCENE], bpy.data.collections["HorseGen"], existing
        bpy.context.window.scene = sc
        for ob in list(coll.objects):
            if ob is not horse:
                bpy.data.objects.remove(ob, do_unlink=True)
        for ob in list(sc.collection.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        horse.parent = None
        horse.modifiers.clear()
        horse.vertex_groups.clear()
        tris = sum(len(p.vertices) - 2 for p in horse.data.polygons)
    else:
        sc, coll, horse = collect_source()
        orient_and_scale(horse)
        tris = decimate(horse)
    m = measure(horse)
    lib["BONES"][:] = fit_bones(m)
    rig = lib["armature"](coll)
    rig.name = "HorseGenRig"
    skin_via_proxy(rig, horse)
    cleaned = keep_legs_to_legs(horse, m)
    lib["animate"](rig)
    cams = lib["preview_setup"](sc)
    rest_pose(rig, True)
    lib["preview"](sc, cams)
    rest_pose(rig, False)
    lib["export"](sc, rig)
    return {"triangles": tris, "leg_weights_removed_from": cleaned, "landmarks": {k: (tuple(round(x, 3) for x in v) if hasattr(v, "x") else round(v, 3)) for k, v in m.items()}}


if globals().get("RUN", True):
    result = run()
    print("GM generated horse:", result)

"""Game-ready horse for GM, modelled from art/models/horse/model-sheet-horse-v1.png.

Run inside Blender (Blender MCP, or the Text Editor), with p pointing at this file in your clone:
    p = "/path/to/GM-fron/art/tools/build_horse.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_horse", "__file__": p})

Builds the scene "GM Horse" and leaves every other scene alone; rerunning rebuilds it. Steps:
  model    one smooth body mesh with vertex colours, plus mane, tail, eyes and tack
  texture  UV unwrap, then bake colour x painted detail textures (textures/tex-*.png, made with Codex
           imagegen) x soft occlusion into one texture per part: horse-body.png, horse-mane.png, ...
  rig      armature, skin weights, and the actions Idle / Graze / Walk / Gallop
  preview  orthographic renders next to the sheet, written to art/models/horse/preview-*.png
  export   art/models/horse/horse.glb (+ horse.blend)
Pass {"STEPS": ["model", "preview"]} in the exec globals to run only some of them.

Units are metres. The horse stands on the origin facing -Y, which is +Z (forward) in glTF and Unity.
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "models", "horse"))
SCENE = "GM Horse"
FPS = 30

COLORS = {
    "coat": "#a8632f", "coat_light": "#c98a55", "sock": "#5b3a26", "hoof": "#4b4a52",
    "muzzle": "#ecd0ae", "blaze": "#f7efe6", "mane": "#4a2c1a", "eye": "#15111a", "shine": "#ffffff",
    "blanket": "#2e8a84", "gold": "#e0ad3c", "leather": "#7b3424", "leather_dark": "#5c2618", "strap": "#5a3420",
}


def linear(hex_color):
    h = hex_color.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# ---------------------------------------------------------------- primitives into one bmesh

def ellipsoid(bm, center, radii, rot=None, subdiv=3):
    verts = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)["verts"]
    m = Matrix.Diagonal((*radii, 1.0))
    if rot is not None:
        m = rot.to_4x4() @ m
    bmesh.ops.transform(bm, matrix=Matrix.Translation(center) @ m, verts=verts)


def tube(bm, a, b, r0, r1, segs=16):
    """Capped cone from a (radius r0) to b (radius r1)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    verts = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                                  radius1=r0, radius2=r1, depth=d.length)["verts"]
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=verts)


def path_tube(bm, pts, r, segs=6):
    """A thin round strap swept along a polyline (reins, collar)."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = t.cross(Vector((0, 0, 1)))
        if side.length < 1e-4:
            side = t.cross(Vector((1, 0, 0)))
        side.normalize()
        up = side.cross(t)
        rings.append([bm.verts.new(p + (side * math.cos(k * math.tau / segs) + up * math.sin(k * math.tau / segs)) * r)
                      for k in range(segs)])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new((ra[k], ra[(k + 1) % segs], rb[(k + 1) % segs], rb[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])


def ring(bm, center, major, minor, axis, scale=(1, 1, 1), segs=(24, 8)):
    """Torus whose hole points along `axis`."""
    verts = []
    for i in range(segs[0]):
        u = i * math.tau / segs[0]
        for j in range(segs[1]):
            v = j * math.tau / segs[1]
            verts.append(bm.verts.new(((major + minor * math.cos(v)) * math.cos(u),
                                       (major + minor * math.cos(v)) * math.sin(u),
                                       minor * math.sin(v))))
    n, m = segs
    for i in range(n):
        for j in range(m):
            a, b = verts[i * m + j], verts[((i + 1) % n) * m + j]
            c, d = verts[((i + 1) % n) * m + (j + 1) % m], verts[i * m + (j + 1) % m]
            bm.faces.new((a, b, c, d))
    rot = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(center) @ rot @ Matrix.Diagonal((*scale, 1)), verts=verts)


def arch(bm, a0, a1, y0, y1, radius, cz, nx=20, ny=14):
    """A sheet bent around the back (angle a from straight up), later shrink-wrapped onto the body."""
    grid = [[bm.verts.new((radius * math.sin(a0 + (a1 - a0) * i / nx), y0 + (y1 - y0) * j / ny,
                           cz + radius * math.cos(a0 + (a1 - a0) * i / nx))) for j in range(ny + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))


# ---------------------------------------------------------------- objects and materials

_mats = {}


def material(key, rough=0.75, metal=0.0, vertex_colors=False, emit=0.0):
    name = "GMH_" + key
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if vertex_colors:
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*linear(COLORS[key]), 1)
        m.diffuse_color = (*linear(COLORS[key]), 1)
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*linear(COLORS[key]), 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    _mats[name] = m
    return m


def to_object(name, bm, coll, mat):
    me = bpy.data.meshes.new("gmh_" + name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def bake(ob, setup):
    """Adds the modifiers `setup` creates, then replaces the mesh with the evaluated result."""
    setup(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.validate(clean_customdata=False)   # decimation can leave degenerate faces
    for poly in me.polygons:
        poly.use_smooth = True
    return ob


def remesh_smooth(voxel, smooth_iters, target_faces):
    def setup(ob):
        r = ob.modifiers.new("Remesh", "REMESH")
        r.mode, r.voxel_size, r.adaptivity = "VOXEL", voxel, 0.0
        s = ob.modifiers.new("Smooth", "LAPLACIANSMOOTH")
        s.iterations, s.lambda_factor, s.use_volume_preserve = smooth_iters, 0.9, True
    def finish(ob):
        bake(ob, setup)
        ratio = min(1.0, target_faces / max(1, len(ob.data.polygons)))
        def dec(o):
            d = o.modifiers.new("Decimate", "DECIMATE")
            d.ratio = ratio
        bake(ob, dec)
        return ob
    return finish


# ---------------------------------------------------------------- the horse

def body(coll):
    """Chibi pony proportions from the sheet: deep round barrel, thick neck, big head, short sturdy legs."""
    bm = bmesh.new()
    ellipsoid(bm, (0, 0.0, 0.70), (0.25, 0.47, 0.255))           # barrel
    ellipsoid(bm, (0, -0.33, 0.74), (0.245, 0.24, 0.25))          # chest
    ellipsoid(bm, (0, 0.31, 0.73), (0.255, 0.26, 0.25))           # rump
    tube(bm, (0, -0.40, 0.82), (0, -0.56, 1.16), 0.175, 0.135)   # neck
    ellipsoid(bm, (0, -0.48, 1.0), (0.14, 0.15, 0.18))
    ellipsoid(bm, (0, -0.67, 1.20), (0.165, 0.18, 0.17))          # skull
    ellipsoid(bm, (0, -0.83, 1.05), (0.13, 0.13, 0.11))           # muzzle
    tube(bm, (0, -0.70, 1.16), (0, -0.82, 1.06), 0.14, 0.115)
    for sx in (-1, 1):
        ear_rot = Matrix.Rotation(-sx * 0.28, 3, "Y") @ Matrix.Rotation(0.15, 3, "X")
        ellipsoid(bm, (sx * 0.085, -0.63, 1.40), (0.045, 0.028, 0.1), ear_rot, subdiv=2)        # ears
        x = 0.14 * sx
        # Front leg: forearm, knee, cannon, fetlock, hoof.
        tube(bm, (x, -0.33, 0.60), (x, -0.33, 0.31), 0.095, 0.078)
        ellipsoid(bm, (x, -0.33, 0.31), (0.08, 0.08, 0.08), subdiv=2)
        tube(bm, (x, -0.33, 0.31), (x, -0.335, 0.12), 0.072, 0.07)
        ellipsoid(bm, (x, -0.335, 0.115), (0.08, 0.08, 0.075), subdiv=2)
        tube(bm, (x, -0.34, 0.0), (x, -0.34, 0.10), 0.105, 0.09)
        # Hind leg: haunch, gaskin, hock, cannon, fetlock, hoof.
        ellipsoid(bm, (x, 0.30, 0.56), (0.125, 0.16, 0.18))
        tube(bm, (x, 0.33, 0.50), (x, 0.37, 0.31), 0.1, 0.078)
        ellipsoid(bm, (x, 0.37, 0.31), (0.08, 0.08, 0.08), subdiv=2)
        tube(bm, (x, 0.37, 0.31), (x, 0.35, 0.12), 0.072, 0.07)
        ellipsoid(bm, (x, 0.35, 0.115), (0.08, 0.08, 0.075), subdiv=2)
        tube(bm, (x, 0.345, 0.0), (x, 0.345, 0.10), 0.105, 0.09)
    ob = to_object("HorseBody", bm, coll, material("body", rough=0.8, vertex_colors=True))
    remesh_smooth(0.011, 6, 2600)(ob)
    paint_body(ob.data)
    return ob


def body_color(co):
    x, y, z = co
    c = linear(COLORS["coat"])
    c = mix(c, linear(COLORS["coat_light"]), smoothstep(0.55, 0.47, z) * smoothstep(0.25, 0.1, abs(x)) * 0.6)  # pale belly
    legs = smoothstep(0.38, 0.27, z) * (1.0 if abs(y) > 0.18 else 0.0)
    c = mix(c, linear(COLORS["sock"]), legs)
    c = mix(c, linear(COLORS["hoof"]), smoothstep(0.1, 0.085, z))
    m = Vector((x / 0.135, (y + 0.85) / 0.135, (z - 1.04) / 0.115)).length
    c = mix(c, linear(COLORS["muzzle"]), smoothstep(1.0, 0.82, m))
    if y < -0.78 and 1.08 < z < 1.34:
        half = 0.028 + 0.025 * smoothstep(1.2, 1.32, z)
        c = mix(c, linear(COLORS["blaze"]), smoothstep(half, half * 0.6, abs(x)))
    return c


def paint_body(me):
    attr = me.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
    for loop in me.loops:
        attr.data[loop.index].color = (*body_color(me.vertices[loop.vertex_index].co), 1.0)
    me.color_attributes.active_color = attr


def mane(coll):
    """Long chunky locks falling mostly down the left side of the neck, and a forelock swept to one side."""
    bm = bmesh.new()
    poll, withers = Vector((0, -0.60, 1.37)), Vector((0, -0.34, 1.0))
    for i in range(10):
        t = i / 9
        p = poll.lerp(withers, t)
        sx = -1 if i % 3 == 2 else 1
        rot = Matrix.Rotation(0.62, 3, "X") @ Matrix.Rotation(-sx * 0.55, 3, "Y")
        ellipsoid(bm, p + Vector((sx * 0.07, 0.02, -0.09)), (0.06, 0.08, 0.17 - 0.04 * t), rot, subdiv=2)
    # Forelock swept down over the forehead, toward the left eye.
    ellipsoid(bm, (0.025, -0.825, 1.30), (0.055, 0.022, 0.1), Matrix.Rotation(-0.3, 3, "X") @ Matrix.Rotation(0.35, 3, "Y"), subdiv=2)
    ellipsoid(bm, (0, -0.72, 1.37), (0.05, 0.04, 0.045), subdiv=2)
    ob = to_object("HorseMane", bm, coll, material("mane", rough=0.85))
    remesh_smooth(0.009, 5, 800)(ob)
    return ob


def tail(coll):
    """A full tail of four strands fanning out from the dock."""
    bm = bmesh.new()
    steps = 10
    for k, spread in enumerate((-0.085, -0.03, 0.03, 0.085)):
        # Each strand leaves the dock, arcs back, then falls and fans out toward the tip.
        pts = []
        for i in range(steps + 1):
            f = i / steps
            pts.append(Vector((spread * f * f, 0.54 + 0.26 * math.sin(f * 1.4) - 0.03 * k * f, 0.92 - 0.66 * f)))
        for i, p in enumerate(pts):
            f = i / steps
            t = (pts[min(i + 1, steps)] - pts[max(i - 1, 0)]).normalized()
            r = (0.05 + 0.05 * math.sin(f * math.pi * 0.85)) * (1.0 if k in (1, 2) else 0.8)
            ellipsoid(bm, p, (r, r * 0.8, r * 1.5), Vector((0, 0, 1)).rotation_difference(t).to_matrix(), subdiv=2)
    ob = to_object("HorseTail", bm, coll, material("mane", rough=0.85))
    remesh_smooth(0.009, 10, 700)(ob)
    return ob


def eyes(coll):
    """Big friendly eyes with a catch light."""
    bm = bmesh.new()
    for sx in (-1, 1):
        ellipsoid(bm, (sx * 0.128, -0.765, 1.225), (0.026, 0.05, 0.058), subdiv=2)
    for sx in (-1, 1):
        ellipsoid(bm, (sx * 0.05, -0.952, 1.06), (0.011, 0.007, 0.016), subdiv=2)     # nostrils
    ob = to_object("HorseEyes", bm, coll, material("eye", rough=0.15))
    bm = bmesh.new()
    for sx in (-1, 1):
        ellipsoid(bm, (sx * 0.146, -0.79, 1.25), (0.009, 0.014, 0.014), subdiv=1)
        ellipsoid(bm, (sx * 0.15, -0.775, 1.205), (0.006, 0.007, 0.007), subdiv=1)
    shine = to_object("HorseEyeShine", bm, coll, material("shine", rough=0.2, emit=0.6))
    return ob, shine


def wrapped(name, coll, mat, build, offset, thickness, target, bevel=0.0):
    bm = bmesh.new()
    build(bm)
    ob = to_object(name, bm, coll, mat)

    def setup(o):
        sw = o.modifiers.new("Wrap", "SHRINKWRAP")
        sw.target, sw.wrap_method, sw.offset = target, "NEAREST_SURFACEPOINT", offset
        so = o.modifiers.new("Thick", "SOLIDIFY")
        so.thickness, so.offset = thickness, 1.0
        if bevel:
            bv = o.modifiers.new("Bevel", "BEVEL")
            bv.width, bv.segments, bv.limit_method = bevel, 2, "ANGLE"
    return bake(ob, setup)


def tack(coll, target):
    parts = []
    parts.append(wrapped("HorseTrim", coll, material("gold", rough=0.35, metal=0.6),
                         lambda bm: arch(bm, -1.26, 1.26, -0.29, 0.27, 0.27, 0.70, 18, 12), 0.004, 0.008, target))
    parts.append(wrapped("HorseBlanket", coll, material("blanket", rough=0.9),
                         lambda bm: arch(bm, -1.2, 1.2, -0.27, 0.25, 0.27, 0.70, 18, 12), 0.009, 0.012, target))
    parts.append(wrapped("HorseSaddle", coll, material("leather", rough=0.55),
                         lambda bm: arch(bm, -0.55, 0.55, -0.15, 0.15, 0.27, 0.70, 14, 10), 0.024, 0.04, target, 0.008))
    for sx in (-1, 1):
        parts.append(wrapped("HorseFender" + ("L" if sx > 0 else "R"), coll, material("leather_dark", rough=0.6),
                             lambda bm, sx=sx: arch(bm, *sorted((sx * 0.85, sx * 1.45)), -0.07, 0.07, 0.27, 0.70, 6, 6), 0.018, 0.012, target))
    for sx in (-1, 1):
        parts.append(wrapped("HorseSkirt" + ("L" if sx > 0 else "R"), coll, material("leather_dark", rough=0.6),
                             lambda bm, sx=sx: arch(bm, *sorted((sx * 0.55, sx * 1.0)), -0.12, 0.12, 0.27, 0.70, 8, 8), 0.022, 0.012, target))
    bm = bmesh.new()
    ellipsoid(bm, (0, -0.155, 0.985), (0.075, 0.05, 0.05), subdiv=2)     # pommel
    ellipsoid(bm, (0, 0.145, 0.995), (0.13, 0.035, 0.055), Matrix.Rotation(-0.35, 3, "X"), subdiv=2)  # cantle
    parts.append(to_object("HorseSaddleRims", bm, coll, material("leather", rough=0.55)))
    strap, gold = material("strap", rough=0.6), material("gold", rough=0.35, metal=0.6)
    # Straps that ride on the body: stirrup leathers, girth, breast collar.
    bm = bmesh.new()
    for sx in (-1, 1):
        tube(bm, (sx * 0.25, -0.02, 0.95), (sx * 0.285, -0.02, 0.645), 0.012, 0.012, segs=6)
    ring(bm, (0, -0.10, 0.70), 1.0, 0.017, (0, 1, 0), scale=(0.247, 0.245, 1), segs=(40, 6))
    path_tube(bm, [(-0.2, -0.24, 0.92), (-0.13, -0.47, 0.80), (0, -0.54, 0.76), (0.13, -0.47, 0.80), (0.2, -0.24, 0.92)], 0.012)
    parts.append(to_object("HorseBodyStraps", bm, coll, strap))
    bm = bmesh.new()
    for sx in (-1, 1):
        # Stirrup iron: a rounded trapezoid hanging from the leather.
        x = sx * 0.29
        path_tube(bm, [(x, -0.02, 0.645), (x, 0.025, 0.61), (x, 0.045, 0.545), (x, -0.085, 0.545),
                       (x, -0.065, 0.61), (x, -0.02, 0.645)], 0.01)
    ring(bm, (0, -0.555, 0.76), 0.03, 0.008, (0, 1, 0), segs=(16, 5))
    parts.append(to_object("HorseStirrups", bm, coll, gold))
    # Bridle on the head: cheek straps, browband, noseband, bit rings.
    bm = bmesh.new()
    for sx in (-1, 1):
        tube(bm, (sx * 0.12, -0.80, 1.10), (sx * 0.10, -0.64, 1.36), 0.009, 0.009, segs=6)
    tube(bm, (-0.105, -0.70, 1.34), (0.105, -0.70, 1.34), 0.009, 0.009, segs=6)
    ring(bm, (0, -0.84, 1.05), 0.118, 0.011, (0, -0.71, -0.71), segs=(28, 6))
    parts.append(to_object("HorseBridle", bm, coll, strap))
    bm = bmesh.new()
    for sx in (-1, 1):
        ring(bm, (sx * 0.115, -0.88, 1.0), 0.022, 0.006, (1, 0, 0), segs=(14, 5))
    parts.append(to_object("HorseBitRings", bm, coll, gold))
    # Reins run from the bit to the withers, so they bend with the neck (skinned, not rigid).
    bm = bmesh.new()
    for sx in (-1, 1):
        path_tube(bm, [(sx * 0.115, -0.88, 1.0), (sx * 0.15, -0.72, 0.86), (sx * 0.16, -0.52, 0.86), (sx * 0.13, -0.36, 0.98)], 0.008)
    parts.append(to_object("HorseReins", bm, coll, strap))
    return parts


# ---------------------------------------------------------------- textures: unwrap and bake

TEX_DIR = os.path.join(OUT, "textures")
# Which painted detail texture each material gets, and how many times it repeats per metre.
DETAIL = {"body": ("tex-fur.png", 3.0), "mane": ("tex-hair.png", 3.0), "leather": ("tex-leather.png", 4.0),
          "leather_dark": ("tex-leather.png", 4.0), "strap": ("tex-leather.png", 6.0), "blanket": ("tex-blanket.png", 5.0)}


def join(names, new_name):
    obs = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
    target = obs[0]
    with bpy.context.temp_override(active_object=target, object=target, selected_objects=obs, selected_editable_objects=obs):
        bpy.ops.object.join()
    target.name = new_name
    return target


def view3d_override():
    win = bpy.context.window
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return {"window": win, "area": area, "region": region}


def unwrap(ob, margin=0.008):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(**view3d_override(), active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin)
        bpy.ops.object.mode_set(mode="OBJECT")


def bake_tree(mat, key, image):
    """Emission-only graph: base colour x detail texture x occlusion x a soft top light. Baking EMIT records it as is."""
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new("ShaderNodeOutputMaterial")
    emit = N.new("ShaderNodeEmission")
    L.new(emit.outputs[0], out.inputs["Surface"])

    def mul(a, b):
        m = N.new("ShaderNodeVectorMath")
        m.operation = "MULTIPLY"
        L.new(a, m.inputs[0])
        L.new(b, m.inputs[1])
        return m.outputs[0]

    if key == "body":
        vc = N.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        color = vc.outputs["Color"]
    else:
        rgb = N.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (*linear(COLORS[key]), 1)
        color = rgb.outputs[0]
    if key in DETAIL and os.path.exists(os.path.join(TEX_DIR, DETAIL[key][0])):
        name, per_metre = DETAIL[key]
        tex = N.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(TEX_DIR, name), check_existing=True)
        tex.projection, tex.projection_blend = "BOX", 0.3
        coord, mapping = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (per_metre,) * 3
        L.new(coord.outputs["Object"], mapping.inputs["Vector"])
        L.new(mapping.outputs[0], tex.inputs["Vector"])
        # Keep the base colour and borrow only the texture's light and dark strokes.
        bw, rng = N.new("ShaderNodeRGBToBW"), N.new("ShaderNodeMapRange")
        L.new(tex.outputs["Color"], bw.inputs[0])
        L.new(bw.outputs[0], rng.inputs["Value"])
        rng.inputs["From Min"].default_value, rng.inputs["From Max"].default_value = 0.05, 0.6
        rng.inputs["To Min"].default_value, rng.inputs["To Max"].default_value = 0.87, 1.13
        color = mul(color, rng.outputs[0])
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.12
    shade = N.new("ShaderNodeMapRange")
    L.new(ao.outputs["AO"], shade.inputs["Value"])
    shade.inputs["To Min"].default_value = 0.55
    color = mul(color, shade.outputs[0])
    geo, sep, top = N.new("ShaderNodeNewGeometry"), N.new("ShaderNodeSeparateXYZ"), N.new("ShaderNodeMapRange")
    L.new(geo.outputs["Normal"], sep.inputs[0])
    L.new(sep.outputs["Z"], top.inputs["Value"])
    top.inputs["From Min"].default_value, top.inputs["From Max"].default_value = -1.0, 1.0
    top.inputs["To Min"].default_value, top.inputs["To Max"].default_value = 0.86, 1.08
    color = mul(color, top.outputs[0])
    L.new(color, emit.inputs["Color"])
    target = N.new("ShaderNodeTexImage")
    target.image = image
    N.active = target


def final_material(name, image, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out, bsdf, tex = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeBsdfPrincipled"), nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return m


ROUGH = {"body": 0.8, "mane": 0.85, "leather": 0.55, "leather_dark": 0.6, "strap": 0.6, "blanket": 0.9, "gold": 0.35}


def bake_object(sc, ob, file_name, size):
    """Bakes every material on ob into one image, then swaps in plain textured materials for export."""
    image = bpy.data.images.get(file_name) or bpy.data.images.new(file_name, size, size, alpha=False)
    if tuple(image.size) != (size, size):
        image.scale(size, size)
    keys = []
    for slot in ob.material_slots:
        key = slot.material.name.removeprefix("GMH_").split(".")[0]
        keys.append(key)
        bake_mat = slot.material.copy()
        bake_mat.name = "GMH_bake_" + key
        bake_tree(bake_mat, key, image)
        slot.material = bake_mat
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.bake(type="EMIT", margin=6, use_clear=True)
    image.filepath_raw = os.path.join(OUT, file_name)
    image.file_format = "PNG"
    image.save()
    for slot, key in zip(ob.material_slots, keys):
        baked = slot.material
        slot.material = final_material(f"GMH_{ob.name}_{key}", image, ROUGH.get(key, 0.7), 0.6 if key == "gold" else 0.0)
        bpy.data.materials.remove(baked)


def texture(sc, coll):
    join(["HorseTrim", "HorseBlanket", "HorseSaddle", "HorseFenderL", "HorseFenderR", "HorseSkirtL", "HorseSkirtR",
          "HorseSaddleRims", "HorseBodyStraps", "HorseStirrups"], "HorseTack")
    join(["HorseBridle", "HorseBitRings"], "HorseHeadGear")
    previous = sc.render.engine
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 24
    plan = [("HorseBody", "horse-body.png", 2048), ("HorseMane", "horse-mane.png", 1024), ("HorseTail", "horse-tail.png", 1024),
            ("HorseTack", "horse-tack.png", 1024), ("HorseHeadGear", "horse-headgear.png", 512)]
    for name, file_name, size in plan:
        ob = bpy.data.objects[name]
        unwrap(ob)
        bake_object(sc, ob, file_name, size)
    try:
        sc.render.engine = previous
    except TypeError:
        pass


# ---------------------------------------------------------------- rig and animation

BONES = [  # name, head, tail, parent
    ("root", (0, 0, 0), (0, 0.25, 0), None),
    ("pelvis", (0, 0.30, 0.80), (0, 0.05, 0.82), "root"),
    ("spine", (0, 0.05, 0.82), (0, -0.25, 0.84), "pelvis"),
    ("chest", (0, -0.25, 0.84), (0, -0.40, 0.92), "spine"),
    ("neck1", (0, -0.40, 0.92), (0, -0.48, 1.12), "chest"),
    ("neck2", (0, -0.48, 1.12), (0, -0.58, 1.30), "neck1"),
    ("head", (0, -0.58, 1.30), (0, -0.88, 1.10), "neck2"),
    ("ear.L", (0.075, -0.64, 1.32), (0.095, -0.655, 1.47), "head"),
    ("ear.R", (-0.075, -0.64, 1.32), (-0.095, -0.655, 1.47), "head"),
    ("tail1", (0, 0.53, 0.92), (0, 0.63, 0.77), "pelvis"),
    ("tail2", (0, 0.63, 0.77), (0, 0.71, 0.55), "tail1"),
    ("tail3", (0, 0.71, 0.55), (0, 0.74, 0.25), "tail2"),
]
for _sx, _s in ((1, "L"), (-1, "R")):
    _x = 0.135 * _sx
    BONES += [
        ("leg_upper.F" + _s, (_x, -0.33, 0.66), (_x, -0.33, 0.31), "chest"),
        ("leg_lower.F" + _s, (_x, -0.33, 0.31), (_x, -0.335, 0.105), "leg_upper.F" + _s),
        ("hoof.F" + _s, (_x, -0.335, 0.105), (_x, -0.34, 0.0), "leg_lower.F" + _s),
        ("leg_upper.B" + _s, (_x, 0.31, 0.68), (_x, 0.37, 0.31), "pelvis"),
        ("leg_lower.B" + _s, (_x, 0.37, 0.31), (_x, 0.35, 0.105), "leg_upper.B" + _s),
        ("hoof.B" + _s, (_x, 0.35, 0.105), (_x, 0.345, 0.0), "leg_lower.B" + _s),
    ]


def armature(coll):
    arm = bpy.data.armatures.new("gmh_HorseRig")
    ob = bpy.data.objects.new("HorseRig", arm)
    coll.objects.link(ob)
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode="EDIT")
        made = {}
        for name, head, tail_, parent in BONES:
            b = arm.edit_bones.new(name)
            b.head, b.tail = head, tail_
            b.roll = 0.0
            if parent:
                b.parent = made[parent]
                b.use_connect = False
            made[name] = b
        arm.edit_bones["root"].use_deform = False
        bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "XYZ"
    return ob


def skin(rig, body_ob, soft, rigid):
    """Automatic weights for the body (and other soft parts); tack and eyes ride rigidly on one bone."""
    for ob in [body_ob] + soft:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        with bpy.context.temp_override(active_object=rig, object=rig, selected_objects=[ob, rig],
                                       selected_editable_objects=[ob, rig]):
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for ob, bone in rigid:
        mw = ob.matrix_world.copy()
        ob.parent = rig
        ob.parent_type = "BONE"
        ob.parent_bone = bone
        ob.matrix_world = mw


def key_action(rig, name, frames, pose_at):
    """Keys `frames` frames of pose_at(t in 0..1) -> {bone: (rx, ry, rz)} and stores the action on an NLA track."""
    ad = rig.animation_data or rig.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ad.action = act
    for f in range(frames + 1):
        pose = pose_at(f / frames)
        for pb in rig.pose.bones:
            pb.rotation_euler = pose.get(pb.name, (0.0, 0.0, 0.0))
            pb.keyframe_insert("rotation_euler", frame=f + 1)
        root = rig.pose.bones["root"]
        root.location = (0.0, 0.0, pose.get("_bob", 0.0))
        root.keyframe_insert("location", frame=f + 1)
    track = ad.nla_tracks.new()
    track.name = name
    track.strips.new(name, 1, act)
    ad.action = None
    return act


def stride(u, contact, stance, reach, push):
    """Upper-leg angle over a stride. Positive swings the leg back. On the ground (the first `stance` of the
    cycle after `contact`) the leg sweeps steadily from `reach` (forward) to `push` (back); in the air it
    eases back forward. Also returns how folded the leg is (0 planted .. 1 mid-swing)."""
    p = (u - contact) % 1.0
    if p < stance:
        return reach + (push - reach) * (p / stance), 0.0
    t = (p - stance) / (1.0 - stance)
    e = 0.5 - 0.5 * math.cos(math.pi * t)
    return push + (reach - push) * e, math.sin(math.pi * t) ** 1.3


def gait(u, contacts, stance, front_reach, front_push, hind_reach, hind_push, fold):
    """Leg poses for a gait from each leg's contact time; knees fold back, hocks fold forward in the air."""
    pose = {}
    for leg, contact in contacts.items():
        front = ".F" in leg
        angle, f = stride(u, contact, stance, *((front_reach, front_push) if front else (hind_reach, hind_push)))
        pose["leg_upper" + leg] = (angle, 0, 0)
        pose["leg_lower" + leg] = ((1.25 if front else -1.15) * fold * f, 0, 0)
        pose["hoof" + leg] = ((0.7 if front else 0.6) * fold * f, 0, 0)
    return pose


def legs_cycle(t, amp, offsets, lift):
    pose = {}
    for leg, off in offsets.items():
        a = math.tau * (t + off)
        swing = math.sin(a) * amp
        bend = max(0.0, math.sin(a + 1.2)) * lift            # fold the lower leg while it travels forward
        front = ".F" in leg
        pose["leg_upper" + leg] = (swing, 0, 0)
        pose["leg_lower" + leg] = (-bend if front else bend, 0, 0)
        pose["hoof" + leg] = (bend * 0.5 if front else -bend * 0.5, 0, 0)
    return pose


def animate(rig):
    bpy.context.scene.render.fps = FPS

    def idle(t):
        a = math.tau * t
        return {"chest": (0.02 * math.sin(a), 0, 0), "neck1": (0.04 * math.sin(a + 0.6), 0, 0), "head": (0.05 * math.sin(a), 0, 0.03 * math.sin(a * 2)),
                "tail1": (0.15, 0, 0.25 * math.sin(a)), "tail2": (0.05, 0, 0.3 * math.sin(a - 0.7)), "tail3": (0, 0, 0.3 * math.sin(a - 1.4)),
                "ear.L": (0, 0, 0.25 * max(0, math.sin(a * 3))), "ear.R": (0, 0, -0.1 * math.sin(a))}

    def graze(t):
        a = math.tau * t
        chew = 0.05 * math.sin(a * 6)
        return {"neck1": (0.85, 0, 0), "neck2": (0.45, 0, 0), "head": (0.55 + chew, 0, 0),
                "leg_upper.FL": (0.12, 0, 0), "leg_upper.FR": (-0.06, 0, 0),
                "tail1": (0.12, 0, 0.2 * math.sin(a)), "tail2": (0, 0, 0.25 * math.sin(a - 0.7)), "tail3": (0, 0, 0.25 * math.sin(a - 1.4))}

    def walk(t):
        # Four-beat walk: hind left, front left, hind right, front right; three hooves down most of the time.
        p = gait(t, {".BL": 0.0, ".FL": 0.25, ".BR": 0.5, ".FR": 0.75}, 0.6, -0.4, 0.32, -0.36, 0.4, 0.85)
        a = math.tau * t
        # Head nods down as each front hoof lands (twice a stride); hips and shoulders roll opposite ways
        # with the hind and front legs; the body dips as weight shifts onto a single diagonal.
        nod = math.cos(2 * a - math.tau * 0.5 - 0.6)
        p.update({"neck1": (0.09 * nod, 0, 0), "neck2": (0.04 * nod, 0, 0), "head": (-0.06 * nod, 0, 0.04 * math.sin(a)),
                  "pelvis": (0.02 * math.sin(2 * a), 0.06 * math.sin(a), 0), "chest": (0, -0.05 * math.sin(a + 1.6), 0.03 * math.sin(a + 1.6)),
                  "ear.L": (0.1 * math.sin(a), 0, 0), "ear.R": (-0.1 * math.sin(a), 0, 0),
                  "tail1": (0.18, 0, 0.16 * math.sin(a)), "tail2": (0.04, 0, 0.18 * math.sin(a - 0.7)), "tail3": (0, 0, 0.2 * math.sin(a - 1.4)),
                  "_bob": 0.018 * math.cos(2 * a)})
        return p

    def gallop(t):
        # Transverse gallop: hind left, hind right, front left, front right, then all four tuck up in the air.
        p = gait(t, {".BL": 0.0, ".BR": 0.09, ".FL": 0.3, ".FR": 0.39}, 0.3, -0.9, 0.55, -0.7, 0.75, 1.0)
        a = math.tau * t
        # The rump rises as the hinds push, the chest rises as the fronts push off, then the body sails.
        pitch = 0.11 * math.sin(a - 0.6)
        p.update({"pelvis": (pitch, 0, 0), "spine": (-0.06 * math.sin(a - 0.2), 0, 0), "chest": (-0.07 * math.sin(a + 0.3), 0, 0),
                  "neck1": (-0.2 + 0.22 * math.sin(a - 1.9), 0, 0), "neck2": (0.1 * math.sin(a - 2.3), 0, 0), "head": (0.12 * math.sin(a - 2.6), 0, 0),
                  "ear.L": (0.35, 0, 0), "ear.R": (0.35, 0, 0),
                  "tail1": (0.55 + 0.12 * math.sin(a - 0.8), 0, 0.05 * math.sin(a)),
                  "tail2": (0.2 + 0.15 * math.sin(a - 1.4), 0, 0.07 * math.sin(a - 0.6)),
                  "tail3": (0.1 + 0.15 * math.sin(a - 2.0), 0, 0.08 * math.sin(a - 1.2)),
                  "_bob": 0.06 * math.sin(a - 2.1) + 0.02})
        return p

    key_action(rig, "Idle", 60, idle)
    key_action(rig, "Graze", 90, graze)
    key_action(rig, "Walk", 32, walk)
    key_action(rig, "Gallop", 18, gallop)


# ---------------------------------------------------------------- scene, preview, export

def fresh_scene():
    old = bpy.data.scenes.get(SCENE)
    if old is not None:
        if bpy.context.window.scene == old:
            bpy.context.window.scene = next(s for s in bpy.data.scenes if s != old)
        for ob in list(old.collection.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        for c in list(old.collection.children_recursive):
            bpy.data.collections.remove(c)
        bpy.data.scenes.remove(old)
    for data in (bpy.data.meshes, bpy.data.armatures):
        for block in list(data):
            if block.users == 0 and block.name.startswith("gmh_"):
                data.remove(block)
    for act in list(bpy.data.actions):
        if act.name in ("Idle", "Graze", "Walk", "Gallop") or act.name.startswith(("Idle.", "Graze.", "Walk.", "Gallop.")):
            bpy.data.actions.remove(act)
    sc = bpy.data.scenes.new(SCENE)
    bpy.context.window.scene = sc
    coll = bpy.data.collections.new("Horse")
    sc.collection.children.link(coll)
    return sc, coll


def preview_setup(sc):
    world = bpy.data.worlds.get("GMH_World") or bpy.data.worlds.new("GMH_World")
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.62, 0.64, 0.68, 1)
    bg.inputs[1].default_value = 1.0
    sc.world = world
    sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("GMH_Sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(140))
    sc.collection.objects.link(sun)
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = engine
            break
        except TypeError:
            continue
    sc.view_settings.view_transform = "Standard"

    def cam(name, loc, rot, ortho=None):
        c = bpy.data.cameras.new("GMH_" + name)
        if ortho:
            c.type, c.ortho_scale = "ORTHO", ortho
        ob = bpy.data.objects.new(name, c)
        ob.location, ob.rotation_euler = loc, rot
        sc.collection.objects.link(ob)
        return ob

    cams = {
        "side": cam("CamSide", (4, 0.0, 0.78), (math.radians(90), 0, math.radians(90)), 1.95),
        "front": cam("CamFront", (0, -4, 0.75), (math.radians(90), 0, 0), 1.6),
        "back": cam("CamBack", (0, 4, 0.75), (math.radians(90), 0, math.radians(180)), 1.6),
        "three_quarter": cam("Cam34", (2.6, -2.6, 1.6), (math.radians(68), 0, math.radians(45))),
    }
    cams["three_quarter"].data.lens = 50
    return cams


def preview(sc, cams):
    """Renders the rest pose: the NLA tracks are muted while rendering so no action bends the horse."""
    os.makedirs(OUT, exist_ok=True)
    rig = bpy.data.objects.get("HorseRig")
    tracks = list(rig.animation_data.nla_tracks) if rig and rig.animation_data else []
    for tr in tracks:
        tr.mute = True
    if rig:
        for pb in rig.pose.bones:   # keying leaves the last pose behind; go back to rest
            pb.rotation_euler = (0, 0, 0)
            pb.location = (0, 0, 0)
    sc.frame_set(1)
    sizes = {"side": (900, 800), "front": (640, 800), "back": (640, 800), "three_quarter": (800, 800)}
    for name, ob in cams.items():
        sc.camera = ob
        sc.render.resolution_x, sc.render.resolution_y = sizes[name]
        sc.render.filepath = os.path.join(OUT, f"preview-{name}.png")
        bpy.ops.render.render(write_still=True, scene=sc.name)
    for tr in tracks:
        tr.mute = False


def export(sc, rig):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    keep = [rig] + [c for c in rig.children_recursive if c.type == "MESH"]
    for o in keep:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "horse.glb"), export_format="GLB", use_selection=True,
                              use_active_scene=True, export_apply=False, export_skins=True, export_animations=True,
                              export_animation_mode="NLA_TRACKS", export_vertex_color="MATERIAL", export_yup=True)
    bpy.data.libraries.write(os.path.join(OUT, "horse.blend"), {sc}, fake_user=True, compress=True)


def build(steps):
    _mats.clear()
    result = {}
    if "model" in steps:
        sc, coll = fresh_scene()
        body_ob = body(coll)
        mane_ob, tail_ob = mane(coll), tail(coll)
        eye_ob, shine_ob = eyes(coll)
        tack_obs = tack(coll, body_ob)
        result["faces"] = {o.name: len(o.data.polygons) for o in coll.objects if o.type == "MESH"}
    sc = bpy.data.scenes[SCENE]
    coll = bpy.data.collections["Horse"]
    if "texture" in steps:
        texture(sc, coll)
    if "rig" in steps:
        rig = armature(coll)
        names = {o.name: o for o in coll.objects}
        soft = [names["HorseMane"], names["HorseTail"], names["HorseReins"]]
        head_parts = ("HorseEyes", "HorseEyeShine", "HorseHeadGear", "HorseBridle", "HorseBitRings")
        rigid = [(names[n], "head") for n in head_parts if n in names]
        rigid += [(names[n], "spine") for n in names
                  if n.startswith(("HorseTack", "HorseTrim", "HorseBlanket", "HorseSaddle", "HorseSkirt", "HorseFender", "HorseBodyStraps", "HorseStirrups"))]
        skin(rig, names["HorseBody"], soft, rigid)
        animate(rig)
        result["groups"] = len(names["HorseBody"].vertex_groups)
    if "preview" in steps:
        cams = preview_setup(sc)
        preview(sc, cams)
    if "export" in steps:
        export(sc, bpy.data.objects["HorseRig"])
    return result


result = build(set(globals().get("STEPS", ["model", "texture", "rig", "preview", "export"])))
print("GM Horse:", result)

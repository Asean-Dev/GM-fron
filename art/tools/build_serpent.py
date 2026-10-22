"""Builds the adult Abyssal Lantern Serpent (art/models/serpent/parts-lantern-adult-v1.png) as a game mount.

The body and the saddle come from Hyper3D (single 3/4 images render-body-lantern-v1.png and
render-saddle-lantern-v1.png); the two lantern antennae are modelled here, so their glass and glow are real
materials. The antennae and the saddle stay separate meshes, as the parts sheet asks.

Run inside Blender with p pointing at this file in your clone:
    p = "/path/to/GM-fron/art/tools/build_serpent.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_serpent", "__file__": p, "STEPS": ["antennae"]})
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "models", "serpent", "generated"))
SCENE = "GM Serpent"
STEPS = globals().get("STEPS", ["antennae"])

# Antenna stalk centre line in its own frame: base at the origin, rising, arcing forward (-Y) and drooping, so the
# lantern hangs from the tip. Metres; the lantern then hangs about level with the brow.
STALK = [(0.0, 0.0, 0.0), (0.0, 0.03, 0.17), (0.0, 0.0, 0.36), (0.0, -0.1, 0.46), (0.0, -0.21, 0.45), (0.0, -0.26, 0.39), (0.0, -0.27, 0.34)]
STALK_RADIUS = (0.024, 0.011)          # base, tip
LANTERN_RADIUS, LANTERN_HEIGHT = 0.075, 0.17


def scene():
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    bpy.context.window.scene = sc
    return sc


def material(name, color, roughness=0.5, emission=None, strength=0.0, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Alpha"].default_value = alpha
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
    return m


def catmull(points, samples):
    """Smooth curve through points (Catmull-Rom), `samples` points from first to last."""
    pts = [Vector(p) for p in points]
    pts = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for k in range(samples):
        t = k / (samples - 1) * (len(pts) - 3)
        i = min(int(t), len(pts) - 4)
        u = t - i
        p0, p1, p2, p3 = pts[i:i + 4]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    return out


def tube(bm, path, r0, r1, sides=10, cap=True):
    """A tapering tube along path into bm; returns the rings of verts."""
    rings, prev_n = [], None
    for k, p in enumerate(path):
        tangent = (path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]).normalized()
        # Parallel transport of the ring frame keeps the tube from twisting.
        n = prev_n if prev_n is not None else tangent.orthogonal().normalized()
        n = (n - tangent * n.dot(tangent)).normalized()
        b = tangent.cross(n)
        prev_n = n
        r = r0 + (r1 - r0) * k / (len(path) - 1)
        rings.append([bm.verts.new(p + (n * math.cos(a) + b * math.sin(a)) * r)
                      for a in (math.tau * s / sides for s in range(sides))])
    for a, b in zip(rings, rings[1:]):
        for s in range(sides):
            bm.faces.new((a[s], a[(s + 1) % sides], b[(s + 1) % sides], b[s]))
    if cap:
        bm.faces.new(rings[-1])
        bm.faces.new(list(reversed(rings[0])))
    return rings


def build_antenna(name, side, aged=False):
    """One antenna (stalk, cap, ribbed glass lantern, glowing core, light tendrils) as one object with a material
    per part, in its own frame (base at the origin). side +1 / -1 leans the tip outward; aged gives the elder's
    old sea-glass lanterns (greener glass, warmer light). Returns the object and the stalk joints for bones."""
    path_pts = [Vector((x + side * 0.08 * (z / 0.42), y, z)) for x, y, z in STALK]
    path = catmull(path_pts, 28)
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    if aged:
        mats = [material("gms_stalk_old", (0.02, 0.03, 0.08), 0.5),
                material("gms_glass_old", (0.55, 0.85, 0.72), 0.25, (0.45, 0.8, 0.6), 0.8, alpha=0.7),
                material("gms_core_old", (1.0, 0.72, 0.35), 0.4, (1.0, 0.65, 0.28), 3.4),
                material("gms_tendril_old", (1.0, 0.7, 0.38), 0.4, (1.0, 0.62, 0.28), 1.6, alpha=0.65)]
    else:
        mats = [material("gms_stalk", (0.03, 0.05, 0.16), 0.35),
                material("gms_glass", (0.35, 0.7, 1.0), 0.05, (0.3, 0.7, 1.0), 1.2, alpha=0.6),
                material("gms_core", (1.0, 0.8, 0.4), 0.4, (1.0, 0.75, 0.35), 3.0),
                material("gms_tendril", (1.0, 0.75, 0.4), 0.4, (1.0, 0.7, 0.3), 1.5, alpha=0.65)]
    for m in mats:
        me.materials.append(m)
    bm = bmesh.new()
    seen = set()

    def take(index):
        # Give the faces added since the last call this material.
        for f in bm.faces:
            if f not in seen:
                f.material_index = index
                seen.add(f)

    tube(bm, path, *STALK_RADIUS)
    take(0)
    tip = path[-1]
    # A small dark cap where the lantern hangs.
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.03, radius2=0.018, depth=0.03,
                                matrix=Matrix.Translation(tip + Vector((0, 0, -0.012))))
    take(0)
    # Glass bulb: a sphere stretched tall with soft vertical ribs, like a jellyfish bell.
    centre = tip + Vector((0, 0, -0.03 - LANTERN_HEIGHT / 2))
    bulb = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1.0)
    for v in bulb["verts"]:
        a = math.atan2(v.co.y, v.co.x)
        rib = 1 + 0.07 * math.cos(8 * a) * (1 - abs(v.co.z))
        bell = 1 + 0.25 * min(v.co.z, 0.0)          # narrower toward the bottom
        r = LANTERN_RADIUS * rib * bell
        v.co = centre + Vector((v.co.x * r, v.co.y * r, v.co.z * LANTERN_HEIGHT / 2))
    take(1)
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=LANTERN_RADIUS * 0.45, matrix=Matrix.Translation(centre))
    take(2)
    # Three wavy light tendrils trailing from the bottom of the bulb.
    bottom = centre + Vector((0, 0, -LANTERN_HEIGHT / 2 + 0.01))
    for i in range(3):
        a = math.tau * i / 3 + 0.4
        start = bottom + Vector((math.cos(a), math.sin(a), 0)) * 0.025
        pts = [start + Vector((math.cos(a) * 0.012 * k + 0.012 * math.sin(k * 1.7 + i), math.sin(a) * 0.012 * k, -0.035 * k)) for k in range(6)]
        tube(bm, catmull(pts, 14), 0.006, 0.0015, sides=6)
        take(3)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    joints = [path[0], path[len(path) // 3], path[2 * len(path) // 3], path[-1]]
    return ob, joints


def step_antennae(sc):
    for name in ("SerpentAntenna.L", "SerpentAntenna.R"):
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
    made = []
    for side, tag in ((1, "L"), (-1, "R")):
        ob, joints = build_antenna("SerpentAntenna." + tag, side)
        sc.collection.objects.link(ob)
        ob.location.x = side * 0.09
        made.append((ob.name, [tuple(round(c, 3) for c in j) for j in joints]))
    return made


def run():
    sc = scene()
    result = {}
    if "antennae" in STEPS:
        result["antennae"] = step_antennae(sc)
    return result


if globals().get("RUN", True):
    print("GM serpent:", run())

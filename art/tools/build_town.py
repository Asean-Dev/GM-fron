"""Starter-town blockout for GM, built from art/concepts/concept-town-a.png.

Run inside Blender (Blender MCP, or the Text Editor):
    p = "/Users/asean/Desktop/GM-fron/art/tools/build_town.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_town"})

Builds into its own scene "GM Town" and leaves every other scene alone; rerunning rebuilds it.
1 Blender unit = 1 server grid cell: cell (x, y) is Blender (x, y), on map-server's 100x100 map.
Also writes art/maps/town/walkable.txt, the grid the server will use for pathfinding.
"""

import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

MAP = 100
CENTER = Vector((50.0, 50.0))
PLAZA_R = 10.0
RING_R = 19.0
WALL_R = 40.0
GATE_HALF = 3.0
RIVER_W = 5.0
SEED = 7
SCENE = "GM Town"
OUT_DIR = "/Users/asean/Desktop/GM-fron/art/maps/town"

# Walkability grid kinds: . = , walkable; # ~ blocked.
FREE, ROAD, FIELD, BUILT, WATER = ".", "=", ",", "#", "~"

PALETTE = {
    "grass_a": "#74c447", "grass_b": "#9fd45a", "grass_root": "#4f9a3a", "grass_tip": "#c8ee7c",
    "grass_cool": "#d9f0e6", "grass_warm": "#fff7cf",
    "cobble_a": "#e2d2b4", "cobble_b": "#97876f",
    "plaza_a": "#ecdcbd", "plaza_b": "#9c8b75",
    "dirt_a": "#d2ad72", "dirt_b": "#b38c55",
    "plaster": "#f5e8cb", "wood": "#7d4f33", "stone": "#c4bba9", "stone_dark": "#8b8478",
    "roof_red": "#d4552e", "roof_orange": "#ea8b38", "roof_blue": "#2e5ec0", "slate": "#59647a",
    "door": "#5a3826", "window": "#ffd27a",
    "water": "#36a8e6", "bank": "#a8a296",
    "crystal": "#1f8fff", "shutter_1": "#2e8f86", "shutter_2": "#3a63b8", "shutter_3": "#6f9a35", "banner": "#1f4fb0", "gold": "#eab53b", "fire": "#ff8a2a",
    "awning_1": "#26b3a2", "awning_2": "#f2c339", "awning_3": "#e8633b", "cloth": "#fff4de",
    "trunk": "#7a5135", "leaf_1": "#4ea343", "leaf_2": "#6dbf4b", "leaf_3": "#3c8b3d",
    "leaf_autumn": "#e8953a", "pine": "#2d7a4b",
    "wheat": "#ebc75b", "soil": "#9a6a42",
    "flower_1": "#ff78a8", "flower_2": "#ffd84a", "flower_3": "#ff5a5a",
    "skin": "#ffd9b8", "hair": "#4a2f22", "eye": "#1d1d26", "lantern": "#ffcf70",
    "slime_1": "#62c6ff", "slime_2": "#ff8fb8", "slime_3": "#93e05e",
    "cloth_1": "#d94a4a", "cloth_2": "#3d6fd9", "cloth_3": "#3fb36b", "cloth_4": "#8f5bd9",
}

for _k in ("roof_red", "roof_orange", "roof_blue", "slate"):
    _h = PALETTE[_k].lstrip("#")
    PALETTE[_k + "_dk"] = "#" + "".join("%02x" % int(int(_h[i:i + 2], 16) * 0.8) for i in (0, 2, 4))

rnd = random.uniform
# Flat shapes that grass must not grow through: ("rect", c, w, d, rot) / ("circle", c, r) / ("path", pts, width, closed)
grass_blockers = []
grid = [[FREE] * MAP for _ in range(MAP)]


# ---------------------------------------------------------------- helpers

def dirv(t):
    return Vector((math.cos(t), math.sin(t)))


def facing(front):
    """Z rotation that turns a model's front (local -Y) toward `front`."""
    return math.atan2(front.x, -front.y)


def river_x(y):
    return 81.0 + 2.2 * math.sin(y * 0.09) + 1.0 * math.sin(y * 0.23)


def linear(hex_color):
    h = hex_color.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def rgba(key):
    return (*linear(PALETTE[key]), 1.0)


def dist_to_segment(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared == 0 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def catmull(points, closed=False, per_seg=6):
    pts = [Vector(p) for p in points]
    n = len(pts)
    out = []
    for i in range(n if closed else n - 1):
        p0 = pts[(i - 1) % n] if closed else pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed else pts[min(i + 2, n - 1)]
        for k in range(per_seg):
            t = k / per_seg
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t * t * t))
    if not closed:
        out.append(pts[-1])
    return out


# ---------------------------------------------------------------- grid

def in_map(gx, gy):
    return 0 <= gx < MAP and 0 <= gy < MAP


def rect_cells(c, w, d, rot, margin=0.0):
    cs, sn = math.cos(rot), math.sin(rot)
    reach = math.hypot(w, d) / 2 + margin + 1
    for gx in range(math.floor(c.x - reach), math.ceil(c.x + reach) + 1):
        for gy in range(math.floor(c.y - reach), math.ceil(c.y + reach) + 1):
            dx, dy = gx - c.x, gy - c.y
            if abs(dx * cs + dy * sn) <= w / 2 + margin and abs(-dx * sn + dy * cs) <= d / 2 + margin:
                yield gx, gy


def rect_free(c, w, d, rot, margin=0.8, inside_wall=True):
    if inside_wall:
        m = Matrix.Rotation(rot, 2)
        for sx in (-1, 1):
            for sy in (-1, 1):
                if (c + m @ Vector((sx * w / 2, sy * d / 2)) - CENTER).length > WALL_R - 1.4:
                    return False
    return all(in_map(gx, gy) and grid[gy][gx] == FREE for gx, gy in rect_cells(c, w, d, rot, margin))


def claim(c, w, d, rot, kind=BUILT):
    grass_blockers.append(("rect", c.copy(), w, d, rot))
    for gx, gy in rect_cells(c, w, d, rot):
        if in_map(gx, gy):
            grid[gy][gx] = kind


def claim_circle(c, r, kind=BUILT):
    grass_blockers.append(("circle", c.copy(), r))
    for gx in range(math.floor(c.x - r), math.ceil(c.x + r) + 1):
        for gy in range(math.floor(c.y - r), math.ceil(c.y + r) + 1):
            if in_map(gx, gy) and (Vector((gx, gy)) - c).length <= r:
                grid[gy][gx] = kind


def mark_path(pts, width, kind, closed=False):
    grass_blockers.append(("path", pts, width + (1.6 if kind == WATER else 0.0), closed))
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed else [])
    reach = width / 2 + 0.5
    for a, b in segs:
        for gx in range(math.floor(min(a.x, b.x) - reach), math.ceil(max(a.x, b.x) + reach) + 1):
            for gy in range(math.floor(min(a.y, b.y) - reach), math.ceil(max(a.y, b.y) + reach) + 1):
                if in_map(gx, gy) and dist_to_segment(Vector((gx, gy)), a, b) <= reach:
                    grid[gy][gx] = kind


def cell_is(p, kind, ring=0):
    gx, gy = round(p.x), round(p.y)
    return all(in_map(gx + i, gy + j) and grid[gy + j][gx + i] == kind
               for i in range(-ring, ring + 1) for j in range(-ring, ring + 1))


# ---------------------------------------------------------------- materials

_mats = {}


def _fresh_tree(m):
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return nt, bsdf


def mat(key, rough=0.85, emit=0.0):
    if key not in _mats:
        m = bpy.data.materials.get("GM_" + key) or bpy.data.materials.new("GM_" + key)
        _, bsdf = _fresh_tree(m)
        bsdf.inputs["Base Color"].default_value = rgba(key)
        bsdf.inputs["Roughness"].default_value = rough
        if emit:
            bsdf.inputs["Emission Color"].default_value = rgba(key)
            bsdf.inputs["Emission Strength"].default_value = emit
        m.diffuse_color = rgba(key)
        _mats[key] = m
    return _mats[key]


def pattern_mat(name, light, dark, kind, scale):
    """Two-colour procedural material in object space: 'noise' for grass, 'cells' for cobbles."""
    if name not in _mats:
        m = bpy.data.materials.get("GM_" + name) or bpy.data.materials.new("GM_" + name)
        nt, bsdf = _fresh_tree(m)
        coord = nt.nodes.new("ShaderNodeTexCoord")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        els = ramp.color_ramp.elements
        if kind == "noise":
            tex = nt.nodes.new("ShaderNodeTexNoise")
            fac = tex.outputs["Fac"]
            els[0].position, els[0].color = 0.42, rgba(dark)
            els[1].position, els[1].color = 0.62, rgba(light)
        else:
            tex = nt.nodes.new("ShaderNodeTexVoronoi")
            fac = tex.outputs["Distance"]
            els[0].position, els[0].color = 0.0, rgba(light)
            els[1].position, els[1].color = 0.5, rgba(dark)
            mid = els.new(0.36)
            mid.color = rgba(light)
        tex.inputs["Scale"].default_value = scale
        nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
        nt.links.new(fac, ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.9
        m.diffuse_color = rgba(light)
        _mats[name] = m
    return _mats[name]


def _sock(sockets, name, kind):
    return next(s for s in sockets if s.name == name and s.type == kind and s.enabled)


def grass_mat(name, tip=None):
    """Grass colour: dark roots to light tips, big soft colour patches, and drifting cloud shadows.
    Blades read their height from the 'tip' attribute; the ground uses a fixed `tip`."""
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.get("GM_" + name) or bpy.data.materials.new("GM_" + name)
    nt, bsdf = _fresh_tree(m)
    pos = nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]

    def ramp(fac, stops):
        r = nt.nodes.new("ShaderNodeValToRGB")
        els = r.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for el, (at, col) in zip(els, stops):
            el.position, el.color = at, col
        if isinstance(fac, float):
            r.inputs["Fac"].default_value = fac
        else:
            nt.links.new(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def noise(scale, detail):
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        nt.links.new(pos, n.inputs["Vector"])
        return n.outputs["Fac"]

    def multiply(a, b):
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type, mx.blend_type = "RGBA", "MULTIPLY"
        _sock(mx.inputs, "Factor", "VALUE").default_value = 1.0
        nt.links.new(a, _sock(mx.inputs, "A", "RGBA"))
        nt.links.new(b, _sock(mx.inputs, "B", "RGBA"))
        return _sock(mx.outputs, "Result", "RGBA")

    if tip is None:
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "tip"
        tip = attr.outputs["Fac"]
    base = ramp(tip, [(0.0, rgba("grass_root")), (0.55, rgba("grass_a")), (1.0, rgba("grass_tip"))])
    patches = ramp(noise(0.07, 2.0), [(0.38, rgba("grass_cool")), (0.66, rgba("grass_warm"))])
    clouds = ramp(noise(0.028, 1.0), [(0.52, (1, 1, 1, 1)), (0.6, (0.62, 0.68, 0.74, 1))])
    nt.links.new(multiply(multiply(base, patches), clouds), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.95
    m.diffuse_color = rgba("grass_a")
    _mats[name] = m
    return m


# ---------------------------------------------------------------- mesh builder

class MB:
    """Accumulates primitives into one mesh, one material slot per material."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _finish(self, verts, material, xform, smooth=False):
        if xform is not None:
            bmesh.ops.transform(self.bm, matrix=xform, verts=verts)
        if material not in self.mats:
            self.mats.append(material)
        idx = self.mats.index(material)
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = idx
            f.smooth = smooth

    def box(self, material, center, size, xform=None):
        verts = bmesh.ops.create_cube(self.bm, size=1.0)["verts"]
        bmesh.ops.scale(self.bm, vec=size, verts=verts)
        bmesh.ops.translate(self.bm, vec=center, verts=verts)
        self._finish(verts, material, xform)

    def cone(self, material, base, r1, r2, h, segs=8, xform=None, smooth=False, rot=0.0):
        """Cylinder/cone standing on `base` (bottom centre)."""
        verts = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                      radius1=r1, radius2=r2, depth=h)["verts"]
        if rot:
            bmesh.ops.rotate(self.bm, matrix=Matrix.Rotation(rot, 3, "Z"), verts=verts)
        bmesh.ops.translate(self.bm, vec=Vector(base) + Vector((0, 0, h / 2)), verts=verts)
        self._finish(verts, material, xform, smooth)

    def ball(self, material, center, r, scale=(1, 1, 1), subdiv=2, xform=None):
        verts = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=r)["verts"]
        bmesh.ops.scale(self.bm, vec=scale, verts=verts)
        bmesh.ops.translate(self.bm, vec=center, verts=verts)
        self._finish(verts, material, xform, smooth=True)

    def prism(self, material, base, w, d, h, xform=None):
        """Gable roof: ridge along local X, footprint w x d centred on `base`."""
        bx, by, bz = base
        pts = [(-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (-w / 2, d / 2, 0),
               (-w / 2, 0, h), (w / 2, 0, h)]
        v = [self.bm.verts.new((bx + x, by + y, bz + z)) for x, y, z in pts]
        for f in ((3, 2, 1, 0), (0, 1, 5, 4), (2, 3, 4, 5), (1, 2, 5), (3, 0, 4)):
            self.bm.faces.new([v[i] for i in f])
        self._finish(v, material, xform)

    def slab(self, material, length, y0, y1, top, thickness, xform=None, n=14):
        """Strip along local X between y0..y1 whose top follows top(x). Bridges are built from these."""
        rings = []
        for i in range(n + 1):
            x = -length / 2 + length * i / n
            z = top(x)
            rings.append([self.bm.verts.new(p) for p in
                          ((x, y0, z), (x, y1, z), (x, y1, z - thickness), (x, y0, z - thickness))])
        for a, b in zip(rings, rings[1:]):
            for k in range(4):
                self.bm.faces.new((a[k], b[k], b[(k + 1) % 4], a[(k + 1) % 4]))
        self.bm.faces.new(rings[0][::-1])
        self.bm.faces.new(rings[-1])
        self._finish([v for r in rings for v in r], material, xform)

    def ribbon(self, material, pts, width, z, closed=False):
        n = len(pts)
        left, right = [], []
        for i, p in enumerate(pts):
            a = pts[i - 1] if closed else pts[max(i - 1, 0)]
            b = pts[(i + 1) % n] if closed else pts[min(i + 1, n - 1)]
            t = (b - a).normalized()
            off = Vector((-t.y, t.x)) * (width / 2)
            left.append(self.bm.verts.new((p.x + off.x, p.y + off.y, z)))
            right.append(self.bm.verts.new((p.x - off.x, p.y - off.y, z)))
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            self.bm.faces.new((right[i], right[j], left[j], left[i]))
        self._finish(left + right, material, None)

    def build(self, name, coll, loc=(0, 0, 0), rot=0.0, bevel=0.0):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        me = bpy.data.meshes.new("gm_" + name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        ob.location = (loc[0], loc[1], loc[2] if len(loc) > 2 else 0.0)
        ob.rotation_euler = (0.0, 0.0, rot)
        coll.objects.link(ob)
        if bevel:
            mod = ob.modifiers.new("Bevel", "BEVEL")
            mod.width = bevel
            mod.segments = 2
            mod.limit_method = "ANGLE"
        return ob


def place_xform(c, rot):
    return Matrix.Translation((c.x, c.y, 0)) @ Matrix.Rotation(rot, 4, "Z")


# ---------------------------------------------------------------- scene

def fresh_scene():
    old = bpy.data.scenes.get(SCENE)
    if old is not None:
        if bpy.context.window.scene == old:
            bpy.context.window.scene = next(s for s in bpy.data.scenes if s != old)
        for ob in list(old.collection.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        for coll in list(old.collection.children_recursive):
            bpy.data.collections.remove(coll)
        bpy.data.scenes.remove(old)
    for me in list(bpy.data.meshes):
        if me.users == 0 and me.name.startswith("gm_"):
            bpy.data.meshes.remove(me)
    sc = bpy.data.scenes.new(SCENE)
    bpy.context.window.scene = sc
    colls = {}
    for name in ("Ground", "Water", "Roads", "Walls", "Buildings", "Market", "Props", "Nature",
                 "Characters", "Lights"):
        coll = bpy.data.collections.new("Town " + name)
        sc.collection.children.link(coll)
        colls[name] = coll
    return sc, colls


def ground(colls):
    """Two ground meshes so grass can be denser on the playable map than on the scenery around it."""
    soil = grass_mat("ground", tip=0.12)
    lo, hi, far = -0.5, MAP - 0.5, 95.0

    def quads(rects, name):
        mb = MB()
        verts = []
        for x0, y0, x1, y1 in rects:
            v = [mb.bm.verts.new((x, y, 0)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            mb.bm.faces.new(v)
            verts += v
        mb._finish(verts, soil, None)
        return mb.build(name, colls["Ground"])

    inner = quads([(lo, lo, hi, hi)], "Ground")
    outer = quads([(CENTER.x - far, CENTER.y - far, CENTER.x + far, lo),
                   (CENTER.x - far, hi, CENTER.x + far, CENTER.y + far),
                   (CENTER.x - far, lo, lo, hi), (hi, lo, CENTER.x + far, hi)], "GroundOuter")
    return inner, outer


def river(colls):
    pts = catmull([Vector((river_x(y), y)) for y in range(-45, 146, 3)], per_seg=3)
    mb = MB()
    mb.ribbon(mat("bank"), pts, RIVER_W + 1.6, 0.012)
    mb.ribbon(mat("water", rough=0.12), pts, RIVER_W, 0.022)
    mb.build("River", colls["Water"])
    mark_path(pts, RIVER_W, WATER)


def dry_runs(pts):
    """Splits a path where it crosses the river, so bridges show water under their arch."""
    runs, cur = [], []
    for p in pts:
        if abs(p.x - river_x(p.y)) < RIVER_W / 2 + 0.6:
            if len(cur) > 1:
                runs.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) > 1:
        runs.append(cur)
    return runs


def lay_roads(colls):
    cobble = pattern_mat("cobble", "cobble_a", "cobble_b", "cells", 2.4)
    dirt = pattern_mat("dirt", "dirt_a", "dirt_b", "noise", 0.4)
    roads = []  # (points, width, closed) that houses line up along

    mb = MB()
    for ang in (0, 90, 180, 270):
        d = dirv(math.radians(ang))
        a, b = CENTER + d * (PLAZA_R - 0.5), CENTER + d * 62
        pts = [a + (b - a) * (i / 40) for i in range(41)]
        for run in dry_runs(pts):
            mb.ribbon(cobble, run, 4.0, 0.045)
        mark_path(pts, 4.0, ROAD)
        roads.append((pts, 4.0, False))

    ring = catmull([CENTER + dirv(t) * (RING_R + 0.8 * math.sin(3 * t))
                    for t in (i * math.tau / 24 for i in range(24))], closed=True, per_seg=4)
    mb.ribbon(cobble, ring, 3.0, 0.035, closed=True)
    mark_path(ring, 3.0, ROAD, closed=True)
    roads.append((ring, 3.0, True))

    # Riverside walk on the east bank, and a footbridge lane from the ring road across to it.
    prom = catmull([Vector((river_x(y) + RIVER_W / 2 + 2.6, y)) for y in range(40, 61, 4)], per_seg=4)
    lane_end = Vector((river_x(59.6) + RIVER_W / 2 + 2.6, 59.6))
    ring_pt = CENTER + dirv(math.radians(30)) * (RING_R + 0.8 * math.sin(math.radians(90)))
    lane = catmull([ring_pt, Vector((72, 59.8)), Vector((77, 59.7)), lane_end], per_seg=5)
    for pts in (prom, lane):
        for run in dry_runs(pts):
            mb.ribbon(cobble, run, 2.6, 0.04)
        mark_path(pts, 2.6, ROAD)
        roads.append((pts, 2.6, False))
    mb.build("Roads", colls["Roads"])

    # Dirt tracks from the west gate out to the farms.
    mb = MB()
    for pts in ([(8, 50), (6, 60), (8, 72), (13, 81)], [(8, 50), (7, 40), (9, 29), (12, 22)]):
        pts = catmull([Vector(p) for p in pts], per_seg=6)
        mb.ribbon(dirt, pts, 2.2, 0.03)
        mark_path(pts, 2.2, ROAD)
    mb.build("FarmTracks", colls["Roads"])

    bridge(colls, Vector((river_x(50), 50)), 0.0, 4.6)
    bridge(colls, Vector((river_x(59.7), 59.7)), 0.0, 3.2)
    return roads


def bridge(colls, c, rot, width):
    length = RIVER_W + 3.6
    stone = mat("stone")

    def deck(x):
        return 0.12 + 1.1 * max(0.0, math.cos(math.pi * x / length))

    mb = MB()
    mb.slab(stone, length, -width / 2, width / 2, deck, 0.55)
    for y0, y1 in ((width / 2 - 0.3, width / 2), (-width / 2, -width / 2 + 0.3)):
        mb.slab(mat("stone_dark"), length, y0, y1, lambda x: deck(x) + 0.55, 0.6)
    mb.build("Bridge", colls["Roads"], (c.x, c.y), rot, bevel=0.04)


def plaza(colls):
    mb = MB()
    stone, dark, water = mat("stone"), mat("stone_dark"), mat("water", rough=0.12)
    mb.cone(dark, (0, 0, 0), PLAZA_R + 0.6, PLAZA_R + 0.6, 0.06, segs=64)
    mb.cone(pattern_mat("plaza", "plaza_a", "plaza_b", "cells", 2.2), (0, 0, 0), PLAZA_R, PLAZA_R, 0.09, segs=64)
    # Fountain with the warp crystal rising out of it.
    mb.cone(stone, (0, 0, 0), 3.4, 3.4, 0.7, segs=32)
    mb.cone(water, (0, 0, 0), 3.0, 3.0, 0.62, segs=32)
    mb.cone(stone, (0, 0, 0), 1.0, 0.8, 1.5, segs=12)
    mb.cone(stone, (0, 0, 1.4), 1.7, 1.7, 0.25, segs=24)
    crystal = mat("crystal", rough=0.1, emit=1.6)
    mb.cone(crystal, (0, 0, 1.75), 0.0, 0.75, 0.9, segs=6)  # emission kept low so AgX keeps the blue
    mb.cone(crystal, (0, 0, 2.65), 0.75, 0.0, 2.4, segs=6)
    # Flower beds on the diagonals, banners between them.
    for k in range(4):
        p = dirv(math.radians(45 + 90 * k)) * 6.4
        mb.cone(stone, (p.x, p.y, 0), 1.3, 1.3, 0.4, segs=16)
        mb.ball(mat("leaf_2"), (p.x, p.y, 0.55), 0.95, scale=(1, 1, 0.55))
        for j in range(5):
            q = p + dirv(j * 1.3) * 0.7
            mb.ball(mat("flower_%d" % (j % 3 + 1)), (q.x, q.y, 0.85), 0.16, subdiv=1)
        claim_circle(CENTER + p, 1.3)
    for k in range(8):
        p = dirv(math.radians(22.5 + 45 * k)) * (PLAZA_R - 1.0)
        out = math.radians(22.5 + 45 * k)
        xf = Matrix.Translation((p.x, p.y, 0)) @ Matrix.Rotation(out + math.pi / 2, 4, "Z")
        mb.cone(mat("wood"), (p.x, p.y, 0), 0.08, 0.08, 3.2, segs=6)
        mb.box(mat("banner"), (0, 0.12, 2.1), (0.8, 0.05, 1.5), xf)
        mb.box(mat("gold"), (0, 0.12, 2.9), (1.0, 0.08, 0.1), xf)
    mb.build("Plaza", colls["Props"], (CENTER.x, CENTER.y))
    claim_circle(CENTER, 3.5)


def walls(colls):
    mb = MB()
    stone, dark, roof = mat("stone"), mat("stone_dark"), mat("roof_blue")
    gates = [0, math.pi / 2, math.pi, 3 * math.pi / 2]

    def near_gate(t, extra):
        return any(abs((t - g + math.pi) % math.tau - math.pi) * WALL_R < GATE_HALF + extra for g in gates)

    def near_river(p, extra):
        return abs(p.x - river_x(p.y)) < RIVER_W / 2 + extra

    n = 120
    seg = math.tau * WALL_R / n + 0.12
    for i in range(n):
        t = math.tau * (i + 0.5) / n
        p = CENTER + dirv(t) * WALL_R
        if near_gate(t, 1.8) or near_river(p, 1.0):
            continue
        xf = place_xform(p, t + math.pi / 2)
        mb.box(stone, (0, 0, 0.9), (seg, 1.1, 1.8), xf)
        mb.box(dark, (0, 0, 0.12), (seg, 1.3, 0.24), xf)
        if i % 2 == 0:
            mb.box(stone, (0, 0, 2.0), (seg * 0.55, 1.1, 0.4), xf)
        claim_circle(p, 0.9)
    for k in range(12):
        t = math.radians(15 + 30 * k)
        p = CENTER + dirv(t) * WALL_R
        if near_river(p, 2.5):
            continue
        mb.cone(stone, (p.x, p.y, 0), 1.5, 1.5, 3.4, segs=12)
        mb.cone(roof, (p.x, p.y, 3.4), 1.95, 0.0, 2.3, segs=12)
        claim_circle(p, 1.5)
    for g in gates:
        d = dirv(g)
        tan = Vector((-d.y, d.x))
        mid = CENTER + d * WALL_R
        for s in (-1, 1):
            p = mid + tan * s * (GATE_HALF + 1.5)
            mb.cone(stone, (p.x, p.y, 0), 1.9, 1.9, 4.8, segs=14)
            mb.cone(roof, (p.x, p.y, 4.8), 2.35, 0.0, 2.9, segs=14)
            fx = place_xform(p, g + math.pi / 2)
            mb.box(mat("banner"), (0, -1.95, 2.9), (1.0, 0.06, 1.8), fx)
            mb.box(mat("gold"), (0, -1.97, 3.85), (1.2, 0.08, 0.12), fx)
            claim_circle(p, 1.9)
        mb.box(stone, (0, 0, 3.9), (2 * GATE_HALF + 3.0, 1.5, 1.2), place_xform(mid, g + math.pi / 2))
    mb.build("TownWall", colls["Walls"], bevel=0.05)


# ---------------------------------------------------------------- buildings

def facade(face, w, d):
    """Maps facade coords (u along the wall, v out of it, z up) to building coords for one wall."""
    return {
        "front": Matrix(((1, 0, 0, 0), (0, -1, 0, -d / 2), (0, 0, 1, 0), (0, 0, 0, 1))),
        "back": Matrix(((-1, 0, 0, 0), (0, 1, 0, d / 2), (0, 0, 1, 0), (0, 0, 0, 1))),
        "right": Matrix(((0, 1, 0, w / 2), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))),
        "left": Matrix(((0, -1, 0, -w / 2), (-1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))),
    }[face]


def window(mb, F, u, z, shutters=None, flowers=False):
    wood = mat("wood")
    mb.box(mat("window", rough=0.4, emit=0.8), (u, 0.0, z), (0.52, 0.08, 0.58), F)
    for du, dz, size in ((0, 0.33, (0.72, 0.12, 0.08)), (0, -0.34, (0.8, 0.18, 0.09)),
                         (-0.3, 0, (0.08, 0.12, 0.66)), (0.3, 0, (0.08, 0.12, 0.66)),
                         (0, 0, (0.04, 0.1, 0.58)), (0, 0.04, (0.52, 0.1, 0.04))):
        mb.box(wood, (u + du, 0.04, z + dz), size, F)
    if shutters:
        for du in (-0.47, 0.47):
            mb.box(mat(shutters), (u + du, 0.05, z), (0.28, 0.06, 0.64), F)
    if flowers:
        mb.box(wood, (u, 0.14, z - 0.47), (0.72, 0.24, 0.16), F)
        for j in range(4):
            mb.ball(mat("flower_%d" % random.randint(1, 3)), (u - 0.27 + 0.18 * j, 0.14, z - 0.34), 0.11, subdiv=1, xform=F)


def door(mb, F, u, porch_roof=None):
    wood, dark = mat("wood"), mat("door")
    mb.box(dark, (u, 0.02, 0.68), (0.78, 0.08, 1.3), F)
    mb.box(wood, (u, 0.03, 0.68), (0.04, 0.09, 1.3), F)
    for du, dz, size in ((0, 1.38, (1.02, 0.14, 0.12)), (-0.45, 0.68, (0.12, 0.14, 1.36)), (0.45, 0.68, (0.12, 0.14, 1.36))):
        mb.box(wood, (u + du, 0.05, dz), size, F)
    mb.ball(mat("gold"), (u + 0.25, 0.09, 0.7), 0.05, subdiv=1, xform=F)
    mb.box(mat("stone"), (u, 0.3, 0.08), (1.2, 0.5, 0.16), F)
    if porch_roof:
        mb.prism(mat(porch_roof), (u, 0.42, 1.55), 1.4, 0.95, 0.45, F)


def gable_roof(mb, key, w, d, base_z, rise, eave=0.45, gable=0.35, rows=4, at=None):
    """Thick gable roof built from stepped shingle rows, with a ridge cap. `at` moves the whole roof."""
    at = at if at is not None else Matrix.Identity(4)
    half = d / 2 + eave
    slope = math.atan2(rise, d / 2)
    run = half / math.cos(slope)
    length = w + 2 * gable
    top = base_z + rise + 0.12
    for side in (-1, 1):
        tilt = Matrix.Rotation(-side * slope, 4, "X")
        for k in range(rows):
            u = (k + 0.5) * run / rows
            row = at @ Matrix.Translation((0, 0, top)) @ tilt @ Matrix.Translation((0, side * u, 0.03 * k))
            mb.box(mat(key if k % 2 == 0 else key + "_dk"), (0, 0, 0), (length, run / rows * 1.12, 0.16), row)
    mb.box(mat(key + "_dk"), (0, 0, top + 0.08), (length + 0.1, 0.34, 0.2), at)
    mb.prism(mat("plaster"), (0, 0, base_z), w, d, rise, at)
    for sx in (-1, 1):
        mb.box(mat("wood"), (sx * (w / 2 + 0.02), 0, base_z + 0.06), (0.14, d + 0.1, 0.14), at)


def windows_row(mb, w, d, z, door_x=None):
    xs = [x for x in (-w / 4, w / 4) if door_x is None or abs(x - door_x) > 0.9]
    F = facade("front", w, d)
    for x in xs:
        window(mb, F, x, z)
    for face in ("left", "right"):
        window(mb, facade(face, w, d), 0.0, z)
    return xs


def house(coll, c, rot, w, d, two_storey):
    """Storybook cottage: stone plinth, half-timbered plaster walls, shuttered windows, shingle roof.
    Two-storey houses get an upper floor that juts out over the street."""
    mb = MB()
    plaster, wood = mat("plaster"), mat("wood")
    shutters = random.choice([None, "shutter_1", "shutter_2", "shutter_3"])
    ground_h = rnd(1.9, 2.2)
    mb.box(mat("stone"), (0, 0, 0.2), (w + 0.16, d + 0.16, 0.4))
    mb.box(plaster, (0, 0, ground_h / 2), (w, d, ground_h))
    top_d, top_y, wall_h = d, 0.0, ground_h
    if two_storey:
        top_d, top_y = d + 0.5, -0.25
        mb.box(wood, (0, top_y, ground_h + 0.08), (w + 0.1, top_d + 0.1, 0.16))
        mb.box(plaster, (0, top_y, ground_h + 0.85), (w, top_d, 1.6))
        wall_h = ground_h + 1.65
    # Timber frame: corner posts, sill and plate beams, braces on the gable walls.
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box(wood, (sx * w / 2, sy * d / 2, ground_h / 2), (0.22, 0.22, ground_h))
    mb.box(wood, (0, 0, 0.45), (w + 0.04, d + 0.04, 0.12))
    mb.box(wood, (0, top_y, wall_h - 0.08), (w + 0.04, top_d + 0.04, 0.14))
    for face in ("left", "right"):
        F = facade(face, w, d)
        for su in (-1, 1):
            brace = F @ Matrix.Translation((su * d * 0.3, 0.02, ground_h * 0.55)) @ Matrix.Rotation(su * 0.7, 4, "Y")
            mb.box(wood, (0, 0, 0), (0.1, 0.06, ground_h * 0.8), brace)
    front = facade("front", w, d)
    door_x = rnd(-w / 5, w / 5)
    door(mb, front, door_x, porch_roof=random.choice([None, None, "roof_red", "slate"]))
    for x in (-w / 4 - 0.3, w / 4 + 0.3):
        if abs(x - door_x) > 1.0:
            window(mb, front, x, 1.2, shutters, flowers=random.random() < 0.5)
    for face in ("left", "right"):
        window(mb, facade(face, w, d), 0.0, 1.2, shutters)
    if two_storey:
        upper = Matrix.Translation((0, top_y, 0)) @ facade("front", w, top_d)
        for x in (-w / 4, w / 4):
            window(mb, upper, x, ground_h + 0.9, shutters, flowers=random.random() < 0.4)
    roof_key = random.choice(["roof_red"] * 3 + ["roof_orange"] * 2 + ["roof_blue"] * 3 + ["slate"])
    rise = max(1.6, top_d * 0.6)
    gable_roof(mb, roof_key, w, top_d, wall_h - 0.02, rise, at=Matrix.Translation((0, top_y, 0)))
    if random.random() < 0.5:
        cx, cy = w * 0.28, d * 0.18
        mb.box(mat("stone_dark"), (cx, cy, wall_h + rise * 0.5), (0.5, 0.5, rise + 0.5))
        mb.box(mat("stone"), (cx, cy, wall_h + rise + 0.8), (0.64, 0.64, 0.14))
    # A barrel or a crate by one of the side walls.
    side, kind = random.choice((-1, 1)), random.random()
    if kind < 0.35:
        mb.cone(wood, (side * (w / 2 + 0.4), rnd(-d / 4, d / 4), 0), 0.26, 0.26, 0.7, segs=10)
    elif kind < 0.6:
        mb.box(wood, (side * (w / 2 + 0.4), rnd(-d / 4, d / 4), 0.28), (0.55, 0.55, 0.55))
    mb.build("House", coll, (c.x, c.y), rot, bevel=0.03)


def guild_hall(coll, c, rot):
    mb = MB()
    w, d, h = 11.0, 8.0, 4.4
    mb.box(mat("stone"), (0, 0, 0.25), (w + 0.3, d + 0.3, 0.5))
    mb.box(mat("plaster"), (0, 0, h / 2), (w, d, h))
    mb.box(mat("wood"), (0, 0, 2.2), (w + 0.08, d + 0.08, 0.22))
    mb.prism(mat("roof_blue"), (0, 0, h - 0.1), w + 0.8, d + 1.0, 4.0)
    for sx in (-1, 1):
        mb.cone(mat("stone"), (sx * w / 2, -d / 2, 0), 1.4, 1.4, 7.6, segs=12)
        mb.cone(mat("roof_blue"), (sx * w / 2, -d / 2, 7.6), 1.8, 0.0, 3.4, segs=12)
        mb.box(mat("banner"), (sx * 2.4, -d / 2 - 0.08, 2.6), (1.1, 0.08, 2.4))
        mb.box(mat("gold"), (sx * 2.4, -d / 2 - 0.1, 3.85), (1.3, 0.1, 0.14))
    mb.box(mat("door"), (0, -d / 2 - 0.05, 1.2), (1.8, 0.14, 2.4))
    mb.box(mat("gold"), (0, -d / 2 - 0.08, 2.5), (2.2, 0.12, 0.2))
    mb.box(mat("stone"), (0, -d / 2 - 0.9, 0.15), (4.2, 1.6, 0.3))
    windows_row(mb, w, d, 3.3)
    mb.build("GuildHall", coll, (c.x, c.y), rot, bevel=0.07)


def inn(coll, c, rot):
    mb = MB()
    w, d, h = 9.0, 7.0, 4.0
    mb.box(mat("stone"), (0, 0, 0.2), (w + 0.2, d + 0.2, 0.4))
    mb.box(mat("plaster"), (0, 0, h / 2), (w, d, h))
    for x in (-w / 2, -w / 6, w / 6, w / 2):
        mb.box(mat("wood"), (x, -d / 2, h / 2), (0.26, 0.26, h))
    mb.box(mat("wood"), (0, 0, 2.0), (w + 0.06, d + 0.06, 0.2))
    mb.prism(mat("roof_red"), (0, 0, h - 0.1), w + 0.8, d + 1.0, 3.4)
    for x in (-w * 0.3, w * 0.3):
        mb.box(mat("stone_dark"), (x, d * 0.2, h + 2.0), (0.6, 0.6, 2.6))
    mb.box(mat("door"), (0, -d / 2 - 0.05, 0.75), (1.2, 0.14, 1.5))
    windows_row(mb, w, d, 1.2, 0.0)
    windows_row(mb, w, d, 2.9)
    # Hanging sign and a couple of outdoor tables.
    mb.box(mat("wood"), (1.3, -d / 2 - 0.6, 2.4), (0.1, 1.2, 0.1))
    mb.box(mat("gold"), (1.3, -d / 2 - 0.95, 1.95), (0.08, 0.8, 0.6))
    for x in (-2.6, 2.8):
        mb.cone(mat("wood"), (x, -d / 2 - 2.0, 0), 0.6, 0.6, 0.75, segs=10)
        mb.cone(mat("wood"), (x, -d / 2 - 2.0, 0.75), 0.06, 0.06, 1.3, segs=6)
        mb.cone(mat("awning_%d" % (1 if x < 0 else 2)), (x, -d / 2 - 2.0, 2.0), 1.2, 0.05, 0.5, segs=8)
    mb.build("Inn", coll, (c.x, c.y), rot, bevel=0.06)


def blacksmith(coll, c, rot):
    mb = MB()
    w, d, h = 7.0, 6.0, 2.6
    mb.box(mat("stone_dark"), (0, 0, h / 2), (w, d, h))
    mb.prism(mat("slate"), (0, 0, h - 0.1), w + 0.7, d + 0.9, 2.4)
    mb.box(mat("stone"), (w / 2 - 0.9, d / 2 - 0.9, 3.0), (1.3, 1.3, 6.0))
    mb.box(mat("fire", emit=4.0), (w / 2 - 0.9, d / 2 - 0.9, 6.05), (0.9, 0.9, 0.12))
    # Open forge under a lean-to at the front.
    mb.box(mat("wood"), (0, -d / 2 - 1.2, 2.2), (w * 0.8, 2.6, 0.15))
    for sx in (-1, 1):
        mb.box(mat("wood"), (sx * w * 0.38, -d / 2 - 2.3, 1.1), (0.2, 0.2, 2.2))
    mb.box(mat("stone"), (-1.4, -d / 2 - 1.0, 0.5), (1.6, 1.2, 1.0))
    mb.box(mat("fire", emit=5.0), (-1.4, -d / 2 - 1.0, 1.02), (1.2, 0.8, 0.06))
    mb.box(mat("eye"), (1.2, -d / 2 - 1.6, 0.4), (0.9, 0.45, 0.8))
    mb.box(mat("door"), (1.6, -d / 2 - 0.04, 0.7), (0.9, 0.12, 1.4))
    mb.build("Blacksmith", coll, (c.x, c.y), rot, bevel=0.06)


def stall(coll, c, rot):
    mb = MB()
    wood = mat("wood")
    mb.box(wood, (0, -0.45, 0.45), (2.2, 0.9, 0.9))
    for j in range(3):
        mb.ball(mat(random.choice(["flower_1", "flower_2", "flower_3", "leaf_2", "awning_3"])),
                (-0.6 + 0.6 * j, -0.45, 1.05), 0.2, subdiv=1)
    for sx in (-1.05, 1.05):
        for sy in (-0.95, 0.85):
            mb.box(wood, (sx, sy, 1.15 if sy < 0 else 1.35), (0.1, 0.1, 2.3 if sy < 0 else 2.7))
    stripe = mat(random.choice(["awning_1", "awning_2", "awning_3"]))
    tilt = Matrix.Translation((0, -0.05, 2.5)) @ Matrix.Rotation(math.radians(-14), 4, "X")
    for k in range(5):
        mb.box(stripe if k % 2 == 0 else mat("cloth"), (-0.96 + 0.48 * k, 0, 0), (0.48, 2.3, 0.06), tilt)
    mb.box(wood, (0.5, 0.5, 0.3), (0.6, 0.5, 0.6))
    mb.build("Stall", coll, (c.x, c.y), rot, bevel=0.03)


def place_special(build_fn, coll, angle_deg, w, d, r_from=13.0):
    dv = dirv(math.radians(angle_deg))
    r = r_from
    while r < WALL_R:
        c = CENTER + dv * r
        rot = facing(-dv)
        if rect_free(c, w, d, rot, margin=0.6):
            claim(c, w, d, rot)
            build_fn(coll, c, rot)
            return
        r += 0.5
    print("no room for", build_fn.__name__)


def market(colls):
    """Stalls ring the east half of the plaza and line the east road down to the river."""
    spots = [(CENTER + dirv(math.radians(a)) * 13.8, -dirv(math.radians(a)))
             for a in (-72, -58, -44, -30, 30, 44, 58, 72)]
    spots += [(Vector((x, 50 + side * 3.9)), Vector((0, -side))) for side in (1, -1) for x in (72.4, 74.9)]
    for c, front in spots:
        rot = facing(front)
        if rect_free(c, 2.4, 2.2, rot, margin=0.3):
            claim(c, 2.4, 2.2, rot)
            stall(colls["Market"], c, rot)


def path_sampler(pts, closed):
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed else [])
    lengths = [(b - a).length for a, b in segs]
    total = sum(lengths)

    def at(s):
        for (a, b), ln in zip(segs, lengths):
            if s <= ln and ln > 0:
                return a + (b - a) * (s / ln), (b - a).normalized()
            s -= ln
        a, b = segs[-1]
        return b, (b - a).normalized()

    return total, at


def houses(colls, roads):
    coll = colls["Buildings"]
    for pts, width, closed in roads:
        total, at = path_sampler(pts, closed)
        for side in (1, -1):
            s = rnd(0, 2)
            while s < total:
                p, t = at(s)
                w, d = rnd(3.4, 5.0), rnd(3.0, 4.0)
                nrm = Vector((-t.y, t.x)) * side
                c = p + nrm * (width / 2 + 0.9 + d / 2)
                rot = facing(-nrm)
                if rect_free(c, w, d, rot):
                    claim(c, w, d, rot)
                    house(coll, c, rot, w, d, random.random() < 0.25)
                    s += w + rnd(0.6, 1.8)
                else:
                    s += 1.0
    # Fill the blocks behind the street fronts, facing the nearest road.
    road_pts = [p for pts, _, _ in roads for p in pts[::2]]
    for _ in range(3000):
        c = CENTER + dirv(rnd(0, math.tau)) * rnd(PLAZA_R + 3, WALL_R - 3)
        q = min(road_pts, key=lambda p: (p - c).length_squared)
        if (q - c).length > 11:
            continue
        w, d = rnd(3.2, 4.6), rnd(3.0, 3.8)
        rot = facing((q - c).normalized())
        if rect_free(c, w, d, rot, margin=0.7):
            claim(c, w, d, rot)
            house(coll, c, rot, w, d, random.random() < 0.2)


def field(colls, c, rot, w, d):
    mb = MB()
    xf = place_xform(c, rot)
    mb.box(mat("soil"), (0, 0, 0.06), (w, d, 0.12), xf)
    rows = int(d / 0.9)
    for i in range(rows):
        y = -d / 2 + 0.45 + i * 0.9
        mb.box(mat("wheat"), (0, y, 0.38), (w - 0.6, 0.5, 0.55), xf)
    for i in range(int(2 * (w + d) / 1.6)):
        s = i * 1.6
        if s < w:
            p = (-w / 2 + s, -d / 2 - 0.4)
        elif s < w + d:
            p = (w / 2 + 0.4, -d / 2 + s - w)
        elif s < 2 * w + d:
            p = (w / 2 - (s - w - d), d / 2 + 0.4)
        else:
            p = (-w / 2 - 0.4, d / 2 - (s - 2 * w - d))
        mb.box(mat("wood"), (p[0], p[1], 0.45), (0.15, 0.15, 0.9), xf)
    mb.build("Field", colls["Props"])
    claim(c, w + 1, d + 1, rot, FIELD)


def tree(mb, p, scale):
    if random.random() < 0.2:
        mb.cone(mat("trunk"), (p.x, p.y, 0), 0.22 * scale, 0.18 * scale, 0.8 * scale, segs=6)
        for k in range(3):
            r = (1.5 - 0.35 * k) * scale
            mb.cone(mat("pine"), (p.x, p.y, (0.7 + 1.0 * k) * scale), r, 0.0, 1.8 * scale, segs=8, smooth=True)
        return
    leaf = mat(random.choice(["leaf_1", "leaf_2", "leaf_3"] * 3 + ["leaf_autumn"]))
    h = 1.3 * scale
    mb.cone(mat("trunk"), (p.x, p.y, 0), 0.28 * scale, 0.2 * scale, h, segs=6)
    r = rnd(1.3, 1.8) * scale
    mb.ball(leaf, (p.x, p.y, h + r * 0.7), r)
    for _ in range(random.randint(1, 3)):
        q = p + dirv(rnd(0, math.tau)) * r * 0.6
        mb.ball(leaf, (q.x, q.y, h + r * rnd(0.3, 0.6)), r * rnd(0.55, 0.75))


def nature(colls):
    mb = MB()
    placed = []

    def clear_outside_map(p):
        return abs(p.x - river_x(p.y)) > RIVER_W and min(abs(p.x - 50), abs(p.y - 50)) > 4.5

    def try_tree(p, gap, scale):
        if any((p - q).length < gap for q in placed):
            return
        gx, gy = round(p.x), round(p.y)
        if in_map(gx, gy):
            if not cell_is(p, FREE, ring=1):
                return
            grid[gy][gx] = BUILT
        elif not clear_outside_map(p):
            return
        tree(mb, p, scale)
        placed.append(p)

    for _ in range(9000):
        if len(placed) >= 380:
            break
        p = Vector((rnd(-40, 140), rnd(-40, 140)))
        if (p - CENTER).length > WALL_R + 3:
            try_tree(p, 2.8, rnd(0.9, 1.25))
    inside = len(placed)
    for _ in range(3000):
        if len(placed) - inside >= 45:
            break
        p = CENTER + dirv(rnd(0, math.tau)) * rnd(PLAZA_R + 2, WALL_R - 2)
        try_tree(p, 3.0, rnd(0.7, 0.9))
    # Bushes fill the leftover gaps in town and dot the meadows.
    bushes = 0
    for _ in range(6000):
        if bushes >= 260:
            break
        p = CENTER + dirv(rnd(0, math.tau)) * rnd(PLAZA_R + 2, 55)
        if not cell_is(p, FREE) or any((p - q).length < 1.6 for q in placed):
            continue
        grid[round(p.y)][round(p.x)] = BUILT
        leaf = mat(random.choice(["leaf_1", "leaf_2", "leaf_3", "leaf_2"]))
        r = rnd(0.45, 0.8)
        mb.ball(leaf, (p.x, p.y, r * 0.55), r, scale=(1, 1, 0.8), subdiv=1)
        if random.random() < 0.3:
            mb.ball(mat("flower_%d" % random.randint(1, 3)), (p.x, p.y - r * 0.6, r * 0.75), 0.12, subdiv=1)
        placed.append(p)
        bushes += 1
    mb.build("Trees", colls["Nature"])


def lanterns(colls):
    mb = MB()
    lamp = mat("lantern", rough=0.4, emit=5.0)
    for ang in (0, 90, 180, 270):
        d = dirv(math.radians(ang))
        side = Vector((-d.y, d.x))
        for k, r in enumerate(range(int(PLAZA_R) + 3, int(WALL_R) - 2, 5)):
            p = CENTER + d * r + side * (2.6 if k % 2 else -2.6)
            if not cell_is(p, FREE):
                continue
            mb.cone(mat("wood"), (p.x, p.y, 0), 0.08, 0.07, 2.1, segs=6)
            mb.box(lamp, (p.x, p.y, 2.25), (0.3, 0.3, 0.35))
            mb.cone(mat("stone_dark"), (p.x, p.y, 2.42), 0.28, 0.0, 0.3, segs=4, rot=math.pi / 4)
    mb.build("Lanterns", colls["Props"])


def creatures(colls):
    mb = MB()
    eye = mat("eye", rough=0.3)
    count = 0
    for _ in range(600):
        if count >= 14:
            break
        p = CENTER + dirv(rnd(0, math.tau)) * rnd(WALL_R + 3, 58)
        if not cell_is(p, FREE, ring=1):
            continue
        body = mat(random.choice(["slime_1", "slime_2", "slime_3"]), rough=0.3)
        mb.ball(body, (p.x, p.y, 0.32), 0.48, scale=(1, 1, 0.72))
        for sx in (-0.15, 0.15):
            mb.ball(eye, (p.x + sx, p.y - 0.42, 0.42), 0.07, subdiv=1)
        count += 1
    mb.build("Slimes", colls["Characters"])

    mb = MB()
    road_cells = [(x, y) for y in range(MAP) for x in range(MAP)
                  if grid[y][x] == ROAD and (Vector((x, y)) - CENTER).length < WALL_R - 2]
    for x, y in random.sample(road_cells, min(42, len(road_cells))):
        p = Vector((x + rnd(-0.4, 0.4), y + rnd(-0.4, 0.4)))
        mb.cone(mat(random.choice(["cloth_1", "cloth_2", "cloth_3", "cloth_4"])), (p.x, p.y, 0), 0.26, 0.17, 0.5, segs=8)
        mb.ball(mat("skin"), (p.x, p.y, 0.76), 0.27)
        mb.ball(mat("hair"), (p.x, p.y + 0.05, 0.86), 0.28, scale=(1, 1, 0.75))
    mb.build("Adventurers", colls["Characters"])


def grass_clump():
    """A tuft of curved blades. Normals point up so the tuft shades like one soft mass."""
    old = bpy.data.objects.get("GM_GrassClump")
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    bm = bmesh.new()
    tips = []
    for _ in range(5):
        a, lean = rnd(0, math.tau), rnd(0.15, 0.5)
        h, w = rnd(0.2, 0.34), rnd(0.07, 0.1)
        base = Vector((rnd(-0.09, 0.09), rnd(-0.09, 0.09), 0))
        out, side = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))
        mid = base + out * lean * h * 0.35 + Vector((0, 0, h * 0.55))
        tip = base + out * lean * h + Vector((0, 0, h))
        ring = [base - side * w / 2, base + side * w / 2, mid + side * w * 0.35, mid - side * w * 0.35, tip]
        v = [bm.verts.new(p) for p in ring]
        bm.faces.new(v[:4])
        bm.faces.new((v[3], v[2], v[4]))
        tips += [0.0, 0.0, 0.55, 0.55, 1.0]
    me = bpy.data.meshes.new("gm_grass_clump")
    bm.to_mesh(me)
    bm.free()
    attr = me.attributes.new("tip", "FLOAT", "POINT")
    attr.data.foreach_set("value", tips)
    me.normals_split_custom_set_from_vertices([(0.0, 0.0, 1.0)] * len(me.vertices))
    me.materials.append(grass_mat("grass_blade"))
    return bpy.data.objects.new("GM_GrassClump", me)


def grass(colls, grounds):
    """Scatters tufts over the ground with geometry nodes, skipping anything standing on it
    (roads, water, buildings, walls, fields): points within a hair of those surfaces are deleted."""
    clump = grass_clump()
    mask = grass_mask(colls)

    ng = bpy.data.node_groups.get("GM_Grass")
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new("GM_Grass", "GeometryNodeTree")
    if hasattr(ng, "is_modifier"):
        ng.is_modifier = True
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    density = ng.interface.new_socket("Density", in_out="INPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")

    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    L.new(gi.outputs["Geometry"], dist.inputs["Mesh"])
    L.new(gi.outputs["Density"], dist.inputs["Density"])

    blockers = N.new("GeometryNodeObjectInfo")
    blockers.inputs["Object"].default_value = mask
    prox = N.new("GeometryNodeProximity")
    prox.target_element = "FACES"
    L.new(blockers.outputs["Geometry"], next(s for s in prox.inputs if s.type == "GEOMETRY"))
    near = N.new("FunctionNodeCompare")
    near.data_type, near.operation = "FLOAT", "LESS_THAN"
    L.new(prox.outputs["Distance"], _sock(near.inputs, "A", "VALUE"))
    _sock(near.inputs, "B", "VALUE").default_value = 0.05
    keep = N.new("GeometryNodeDeleteGeometry")
    keep.domain = "POINT"
    L.new(dist.outputs["Points"], keep.inputs["Geometry"])
    L.new(near.outputs[0], keep.inputs["Selection"])

    tuft = N.new("GeometryNodeObjectInfo")
    tuft.inputs["Object"].default_value = clump
    tuft.inputs["As Instance"].default_value = True
    spin = N.new("FunctionNodeRandomValue")
    spin.data_type = "FLOAT_VECTOR"
    _sock(spin.inputs, "Max", "VECTOR").default_value = (0, 0, math.tau)
    size = N.new("FunctionNodeRandomValue")
    size.data_type = "FLOAT"
    _sock(size.inputs, "Min", "VALUE").default_value = 0.65
    _sock(size.inputs, "Max", "VALUE").default_value = 1.3
    inst = N.new("GeometryNodeInstanceOnPoints")
    L.new(keep.outputs["Geometry"], inst.inputs["Points"])
    L.new(tuft.outputs["Geometry"], inst.inputs["Instance"])
    L.new(_sock(spin.outputs, "Value", "VECTOR"), inst.inputs["Rotation"])
    L.new(_sock(size.outputs, "Value", "VALUE"), inst.inputs["Scale"])

    join = N.new("GeometryNodeJoinGeometry")
    L.new(gi.outputs["Geometry"], join.inputs[0])
    L.new(inst.outputs["Instances"], join.inputs[0])
    L.new(join.outputs[0], go.inputs["Geometry"])

    for ob, per_m2 in zip(grounds, (34.0, 9.0)):
        mod = ob.modifiers.new("Grass", "NODES")
        mod.node_group = ng
        mod[density.identifier] = per_m2
        # Grass receives shadows from buildings but casts none, which keeps it soft like painted grass.
        ob.visible_shadow = False


def grass_mask(colls):
    """Flat footprint of everything grass must not grow through, from what the build claimed."""
    mb = MB()
    flat = mat("eye")
    verts = []

    def quad(pts):
        v = [mb.bm.verts.new((p.x, p.y, 0)) for p in pts]
        mb.bm.faces.new(v)
        verts.extend(v)

    for item in grass_blockers + [("circle", CENTER, PLAZA_R + 0.6)]:
        if item[0] == "rect":
            _, c, w, d, rot = item
            m = Matrix.Rotation(rot, 2)
            quad([c + m @ Vector((sx * w / 2, sy * d / 2)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        elif item[0] == "circle":
            _, c, r = item
            ring = [c + dirv(i * math.tau / 24) * r for i in range(24)]
            v = [mb.bm.verts.new((p.x, p.y, 0)) for p in ring]
            mb.bm.faces.new(v)
            verts.extend(v)
        else:
            _, pts, width, closed = item
            n = len(pts)
            for i in range(n if closed else n - 1):
                a, b = pts[i], pts[(i + 1) % n]
                if (b - a).length == 0:
                    continue
                t = (b - a).normalized()
                off = Vector((-t.y, t.x)) * (width / 2)
                quad([a - off - t * 0.3, b - off + t * 0.3, b + off + t * 0.3, a + off - t * 0.3])
    mb._finish(verts, flat, None)
    ob = mb.build("GrassMask", colls["Ground"])
    ob.hide_render = True
    ob.hide_set(True)
    return ob


# ---------------------------------------------------------------- light, cameras, output

def lighting_and_cameras(sc, coll):
    world = bpy.data.worlds.get("GM_Sky") or bpy.data.worlds.new("GM_Sky")
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (*linear("#b8dcf7"), 1.0)
    bg.inputs[1].default_value = 0.75
    sc.world = world

    sun = bpy.data.lights.new("GM_Sun", "SUN")
    sun.energy = 4.6
    sun.angle = math.radians(14)
    sun.color = (1.0, 0.93, 0.82)
    ob = bpy.data.objects.new("Sun", sun)
    ob.rotation_euler = (math.radians(46), 0, math.radians(-38))
    coll.objects.link(ob)

    glow = bpy.data.lights.new("GM_CrystalGlow", "POINT")
    glow.energy = 900
    glow.color = linear("#5fd0ff")
    glow.shadow_soft_size = 0.6
    ob = bpy.data.objects.new("CrystalGlow", glow)
    ob.location = (CENTER.x, CENTER.y, 3.4)
    coll.objects.link(ob)

    def camera(name, target, dist, pitch_deg, lens, fstop=None):
        cam = bpy.data.cameras.new("GM_" + name)
        cam.lens = lens
        cam.clip_end = 1000
        p = math.radians(pitch_deg)
        ob = bpy.data.objects.new(name, cam)
        ob.location = (target.x, target.y - dist * math.cos(p), dist * math.sin(p))
        ob.rotation_euler = (math.pi / 2 - p, 0, 0)
        if fstop:
            cam.dof.use_dof = True
            cam.dof.focus_distance = dist
            cam.dof.aperture_fstop = fstop
        coll.objects.link(ob)
        return ob

    sc.camera = camera("CamOverview", CENTER + Vector((0, 1)), 168, 58, 40, fstop=0.08)
    camera("CamGameplay", CENTER + Vector((5, -9)), 30, 52, 32, fstop=0.9)

    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = engine
            break
        except TypeError:
            continue
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.eevee.taa_render_samples = 48
    sc.eevee.use_raytracing = True
    sc.eevee.use_fast_gi = True
    sc.eevee.fast_gi_distance = 3.0
    looks = [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items]
    want = next((lk for lk in looks if "Medium High Contrast" in lk), None)
    if want:
        sc.view_settings.look = want


def write_walkable():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = ["".join(grid[y][x] for x in range(MAP)) for y in range(MAP - 1, -1, -1)]
    with open(os.path.join(OUT_DIR, "walkable.txt"), "w") as f:
        f.write("# GM starter town walkability, %dx%d cells. First row is y=%d, first column x=0.\n" % (MAP, MAP, MAP - 1))
        f.write("# walkable: . ground  = road  , field      blocked: # building/wall/tree  ~ water\n")
        f.write("\n".join(rows) + "\n")


def build():
    random.seed(SEED)
    for row in grid:
        row[:] = [FREE] * MAP
    grass_blockers.clear()
    _mats.clear()
    sc, colls = fresh_scene()
    grounds = ground(colls)
    river(colls)
    roads = lay_roads(colls)
    plaza(colls)
    walls(colls)
    place_special(guild_hall, colls["Buildings"], 62, 14, 11, r_from=21)
    place_special(inn, colls["Buildings"], 125, 10, 12, r_from=21)
    place_special(blacksmith, colls["Buildings"], 205, 8, 11, r_from=24)
    market(colls)
    field(colls, Vector((13, 86)), math.radians(-40), 12, 8)
    field(colls, Vector((12, 15)), math.radians(35), 11, 8)
    houses(colls, roads)
    nature(colls)
    lanterns(colls)
    creatures(colls)
    grass(colls, grounds)
    lighting_and_cameras(sc, colls["Lights"])
    write_walkable()
    counts = {name: len(c.objects) for name, c in colls.items()}
    print("GM Town built:", counts)
    return counts


result = build()

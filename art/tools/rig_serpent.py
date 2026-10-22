"""Rigs the adult Abyssal Lantern Serpent (art/models/serpent/parts-lantern-adult-v1.png) as a game mount.

Run inside Blender after importing the Hyper3D body (and, optionally, the saddle), with p pointing at this file:
    p = "/path/to/GM-fron/art/tools/rig_serpent.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_serpent_rig", "__file__": p,
                                               "SOURCE": "RodinSerpent", "SADDLE": "RodinSaddle", "STAGE": "adult"})
STAGE picks the life stage (baby, teen, adult, elder; see STAGES); only the adult has a saddle.

Reuses rig_generated_horse.py for clean-up (orient, scale, weld, decimate) and proxy skinning, and build_serpent.py
for the two lantern antennae, which stay separate meshes, as does the saddle. The body gets one chain of bones
traced along its centre line, rooted at the saddle so the rider stays steady while the wave runs down the tail.
Writes art/models/serpent/generated/serpent.glb (serpent-baby.glb and so on for the other stages) with Idle, Swim
and Dash. Every stage gets the same bone names and clips, so a game can swap models as the creature grows.
"""

import heapq
import math
import os

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_point_line

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = globals().get("SOURCE", "RodinSerpent")
SADDLE = globals().get("SADDLE", "RodinSaddle")
# Per life stage (art/models/serpent/growth-lantern-v1.png): length snout to tail tip stretched out (m), antenna
# size, how high every clip floats it (m), triangle budget, whether it wears the saddle, and the output name.
STAGES = {
    "baby": dict(length=0.7, antenna=0.2, hover=0.06, tris=8000, saddle=False, out="serpent-baby"),
    "teen": dict(length=2.5, antenna=0.7, hover=0.14, tris=12000, saddle=False, out="serpent-teen"),
    "adult": dict(length=5.0, antenna=1.15, hover=0.22, tris=14000, saddle=True, out="serpent"),
    # The elder's chin tendrils and coral defeat Blender's automatic weights, so it is weighted along its centre line.
    "elder": dict(length=6.0, antenna=1.35, hover=0.25, tris=24000, saddle=False, out="serpent-elder", aged=True,
                  weights="chain"),
}
STAGE = STAGES[globals().get("STAGE", "adult")]
LENGTH = STAGE["length"]  # the sheet's adult is about 6 m; a little less rides better
STATIONS = 28           # joints along the body, snout to tail tip
SADDLE_RANGE = (0.24, 0.42)  # where along the body (share of its length from the snout) the saddle may sit:
                             # behind the neck, which the Idle lifts into an S
ANTENNA_SCALE = STAGE["antenna"]
HOVER = STAGE["hover"]    # it swims through the air: every clip floats it this high above the ground
SIZE = LENGTH / 5.0       # offsets below were measured on the 5 m adult

_gen_path = os.path.join(HERE, "rig_generated_horse.py")
gen = {"__name__": "gm_rig_lib", "__file__": _gen_path, "SOURCE": SOURCE, "RUN": False}
exec(compile(open(_gen_path).read(), _gen_path, "exec"), gen)
lib = gen["lib"]
gen["SCENE"] = lib["SCENE"] = "GM Serpent"

lib["OUT"] = os.path.normpath(os.path.join(HERE, "..", "models", "serpent", "generated"))

_ant_path = os.path.join(HERE, "build_serpent.py")
ant = {"__name__": "gm_serpent_parts", "__file__": _ant_path, "RUN": False}
exec(compile(open(_ant_path).read(), _ant_path, "exec"), ant)

# Bone chains a game should simulate as springs (root first; three.js drops "." from names, so none are used).
SPRING_CHAINS = [["antennaL1", "antennaL2", "antennaL3"], ["antennaR1", "antennaR2", "antennaR3"]]


def remove_floaters(ob, gap):
    """Hyper3D sometimes adds a loose bead or bubble floating near the body. Delete every piece that stays more than
    `gap` metres away from the main body; pieces touching it or inside it (eyes, say) are kept. Returns the count."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    seen, parts = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        seen.add(v)
        stack, part = [v], []
        while stack:
            x = stack.pop()
            part.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        parts.append(part)
    parts.sort(key=len, reverse=True)
    main = set(parts[0])
    tree = BVHTree.FromPolygons([v.co for v in bm.verts], [[v.index for v in f.verts] for f in bm.faces
                                                           if all(v in main for v in f.verts)])
    dead = [v for part in parts[1:] if min(tree.find_nearest(v.co)[3] for v in part) > gap for v in part]
    count = sum(1 for part in parts[1:] if part[0] in dead)
    bmesh.ops.delete(bm, geom=dead, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return count


def geodesic(me, start):
    """Shortest distance along the surface's edges from vertex `start` to every vertex."""
    nbr = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        d = (me.vertices[a].co - me.vertices[b].co).length
        nbr[a].append((b, d))
        nbr[b].append((a, d))
    dist = [math.inf] * len(me.vertices)
    dist[start] = 0.0
    heap = [(0.0, start)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for w, step in nbr[v]:
            if d + step < dist[w]:
                dist[w] = d + step
                heapq.heappush(heap, (d + step, w))
    return dist


def resample(points, count):
    """`count` points at even spacing along a polyline."""
    seg = [(points[i + 1] - points[i]).length for i in range(len(points) - 1)]
    total = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(count):
        s = total * k / (count - 1)
        while i < len(seg) - 1 and acc + seg[i] < s:
            acc += seg[i]
            i += 1
        f = 0.0 if seg[i] == 0 else min(1.0, (s - acc) / seg[i])
        out.append(points[i].lerp(points[i + 1], f))
    return out, total


def medial_points(me, dist):
    """(distance along the surface, point on the axis, vertex, depth) for every skin point of the solid body. Each
    skin point casts a ray straight inward; where it meets the far wall, the midpoint lies on the axis. Fins are
    skipped: anything thinner than about a third of the body's typical thickness."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    out = []
    for v in me.vertices:
        if dist[v.index] == math.inf:
            continue
        n = v.normal
        hit = bvh.ray_cast(v.co - n * 0.002, -n, 0.8)
        if hit[0] is not None and (hit[0] - v.co).length > 0.01:
            out.append((dist[v.index], (v.co + hit[0]) / 2, v.index, (hit[0] - v.co).length))
    depths = sorted(m[3] for m in out)
    floor = 0.35 * depths[len(depths) // 2]
    return [m for m in out if m[3] > floor]


def centre_line(ob):
    """Joints from the snout to the tail tip along the body's axis. The body's two ends are the pair of points
    farthest apart along the surface; the head end is the wider one. Distances are then measured from the tail
    tip, so the solid point farthest from it is the snout. Axis points are averaged in short runs, smoothed and
    spaced evenly."""
    me = ob.data
    co = [v.co.copy() for v in me.vertices]
    seed = max(range(len(co)), key=lambda i: co[i].z)
    d0 = geodesic(me, seed)
    end_a = max((i for i in range(len(co)) if d0[i] < math.inf), key=lambda i: d0[i])
    da = geodesic(me, end_a)
    end_b = max((i for i in range(len(co)) if da[i] < math.inf), key=lambda i: da[i])
    # The head end is the wider one: a head has cheeks, eyes and side fins, while a tail fin is tall and flat.
    span = da[end_b]
    run = co[end_b] - co[end_a]
    run.z = 0
    across = Vector((-run.y, run.x, 0)).normalized()

    def width(near):
        pts = [co[i].dot(across) for i in range(len(co)) if near(da[i])]
        return max(pts) - min(pts) if pts else 0.0

    head_at_a = width(lambda d: d < 0.12 * span) > width(lambda d: span - 0.12 * span < d < math.inf)
    tail_tip = end_b if head_at_a else end_a
    dist = geodesic(me, tail_tip)
    mids = medial_points(me, dist)
    mids.sort(key=lambda m: m[0])
    length = mids[-1][0]
    runs = 60
    line = [co[tail_tip].copy()]
    for k in range(runs):
        lo, hi = length * k / runs, length * (k + 1) / runs
        pts = [m[1] for m in mids if lo <= m[0] < hi]
        if len(pts) < 3:
            continue
        mid = sum(pts, Vector()) / len(pts)
        spread = sorted((p - mid).length for p in pts)
        near = [p for p in pts if (p - mid).length <= spread[len(spread) // 2] * 1.6] or pts
        line.append(sum(near, Vector()) / len(near))
    # The last runs can come from a thick frill behind the head (farther along the surface than the snout); the
    # body's axis never doubles back, so cut the line where it does (looking only at the head end: the first
    # point, the tail fin's tip, sits off the axis).
    for k in range(max(2, 2 * len(line) // 3), len(line)):
        before, step = line[k - 1] - line[k - 2], line[k] - line[k - 1]
        if before.length > 1e-6 and step.length > 1e-6 and before.normalized().dot(step.normalized()) < -0.3:
            line = line[:k]
            break
    # The snout: the tip of the head straight ahead along the body's own direction there.
    ahead = (line[-1] - line[-5]).normalized()
    solid = {m[2] for m in mids}
    snout = max((i for i in solid if (co[i] - line[-1]).length < 0.12 * length), key=lambda i: (co[i] - line[-1]).dot(ahead))
    line.append(co[snout].copy())
    for _ in range(3):
        line = [line[0]] + [(line[i - 1] + line[i] * 2 + line[i + 1]) / 4 for i in range(1, len(line) - 1)] + [line[-1]]
    joints, total = resample(line[::-1], STATIONS + 1)
    return joints, total


def face_forward(ob, joints):
    """Turn the mesh about the vertical so the front of the body points along -Y, the way every GM model faces.
    Hyper3D keeps the input picture's facing. Returns the turned joints."""
    look = joints[0] - joints[len(joints) // 4]
    look.z = 0
    turn = Matrix.Rotation(-math.atan2(look.x, -look.y), 4, "Z")   # no turn when already looking down -Y
    ob.data.transform(turn)
    ob.data.update()
    return [turn @ j for j in joints]


def pick_saddle(joints):
    """The joint in SADDLE_RANGE where the body runs most nearly level (ties go to about a third of the way back),
    so the rider sits on a back and not on a rising neck."""
    n = len(joints) - 1
    best, score = None, math.inf
    for i in range(max(2, round(SADDLE_RANGE[0] * n)), min(n - 2, round(SADDLE_RANGE[1] * n)) + 1):
        d = (joints[i - 1] - joints[i + 1]).normalized()
        sc = abs(d.z) + 0.3 * abs(i / n - 0.33)
        if sc < score:
            best, score = i, sc
    return best


def build_bones(joints):
    """root -> spine at the saddle; the neck runs forward to the head, the tail back to its tip."""
    a = pick_saddle(joints)
    n = len(joints) - 1
    bones = [("root", (0, 0, 0), (0, 0.25, 0), None),
             ("spine", tuple(joints[a]), tuple(joints[a - 1]), "root")]
    # Where each bone sits along the body, 0 at the snout and 1 at the tail tip (its middle), for the animation.
    along = {"spine": (a - 0.5) / n}
    parent = "spine"
    forward = list(range(a - 1, 0, -1))
    for k, i in enumerate(forward):
        name = "head" if k == len(forward) - 1 else f"neck{k + 1}"
        bones.append((name, tuple(joints[i]), tuple(joints[i - 1]), parent))
        along[name] = (i - 0.5) / n
        parent = name
    parent = "spine"
    for k, i in enumerate(range(a, n)):
        name = f"tail{k + 1}"
        bones.append((name, tuple(joints[i]), tuple(joints[i + 1]), parent))
        along[name] = (i + 0.5) / n
        parent = name
    return bones, a, along


def surface_above(bvh, x, y, z_from=4.0):
    hit = bvh.ray_cast(Vector((x, y, z_from)), Vector((0, 0, -1)))
    return hit[0]


def place_antennae(sc, body, joints, length):
    """Two antennae from build_serpent.py, planted on the crown of the skull. Rays go from the head's axis
    outward, so the first surface they meet is always the skin itself, never coral or a frill growing on top."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)
    up = Vector((0, 0, 1))

    def wall(origin, direction):
        hit = bvh.ray_cast(origin, direction, length)
        return hit[0]

    # The crown: of the axis points in the head (the first 12% of the body, skipping the snout tip), the one with
    # the highest skin straight above it.
    step = length / (len(joints) - 1)
    head = [j for i, j in enumerate(joints) if 0.03 * length <= i * step <= 0.12 * length] or joints[1:3]
    crown = max(head, key=lambda j: (wall(j, up) or j).z)
    look = (joints[0] - crown)
    look.z = 0
    look.normalize()
    across = look.cross(up).normalized()
    half = min(((wall(crown, d) or crown) - crown).length for d in (across, -across))
    made = []
    for side, tag in ((1, "L"), (-1, "R")):
        name = "SerpentAntenna" + tag
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        ob, stalk = ant["build_antenna"](name, side, aged=STAGE.get("aged", False))
        sc.collection.objects.link(ob)
        # build_antenna's "left" is +X with the head facing -Y, which face_forward guarantees.
        foot = crown + Vector((side, 0, 0)) * half * 0.4
        top = wall(foot, up) or (crown + up * half)
        base = top - up * 0.02 * SIZE                # sink the stalk a little into the scalp
        ob.data.transform(Matrix.Translation(base) @ Matrix.Scale(ANTENNA_SCALE, 4))
        made.append((tag, ob, [base + j * ANTENNA_SCALE for j in stalk]))
    return made


def ring_hole(me):
    """Finds the saddle's ring. The saddle is mirror-symmetric left to right, so the body runs along the
    horizontal axis lying in its mirror plane. Rays cast through it along that axis over a grid leave an enclosed
    patch of misses: the hole the body goes through. Returns the axis (0 = X, 1 = Y), the hole's centre and its
    smaller width."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    co = [v.co for v in me.vertices]
    mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    centre = (mn + mx) / 2
    sample = co[::max(1, len(co) // 1500)]

    def mirror_error(k):
        err = 0.0
        for c in sample:
            m = c.copy()
            m[k] = 2 * centre[k] - m[k]
            err += bvh.find_nearest(m)[3]
        return err

    # Mirroring across X matching well means the mirror plane is YZ, so the body runs along Y.
    n = 48
    best = None
    for axis in ((1,) if mirror_error(0) < mirror_error(1) else (0,)):
        other = 1 - axis
        miss = set()
        for i in range(n):
            for j in range(n):
                u = mn[other] + (mx[other] - mn[other]) * (i + 0.5) / n
                z = mn.z + (mx.z - mn.z) * (j + 0.5) / n
                o = Vector((0, 0, z))
                o[other] = u
                o[axis] = mn[axis] - 1.0
                d = Vector((0, 0, 0))
                d[axis] = 1.0
                if bvh.ray_cast(o, d)[0] is None:
                    miss.add((i, j))
        # The hole is the patch of misses that never reaches the edge of the grid.
        seen, holes = set(), []
        for cell in miss:
            if cell in seen:
                continue
            stack, patch, edge = [cell], [], False
            seen.add(cell)
            while stack:
                ci, cj = stack.pop()
                patch.append((ci, cj))
                edge = edge or ci in (0, n - 1) or cj in (0, n - 1)
                for nb in ((ci + 1, cj), (ci - 1, cj), (ci, cj + 1), (ci, cj - 1)):
                    if nb in miss and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            if not edge:
                holes.append(patch)
        if holes:
            patch = max(holes, key=len)
            if best is None or len(patch) > len(best[1]):
                best = (axis, patch)
    axis, patch = best
    other = 1 - axis
    cu = (mx[other] - mn[other]) / n
    cz = (mx.z - mn.z) / n
    iu = [c[0] for c in patch]
    jz = [c[1] for c in patch]
    centre = Vector((0, 0, mn.z + (sum(jz) / len(jz) + 0.5) * cz))
    centre[other] = mn[other] + (sum(iu) / len(iu) + 0.5) * cu
    centre[axis] = (mn[axis] + mx[axis]) / 2
    width = min((max(iu) - min(iu) + 1) * cu, (max(jz) - min(jz) + 1) * cz)
    return axis, centre, width


def place_saddle(body, joints, a):
    """Threads the Hyper3D saddle's ring onto the body at the spine joint: the ring's axis along the body there,
    the hole sized to the body's thickness, the shell on top."""
    src = bpy.data.objects.get(SADDLE)
    if src is None:
        return None
    meshes = [src] if src.type == "MESH" else [o for o in src.children_recursive if o.type == "MESH"]
    for ob in meshes:
        ob.data = ob.data.copy()
        ob.data.transform(ob.matrix_world)
        ob.parent = None
        ob.matrix_world = Matrix.Identity(4)
    saddle = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=saddle, object=saddle, selected_objects=meshes, selected_editable_objects=meshes):
            bpy.ops.object.join()
    saddle.name = "SerpentSaddle"
    for c in list(saddle.users_collection):
        c.objects.unlink(saddle)
    bpy.context.window.scene.collection.objects.link(saddle)
    keep = gen["TARGET_TRIS"]
    gen["TARGET_TRIS"] = 6000
    gen["decimate"](saddle)
    gen["TARGET_TRIS"] = keep
    me = saddle.data
    axis, hole, width = ring_hole(me)
    # Local frame: the ring's axis becomes +Y, up stays up, the hole's centre at the origin.
    me.transform(Matrix.Translation(-hole))
    if axis == 0:
        me.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
    # The body at the saddle: its direction (toward the head) and thickness across it.
    d = (joints[a - 1] - joints[a + 1]).normalized()
    ring = [v.co for v in body.data.vertices if abs((v.co - joints[a]).dot(d)) < 0.04]
    radii = sorted(((v - joints[a]) - d * (v - joints[a]).dot(d)).length for v in ring)
    thick = 2 * radii[len(radii) // 2] if radii else 0.3
    s = thick * 1.08 / width
    x = d.cross(Vector((0, 0, 1)))
    x = x.normalized() if x.length > 1e-4 else Vector((1, 0, 0))
    z = x.cross(d).normalized()
    turn = Matrix((x, d, z)).transposed().to_4x4()      # local X, Y (ring axis), Z to world
    me.transform(Matrix.Translation(joints[a]) @ turn @ Matrix.Scale(s, 4))
    me.update()
    return saddle


def nearest_bone_weights(ob, rig, names):
    """Rigid-ish skinning for the small parts: each vertex goes wholly to the nearest of `names`."""
    ob.vertex_groups.clear()
    groups = {n: ob.vertex_groups.new(name=n) for n in names}
    segs = [(n, rig.data.bones[n].head_local, rig.data.bones[n].tail_local) for n in names]
    for v in ob.data.vertices:
        def dist(seg):
            _, h, t = seg
            p, f = intersect_point_line(v.co, h, t)
            return (v.co - (h if f < 0 else t if f > 1 else p)).length
        groups[min(segs, key=dist)[0]].add([v.index], 1.0, "REPLACE")
    ob.parent = rig
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = rig


def chain_skin(ob, rig, joints):
    """Weights for a body that is one long tube: each point of the solid body belongs to the bone at its nearest
    spot on the centre line, blended half and half with the neighbouring bone at each joint; everything growing off
    it takes the weights of where it attaches. Works however thin or tangled the fins, tendrils and coral are."""
    seg_bone = {}
    for b in rig.data.bones:
        if b.name == "root" or b.name.startswith("antenna"):
            continue
        mid = (b.head_local + b.tail_local) / 2
        seg_bone[min(range(len(joints) - 1), key=lambda k: ((joints[k] + joints[k + 1]) / 2 - mid).length)] = b.name
    ob.vertex_groups.clear()
    groups = {n: ob.vertex_groups.new(name=n) for n in seg_bone.values()}
    last = len(joints) - 2
    me = ob.data
    solid = {m[2] for m in medial_points(me, [0.0] * len(me.vertices))}
    weights = {}
    for v in me.vertices:
        if v.index not in solid:
            continue
        best = None
        for k in range(last + 1):
            _, f = intersect_point_line(v.co, joints[k], joints[k + 1])
            f = min(1.0, max(0.0, f))
            d = (v.co - joints[k].lerp(joints[k + 1], f)).length
            if best is None or d < best[0]:
                best = (d, k, f)
        _, k, t = best
        other, share = None, 0.0
        if t < 0.5 and k > 0:
            other, share = k - 1, 0.5 * (1 - t / 0.5)
        elif t >= 0.5 and k < last:
            other, share = k + 1, 0.5 * ((t - 0.5) / 0.5)
        weights[v.index] = {seg_bone[k]: 1.0 - share}
        if other is not None and share > 0:
            weights[v.index][seg_bone[other]] = share
    # Fins, tendrils and coral copy the weights of the body point they grow from: the nearest solid point
    # along the surface. A chin tendril then moves with the chin, not with whatever part of the neck it hangs near.
    nbr = [[] for _ in me.vertices]
    for e in me.edges:
        i, j = e.vertices
        d = (me.vertices[i].co - me.vertices[j].co).length
        nbr[i].append((j, d))
        nbr[j].append((i, d))
    root = {i: i for i in weights}
    best = {i: 0.0 for i in weights}
    heap = [(0.0, i) for i in weights]
    heapq.heapify(heap)
    while heap:
        d, i = heapq.heappop(heap)
        if d > best.get(i, math.inf):
            continue
        for j, step in nbr[i]:
            if d + step < best.get(j, math.inf):
                best[j] = d + step
                root[j] = root[i]
                heapq.heappush(heap, (d + step, j))
    fallback = {seg_bone[0]: 1.0}
    for v in me.vertices:
        for name, w in weights.get(root.get(v.index), fallback).items():
            groups[name].add([v.index], w, "REPLACE")
    ob.parent = rig
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = rig


def limit_influences(ob, keep=4):
    """glTF carries 4 bone weights per vertex; keep the strongest 4 so Blender and the game deform alike."""
    for v in ob.data.vertices:
        weakest = [g.group for g in sorted(v.groups, key=lambda g: -g.weight)[keep:]]
        for gi in weakest:
            ob.vertex_groups[gi].remove([v.index])
        total = sum(g.weight for g in v.groups)
        if total > 0:
            for g in v.groups:
                g.weight /= total


# ---------- animation: lateral waves about the world vertical, keyed as quaternions

def key_clip(rig, name, frames, pose_at):
    ad = rig.animation_data or rig.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ad.action = act
    for f in range(frames + 1):
        pose = pose_at(f / frames)
        for pb in rig.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = pose.get(pb.name, Quaternion())
            pb.keyframe_insert("rotation_quaternion", frame=f + 1)
        root = rig.pose.bones["root"]
        root.location = (0.0, 0.0, HOVER + pose.get("_bob", 0.0))
        root.keyframe_insert("location", frame=f + 1)
    track = ad.nla_tracks.new()
    track.name = name
    track.strips.new(name, 1, act)
    ad.action = None


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def animate(rig, along):
    """Every clip is a wave of bends travelling from the neck to the tail tip: sideways (about the world vertical)
    and a smaller up-and-down roll, growing toward the tail. The bones are rooted at the saddle, so neck bones
    point toward the head and tail bones toward the tail; a neck bone bends the opposite way to keep one wave.
    On top of the wave each clip has a pose: the Idle lifts the neck into an S, the swims keep it low."""
    bpy.context.scene.render.fps = lib["FPS"]
    bones = rig.data.bones
    up, side = {}, {}
    for b in bones:
        inv = b.matrix_local.to_3x3().inverted()
        d = (b.tail_local - b.head_local).normalized()
        s = d.cross(Vector((0, 0, 1)))
        up[b.name] = inv @ Vector((0, 0, 1))
        # Turning about this axis by +a lifts the bone's far end.
        side[b.name] = inv @ (s.normalized() if s.length > 1e-4 else Vector((1, 0, 0)))
    neck = sorted((n for n in along if n.startswith("neck")), key=lambda n: int(n[4:])) + ["head"]
    tail = sorted((n for n in along if n.startswith("tail")), key=lambda n: int(n[4:]))
    a = along["spine"]

    def clip(t, amp, waves, roll, lift, curl, bob):
        """amp: sideways bend per bone at the tail (rad); waves: waves along the body; roll: up-and-down share;
        lift(name) -> that neck bone's steady lift (rad); curl: steady sideways curl of the tail."""
        pose = {}
        yaw_sum = pitch_sum = 0.0
        for n in neck[:-1] + tail:
            u = along[n]
            sign = -1 if n in neck else 1
            g = amp * (0.15 + 0.85 * smoothstep(0.0, 1.0, u))      # small near the head, full at the tail
            ph = math.tau * (t - waves * u)
            yaw = sign * g * math.sin(ph)
            pitch = sign * g * roll * math.sin(ph + math.pi / 2)
            if n in neck:
                pitch += lift(n)
                yaw_sum += yaw
                pitch_sum += pitch
            else:
                yaw += curl * smoothstep(a, 1.0, u)
            pose[n] = Quaternion(up[n], yaw) @ Quaternion(side[n], pitch)
        # The head turns back against the neck's bends, so it keeps looking ahead.
        pose["head"] = Quaternion(up["head"], -0.8 * yaw_sum) @ Quaternion(side["head"], -0.6 * pitch_sum)
        pose["spine"] = Quaternion(up["spine"], 0.25 * amp * math.sin(math.tau * (t - waves * a)))
        pose["_bob"] = bob * math.sin(math.tau * t)
        return pose

    # Steady neck shapes, spread smoothly over the neck so no joint folds: a share of the turn goes up over the
    # first part of the neck and back down over the last part, which leaves the head looking ahead.
    reach = {n: 1 - along[n] / a for n in neck[:-1]}          # 0 at the saddle .. 1 at the head

    def shape(up_deg, down_deg):
        def bump(v, lo, hi):
            return math.sin(math.pi * min(1.0, max(0.0, (v - lo) / (hi - lo))))
        rise = {n: bump(v, 0.0, 0.6) for n, v in reach.items()}
        fall = {n: bump(v, 0.45, 1.0) for n, v in reach.items()}
        sr, sf = sum(rise.values()) or 1.0, sum(fall.values()) or 1.0
        return lambda n: math.radians(up_deg) * rise[n] / sr - math.radians(down_deg) * fall[n] / sf

    rear, stream, dash = shape(70, 55), shape(4, 10), shape(0, 10)

    key_clip(rig, "Idle", 96, lambda t: clip(t, 0.05, 0.8, 0.5, rear, 0.05, 0.035))
    key_clip(rig, "Swim", 40, lambda t: clip(t, 0.16, 1.3, 0.35, stream, 0.0, 0.03))
    key_clip(rig, "Dash", 24, lambda t: clip(t, 0.23, 1.4, 0.3, dash, 0.0, 0.04))


def run():
    # collect_source rebuilds the "GM Serpent" scene, which it can only do while another scene is showing. Come
    # back to that scene at the end: add-on settings live on the scene (the Blender MCP's Hyper3D switch is one),
    # and a freshly built scene has them all off.
    if bpy.context.window.scene.name == "GM Serpent":
        bpy.context.window.scene = next(s for s in bpy.data.scenes if s.name != "GM Serpent")
    home = bpy.context.window.scene.name
    sc, coll, body = gen["collect_source"]()
    body.name, coll.name = "SerpentBody", "Serpent"
    gen["orient_and_scale"](body)
    # orient_and_scale sizes by height; a stretched-out serpent is sized by length instead.
    co = [v.co for v in body.data.vertices]
    reach = max(max(c.x for c in co) - min(c.x for c in co), max(c.y for c in co) - min(c.y for c in co))
    body.data.transform(Matrix.Scale(LENGTH / reach, 4))
    body.data.update()
    gen["TARGET_TRIS"] = STAGE["tris"]
    tris = gen["decimate"](body)
    floaters = remove_floaters(body, 0.005 * LENGTH)
    joints, length = centre_line(body)
    joints = face_forward(body, joints)
    lib["BONES"][:], a, along = build_bones(joints)
    antennae = place_antennae(sc, body, joints, length)
    saddle = place_saddle(body, joints, a) if STAGE["saddle"] else None
    for tag, ob, stalk in antennae:
        for i in range(3):
            lib["BONES"].append((f"antenna{tag}{i + 1}", tuple(stalk[i]), tuple(stalk[i + 1]), "head" if i == 0 else f"antenna{tag}{i}"))
    rig = lib["armature"](coll)
    rig.name = "SerpentRig"
    if STAGE.get("weights") == "chain":
        chain_skin(body, rig, joints)
    else:
        gen["skin_via_proxy"](rig, body)
    # The antennae are separate meshes with their own bones; their weight on the scalp goes to the head.
    head_group = body.vertex_groups["head"]
    for g in [g for g in body.vertex_groups if g.name.startswith("antenna")]:
        for v in body.data.vertices:
            w = next((x.weight for x in v.groups if x.group == g.index), 0.0)
            if w > 0:
                have = next((x.weight for x in v.groups if x.group == head_group.index), 0.0)
                head_group.add([v.index], have + w, "REPLACE")
        body.vertex_groups.remove(g)
    limit_influences(body)
    for tag, ob, stalk in antennae:
        nearest_bone_weights(ob, rig, [f"antenna{tag}{i + 1}" for i in range(3)])
    if saddle is not None:
        saddle.parent = rig
        saddle.parent_type = "BONE"
        saddle.parent_bone = "spine"
        saddle.matrix_parent_inverse = (rig.matrix_world @ Matrix.Translation(rig.data.bones["spine"].tail_local)
                                        @ rig.data.bones["spine"].matrix_local.to_3x3().to_4x4()).inverted()
    animate(rig, along)
    gen["rest_pose"](rig, False)
    os.makedirs(lib["OUT"], exist_ok=True)
    lib["export"](sc, rig)
    out = lib["OUT"]
    for ext in ("glb", "blend"):
        src, dst = os.path.join(out, f"horse.{ext}"), os.path.join(out, f"{STAGE['out']}.{ext}")
        if os.path.exists(src):
            os.replace(src, dst)
    bpy.context.window.scene = bpy.data.scenes[home]
    return {"triangles": tris, "floaters_removed": floaters, "length_m": round(length, 2), "bones": len(lib["BONES"]), "saddle_joint": a,
            "saddle": saddle is not None}


if globals().get("RUN", True):
    print("GM Abyssal Lantern Serpent:", run())

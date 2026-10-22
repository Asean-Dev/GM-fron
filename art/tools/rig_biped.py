"""Turns the AI-generated Thunder Plume Runner (Hyper3D Rodin, from art/models/biped/model-sheet-thunder-v1.png)
into a game-ready two-legged mount.

Run inside Blender after importing the generated asset, with p pointing at this file in your clone:
    p = "/path/to/GM-fron/art/tools/rig_biped.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_biped", "__file__": p, "SOURCE": "RodinThunder"})

Reuses rig_generated_horse.py for clean-up (orient, scale, decimate) and proxy skinning, and build_horse.py for
the armature, keying, preview and export. Adds its own two-legged skeleton with separate bone chains for the
crest, the tail fan and the arm feathers, so a game can run feather physics on them (see FEATHER_CHAINS),
and its own Idle / Walk / Run actions. Writes art/models/biped/generated/thunder.glb.
"""

import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = globals().get("SOURCE", "RodinThunder")
HEIGHT = 1.95   # crest tip, from the sheet's scale bar

_gen_path = os.path.join(HERE, "rig_generated_horse.py")
gen = {"__name__": "gm_rig_lib", "__file__": _gen_path, "SOURCE": SOURCE, "RUN": False}
exec(compile(open(_gen_path).read(), _gen_path, "exec"), gen)
lib = gen["lib"]
gen["SCENE"] = lib["SCENE"] = "GM Thunder"
gen["HEIGHT"] = HEIGHT
lib["OUT"] = os.path.normpath(os.path.join(HERE, "..", "models", "biped", "generated"))

# Bone chains a game should simulate as springs (root first). Exported as plain bones; physics is runtime.
FEATHER_CHAINS = [
    ["crestF1", "crestF2"], ["crestU1", "crestU2"], ["crestB1", "crestB2", "crestB3"],
    ["tailU1", "tailU2", "tailU3"], ["tailC1", "tailC2", "tailC3"], ["tailD1", "tailD2", "tailD3"],
    ["featherArm.L"], ["featherArm.R"],
]

# Template skeleton at full height, feet centred on y = 0, facing -Y. (name, head, tail, parent)
TEMPLATE = [
    ("root", (0, 0, 0), (0, 0.25, 0), None),
    ("pelvis", (0, 0.12, 0.82), (0, -0.12, 0.86), "root"),
    ("spine", (0, -0.12, 0.86), (0, -0.38, 0.92), "pelvis"),
    ("chest", (0, -0.38, 0.92), (0, -0.52, 1.12), "spine"),
    ("neck1", (0, -0.52, 1.12), (0, -0.55, 1.32), "chest"),
    ("neck2", (0, -0.55, 1.32), (0, -0.6, 1.5), "neck1"),
    ("head", (0, -0.6, 1.5), (0, -0.9, 1.52), "neck2"),
]
# The crest fans from the top of the head: front, up and back chains, placed by measure_fan.
for _k, _n in (("F", 2), ("U", 2), ("B", 3)):
    TEMPLATE += [("crest" + _k + str(i + 1), (0, -0.6, 1.7), (0, -0.5, 1.8), "head" if i == 0 else "crest" + _k + str(i))
                 for i in range(_n)]
# The tail is an upright plume: upper, middle and lower (drooping) chains, placed by measure_fan.
for _k in "UCD":
    TEMPLATE += [("tail" + _k + "1", (0, 0.32, 1.12), (0, 0.5, 1.1), "pelvis"),
                 ("tail" + _k + "2", (0, 0.5, 1.1), (0, 0.7, 1.0), "tail" + _k + "1"),
                 ("tail" + _k + "3", (0, 0.7, 1.0), (0, 0.9, 0.9), "tail" + _k + "2")]
for _sx, _s in ((1, "L"), (-1, "R")):
    TEMPLATE += [
        ("armUpper." + _s, (_sx * 0.22, -0.45, 0.88), (_sx * 0.27, -0.55, 0.68), "chest"),
        ("armLower." + _s, (_sx * 0.27, -0.55, 0.68), (_sx * 0.26, -0.62, 0.5), "armUpper." + _s),
        ("featherArm." + _s, (_sx * 0.27, -0.6, 0.6), (_sx * 0.3, -0.5, 0.4), "armLower." + _s),
        ("thigh." + _s, (_sx * 0.17, 0.1, 0.66), (_sx * 0.18, -0.04, 0.44), "pelvis"),
        ("shin." + _s, (_sx * 0.18, -0.04, 0.44), (_sx * 0.18, 0.08, 0.24), "thigh." + _s),
        ("foot." + _s, (_sx * 0.18, 0.08, 0.24), (_sx * 0.18, 0.0, 0.05), "shin." + _s),
        ("toe." + _s, (_sx * 0.18, 0.0, 0.05), (_sx * 0.18, -0.2, 0.0), "foot." + _s),
    ]


def remove_ghosts(ob):
    """Hyper3D guesses the hidden leg from a single picture and sometimes adds a loose extra foot on each side.
    Weld the UV-seam splits so the creature is one piece, then delete every loose piece except the main one."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
    seen, islands = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        seen.add(v)
        stack, island = [v], []
        while stack:
            x = stack.pop()
            island.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        islands.append(island)
    main = max(islands, key=len)
    dead = [v for island in islands if island is not main for v in island]
    bmesh.ops.delete(bm, geom=dead, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(dead)


def symmetrize(ob):
    """Mirror the left half (+X) onto the right. Hyper3D builds the creature mid-stride from one picture, so its
    two legs come out in different poses; a mirrored copy gives two identical legs that rig and walk the same.
    (The right saddle flap then shows the left one's decoration, mirrored.)"""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction="X", dist=0.002)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def trace_leg(co, s):
    """Centre line of one leg, walking up from just above the toes and only following points near the last one,
    so loose feathers or the other leg never pull it off course."""
    pts, cur, z = [], None, 0.2
    while z <= 0.63:
        sl = [c for c in co if abs(c.z - z) < 0.025 and 0.1 < c.x * s < 0.42 and -0.4 < c.y < 0.35]
        if cur is not None:
            sl = [c for c in sl if abs(c.y - cur.y) < 0.1 and abs(c.x - cur.x) < 0.1]
        if not sl:
            break
        cur = sum(sl, Vector()) / len(sl)
        pts.append(cur)
        z += 0.04
    return pts


def measure_leg(co, s):
    line = trace_leg(co, s)
    at = lambda z: min(line, key=lambda p: abs(p.z - z))
    top, ankle, low = line[-1], at(0.46), at(0.22)
    # The bare lower leg (tarsus) runs straight on down to the ball of the foot.
    ball = ankle + (low - ankle) * ((ankle.z - 0.06) / (ankle.z - low.z))
    foot = [c for c in co if c.z < 0.1 and c.x * s > 0.1 and (c.xy - ball.xy).length < 0.4]
    front = min(c.y for c in foot)
    tip_x = sum(c.x for c in foot if c.y < front + 0.08) / len([c for c in foot if c.y < front + 0.08])
    return {
        "hip": Vector((s * 0.14, top.y + 0.04, 0.8)),
        "knee": Vector((top.x, top.y - 0.06, top.z + 0.02)),
        "ankle": ankle,
        "ball": Vector((ball.x, ball.y, 0.06)),
        "tip": Vector((tip_x, front + 0.03, 0.02)),
    }


def measure_arm(co, s):
    pts = [c for c in co if c.x * s > 0.12 and c.y < -0.28 and 0.42 < c.z < 0.95]
    x = sum(abs(c.x) for c in pts) / len(pts)
    y = sum(c.y for c in pts) / len(pts)
    lo = min(c.z for c in pts)
    return {"shoulder": Vector((s * 0.2, y + 0.14, lo + 0.41)), "elbow": Vector((s * x, y - 0.02, lo + 0.21)),
            "wrist": Vector((s * x, y - 0.1, lo + 0.05)),
            "feather": (Vector((s * (x + 0.03), y + 0.06, lo + 0.19)), Vector((s * (x + 0.03), y + 0.18, lo + 0.02)))}


def measure_fan(co, root, sectors, keep):
    """Fan bone chains through a spray of feathers by side angle around root. sectors: (key, from, to, bones),
    angles in radians (0 = straight back, pi/2 = up). Each joint sits at the centre of the feathers at that
    distance, so the chains follow the feathers' curve."""
    pts = []
    for c in co:
        if keep(c):
            d = c - root
            pts.append((math.atan2(d.z, d.y), Vector((0, d.y, d.z)).length, c))
    chains = {}
    for key, lo, hi, count in sectors:
        sector = sorted(((r, c) for a, r, c in pts if lo <= a < hi), key=lambda p: p[0])
        reach = sector[int(len(sector) * 0.97)][0]
        joints = [root]
        for i in range(1, count + 1):
            band = [c for r, c in sector if abs(r - i / count * reach) < 0.07]
            j = sum(band, Vector()) / len(band)
            joints.append(Vector((0, j.y, j.z)))
        chains[key] = joints
    return chains


def measure(ob):
    co = [v.co.copy() for v in ob.data.vertices]
    front = min(c.y for c in co)
    avg = lambda pts, f, d=0.0: sum(f(p) for p in pts) / len(pts) if pts else d
    head_pts = [c for c in co if 1.3 < c.z < 1.7 and c.y < front + 0.45]
    head = Vector((0, avg(head_pts, lambda p: p.y, -0.68), avg(head_pts, lambda p: p.z, 1.55)))
    # Template body bones shift with the chest: its front, low on the midline, sits 0.625 m ahead of the offset.
    dy = min(c.y for c in co if abs(c.z - 0.9) < 0.04 and abs(c.x) < 0.08) + 0.625
    legs = {"L": measure_leg(co, 1), "R": measure_leg(co, -1)}
    # The AI model stands mid-stride, so the thighs disagree; real hip joints sit level with each other.
    hip_y = (legs["L"]["hip"].y + legs["R"]["hip"].y) / 2
    for g in legs.values():
        g["hip"].y = hip_y
    tail_root, crest_root = Vector((0, 0.32 + dy, 1.12)), Vector((0, head.y + 0.11, head.z + 0.11))
    tail = measure_fan(co, tail_root, [("U", 0.45, 4.0, 3), ("C", -0.35, 0.45, 3), ("D", -4.0, -0.35, 3)],
                       lambda c: abs(c.x) < 0.15 and c.y > tail_root.y + 0.1)
    # The crest mostly sweeps back over the head; the beak and neck stay out (below or in front of the fan).
    crest = measure_fan(co, crest_root, [("B", -0.8, 0.52, 3), ("U", 0.52, 1.57, 2), ("F", 1.57, 3.2, 2)],
                        lambda c: c.z > 1.5 and c.y > crest_root.y - 0.3 and (c - crest_root).length > 0.06)
    return {"foot_y": dy, "head": head, "tail": tail, "crest": crest, "legs": legs,
            "arms": {"L": measure_arm(co, 1), "R": measure_arm(co, -1)}}


def remove_stray_legs(ob, m):
    """The same guessing can leave the stump of a third leg hanging under the body, attached to it. Between the
    feet and the belly, delete everything that isn't along a measured leg (arms sit further forward, the tail
    further back), then cap the opening it leaves."""
    import bmesh
    from mathutils.geometry import intersect_point_line
    segs = []
    for g in m["legs"].values():
        pts = [g["hip"], g["knee"], g["ankle"], g["ball"], g["tip"]]
        segs += list(zip(pts, pts[1:]))

    def near_leg(co):
        for h, t in segs:
            p, f = intersect_point_line(co, h, t)
            if (co - (h if f < 0 else t if f > 1 else p)).length < 0.16:
                return True
        return False

    bm = bmesh.new()
    bm.from_mesh(ob.data)
    dead = {v for v in bm.verts if 0.15 < v.co.z < 0.5 and abs(v.co.x) > 0.08 and -0.28 < v.co.y < 0.35
            and not near_leg(v.co)}
    rim = {o for v in dead for e in v.link_edges for o in e.verts if o not in dead}
    bmesh.ops.delete(bm, geom=list(dead), context="VERTS")
    edges = [e for e in bm.edges if e.is_boundary and all(v in rim for v in e.verts)]
    bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(dead)


def fit(m):
    dy = m["foot_y"]
    t_head = Vector((0, -0.68 + dy, 1.55))
    head_shift = m["head"] - t_head
    pull = {"neck1": (0.0, 0.5), "neck2": (0.5, 1.0), "head": (1.0, 1.0)}
    # Limbs and tail come straight from the measurements; the template only supplies the body, neck and crest.
    limbs = {}
    for prefix in ("tail", "crest"):
        for key, joints in m[prefix].items():
            for i in range(len(joints) - 1):
                limbs[f"{prefix}{key}{i + 1}"] = (joints[i], joints[i + 1])
    for side in ("L", "R"):
        g, a = m["legs"][side], m["arms"][side]
        limbs.update({
            "thigh." + side: (g["hip"], g["knee"]), "shin." + side: (g["knee"], g["ankle"]),
            "foot." + side: (g["ankle"], g["ball"]), "toe." + side: (g["ball"], g["tip"]),
            "armUpper." + side: (a["shoulder"], a["elbow"]), "armLower." + side: (a["elbow"], a["wrist"]),
            "featherArm." + side: a["feather"],
        })
    bones = []
    for name, h, t, parent in TEMPLATE:
        if name in limbs:
            h, t = limbs[name]
            bones.append((name, tuple(h), tuple(t), parent))
            continue
        h, t = Vector(h) + Vector((0, dy, 0)), Vector(t) + Vector((0, dy, 0))
        if name in pull:
            h += head_shift * pull[name][0]
            t += head_shift * pull[name][1]
        bones.append((name, tuple(h), tuple(t), parent))
    return bones


# How far (m) each limb, tail and crest bone may pull the surface around it; beyond that the body owns it.
# The tail and crest are wide fans of feathers, so they reach further.
LIMB_REACH = {"thigh": 0.14, "shin": 0.15, "foot": 0.17, "toe": 0.24, "armUpper": 0.24, "armLower": 0.24,
              "featherArm": 0.26, "tail": 0.35, "crest": 0.3}


def reach_of(name):
    """LIMB_REACH entry for a bone: thigh.L -> thigh, tailU2 -> tail, crestB1 -> crest."""
    base = name.split(".")[0].rstrip("0123456789")
    if base[:-1] in ("tail", "crest"):
        base = base[:-1]
    return LIMB_REACH.get(base)


def cap_limb_weights(ob, rig):
    """Proxy weighting leaks bones onto nearby parts (the drooping tail feathers caught the legs, the back of the
    legs caught the tail tip, the body sides caught the arms). Over the outer 40% of each bone's reach its weight
    fades into the nearest bone that fully reaches the spot, so the skin there bends softly instead of tearing; a
    vertex left with nothing goes to the nearest bone that can still reach it."""
    from mathutils.geometry import intersect_point_line

    def dist(co, b):
        p, f = intersect_point_line(co, b.head_local, b.tail_local)
        return (co - (b.head_local if f < 0 else b.tail_local if f > 1 else p)).length

    bones = {b.name: b for b in rig.data.bones if b.use_deform}
    reach = {n: reach_of(n) for n in bones}
    names = {g.index: g.name for g in ob.vertex_groups}
    trunk = [b for n, b in bones.items() if reach[n] is None]
    moved = 0
    for v in ob.data.vertices:
        fade = {}
        for g in v.groups:
            r = reach.get(names[g.group])
            if r:
                k = 1 - smooth((dist(v.co, bones[names[g.group]]) - 0.6 * r) / (0.4 * r))
                if k < 1:
                    fade[g.group] = (g.weight, k)
        if not fade:
            continue
        moved += 1
        # The faded share goes to the nearest bone that fully reaches this spot (the tarsus for a leg, not the pelvis).
        near = trunk + [b for n, b in bones.items() if reach[n] and dist(v.co, b) <= 0.6 * reach[n]]
        body = min(near, key=lambda b: dist(v.co, b)).name
        handed = 0.0
        for gi, (w, k) in fade.items():
            if k <= 0:
                ob.vertex_groups[gi].remove([v.index])
            else:
                ob.vertex_groups[gi].add([v.index], w * k, "REPLACE")
            handed += w * (1 - max(k, 0))
        if handed > 0 and sum(g.weight for g in v.groups) > 0.05:
            current = next((g.weight for g in v.groups if names[g.group] == body), 0.0)
            ob.vertex_groups[body].add([v.index], current + handed, "REPLACE")
        total = sum(g.weight for g in v.groups)
        if total < 0.05:
            near = trunk + [b for n, b in bones.items() if reach[n] and dist(v.co, b) <= reach[n]]
            nearest = min(near, key=lambda b: dist(v.co, b))
            ob.vertex_groups[nearest.name].add([v.index], 1.0, "REPLACE")
        else:
            for g in v.groups:
                g.weight /= total
    return moved


# Gaits are keyed with foot IK so planted feet don't slide. Lengths in metres, angles in radians.
#   frames: frames per cycle (30 fps)   duty: share of the cycle each foot is down   stride: how far a planted foot
#   travels back   crouch/bob: body lowered / bounce   ankle_lift: how high the ankle rises in the swing
#   fold: how far the tarsus folds the foot up behind it in the swing   curl: toe curl in swing
#   peel: how far the heel rolls up over the toes before push-off
GAITS = {
    "Walk": dict(frames=32, duty=0.6, stride=0.7, crouch=0.03, bob=0.018, ankle_lift=0.05, fold=0.8, curl=0.9, peel=0.35),
    "Run": dict(frames=16, duty=0.33, stride=0.66, crouch=0.05, bob=0.04, ankle_lift=0.06, fold=1.3, curl=1.2, peel=0.5),
}


def gait_speed(g):
    """Ground speed (m/s) that matches a gait's stride; the clips play in place, so the game moves the mount at this."""
    return g["stride"] / (g["duty"] * g["frames"] / lib["FPS"])


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def side_angle(v):
    """Angle of a vector seen from the side (Y back, Z up). Rotating a bone about X by +a adds a: up turns
    forward, forward turns down, down turns back."""
    return math.atan2(v.z, v.y)


def wrap(a):
    return (a + math.pi) % math.tau - math.pi


def posed(rig, pose, bob, name, memo):
    """Armature-space matrix of a bone for a pose dict, worked out the way Blender does (no scene update)."""
    if name in memo:
        return memo[name]
    b = rig.data.bones[name]
    basis = Euler(pose.get(name, (0.0, 0.0, 0.0)), "XYZ").to_matrix().to_4x4()
    if name == "root":
        basis = Matrix.Translation((0, 0, bob)) @ basis
    m = b.matrix_local @ basis if b.parent is None else \
        posed(rig, pose, bob, b.parent.name, memo) @ (b.parent.matrix_local.inverted() @ b.matrix_local) @ basis
    memo[name] = m
    return m


def leg_rest(rig, side):
    bones = rig.data.bones
    hip, ankle = bones["thigh." + side].head_local, bones["foot." + side].head_local
    ball, tip = bones["foot." + side].tail_local, bones["toe." + side].tail_local
    return {"side": side, "hip": hip.copy(), "ball": ball.copy(), "tip": tip.copy(),
            "foot_len": bones["foot." + side].length, "toe_dy": ball.y - tip.y,
            "toe_reach": Vector((0, ball.y - tip.y, ball.z - tip.z)).length,
            "toe_up": math.atan2(ball.z - tip.z, ball.y - tip.y),
            "tarsus": side_angle(ball - ankle), "tarsus_dx": (ball.x - ankle.x) / bones["foot." + side].length,
            "hip_ball": side_angle(ball - hip),
            "l1": bones["thigh." + side].length, "l2": bones["shin." + side].length, "l3": bones["foot." + side].length}


def planted(q, g, leg, home):
    """Ball and toe tip of a foot on the ground, q from touchdown (0) to push-off (1): the toe tip is planted and
    slides back at ground speed; near push-off the heel rolls up over it."""
    tip = Vector((leg["ball"].x, home + g["stride"] * (q - 0.5) - leg["toe_dy"], leg["tip"].z))
    a = leg["toe_up"] + g["peel"] * smooth((q - 0.65) / 0.35)
    return tip + Vector((0, math.cos(a), math.sin(a))) * leg["toe_reach"], tip


def tarsus_dir(leg, phi):
    """Ankle-to-ball direction at side angle phi, keeping the tarsus' sideways lean from the rest pose."""
    sp = math.sqrt(max(0.0, 1 - leg["tarsus_dx"] ** 2))
    return Vector((leg["tarsus_dx"], sp * math.cos(phi), sp * math.sin(phi)))


def stance_ankle(leg, ball, hip):
    """The tarsus hangs from a planted ball at a natural angle (leaning with the leg), turned just enough to keep
    the ankle within reach of the hip. Returns the ankle and the tarsus angle."""
    reach = 0.995 * (leg["l1"] + leg["l2"])
    phi = leg["tarsus"] + 0.8 * wrap(side_angle(ball - leg["hip"]) - leg["hip_ball"])
    at = lambda f: ball - tarsus_dir(leg, f) * leg["l3"]
    for _ in range(60):
        if (at(phi) - hip).length <= reach:
            break
        phi += 0.02 if (at(phi + 0.02) - hip).length < (at(phi - 0.02) - hip).length else -0.02
    return at(phi), phi


def leg_targets(rig, pose, bob, leg, g, p, home):
    """Ankle, ball and toe tip for one leg at phase p (0 = touchdown); g None means standing at rest. In the swing
    the ankle travels forward at about the same height while the tarsus folds the foot up behind it, as a bird
    does, so the knee never has to crumple; the toes curl under and open again for the landing."""
    hip = posed(rig, pose, bob, "thigh." + leg["side"], {}).translation
    if g is None:
        ankle, _ = stance_ankle(leg, leg["ball"], hip)
        return ankle, leg["ball"], leg["tip"]
    d = g["duty"]
    if p < d:
        ball, tip = planted(p / d, g, leg, home)
        return stance_ankle(leg, ball, hip)[0], ball, tip
    s = (p - d) / (1 - d)
    (b0, t0), (b1, t1) = planted(1.0, g, leg, home), planted(0.0, g, leg, home)
    (a0, f0), (a1, f1) = stance_ankle(leg, b0, hip), stance_ankle(leg, b1, hip)
    ankle = a0 + (a1 - a0) * smooth(s) + Vector((0, 0, g["ankle_lift"] * math.sin(math.pi * s)))
    ball = ankle + tarsus_dir(leg, f0 + (f1 - f0) * s + g["fold"] * math.sin(math.pi * s)) * leg["l3"]
    c0, c1 = side_angle(t0 - b0), side_angle(t1 - b1)
    c = c0 + (c1 - c0) * s + g["curl"] * math.sin(math.pi * s)
    return ankle, ball, ball + Vector((0, math.cos(c), math.sin(c))) * leg["toe_reach"]


def aim(rig, pose, bob, bone, target):
    """Turn one bone the shortest way (its parents already posed) so its tail points at target. The shortest turn
    never twists a bone about its own length, which a free solve did and which wrung the legs."""
    trial = dict(pose)
    trial[bone] = (0.0, 0.0, 0.0)
    local = posed(rig, trial, bob, bone, {}).inverted() @ target
    e = Vector((0, 1, 0)).rotation_difference(local.normalized()).to_euler("XYZ")
    pose[bone] = (e.x, e.y, e.z)


def solve_leg(rig, pose, bob, leg, ankle, ball, tip):
    """The knee follows from the hip and ankle (always bending forward, which keeps the backward-bending joint
    behind it); then each bone is aimed at its joint."""
    hip = posed(rig, pose, bob, "thigh." + leg["side"], {}).translation
    l1, l2 = leg["l1"], leg["l2"]
    v = ankle - hip
    dist, axis = min(v.length, 0.995 * (l1 + l2)), v.normalized()
    forward = Vector((0, -1, 0))
    bend = (forward - axis * forward.dot(axis)).normalized()
    along = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    knee = hip + axis * along + bend * math.sqrt(max(0.0, l1 * l1 - along * along))
    for name, target in (("thigh", knee), ("shin", ankle), ("foot", ball), ("toe", tip)):
        aim(rig, pose, bob, name + "." + leg["side"], target)


def level_head(pose, extra=0.0):
    """Counter-rotate the head so the beak stays level whatever the body and neck are doing."""
    pitch = sum(pose.get(n, (0, 0, 0))[0] for n in ("pelvis", "spine", "chest", "neck1", "neck2"))
    rx, ry, rz = pose.get("head", (0, 0, 0))
    pose["head"] = (-pitch + extra + rx, ry, rz)


def body_walk(u, g):
    a = math.tau * u
    step = (2 * u + 0.15) % 1.0
    # Bird head bob: the head holds its place in the world while the body walks under it, then darts forward.
    dart = 1 - step / 0.7 if step < 0.7 else smooth((step - 0.7) / 0.3)
    reach = 0.32 * (dart - 0.5)
    pelvis = 0.06
    pose = {"pelvis": (pelvis + 0.02 * math.cos(2 * a), 0.06 * math.sin(a), 0.05 * math.sin(a)),
            "spine": (0.0, -0.03 * math.sin(a), 0), "chest": (-0.02, 0.02 * math.sin(a), 0),
            "neck1": (0.12 + reach, 0, 0), "neck2": (-0.4 * reach, 0, 0),
            "armUpper.L": (0.12 + 0.12 * math.sin(a + math.pi), 0, -0.05), "armUpper.R": (0.12 + 0.12 * math.sin(a), 0, 0.05),
            "armLower.L": (-0.25, 0, 0), "armLower.R": (-0.25, 0, 0),
            "tailU1": (-0.03 - pelvis, 0, 0.1 * math.sin(a - 0.5)), "tailC1": (-pelvis, 0, 0.12 * math.sin(a - 0.8)),
            "tailD1": (0.05 - pelvis, 0, 0.12 * math.sin(a - 1.1))}
    level_head(pose, 0.04 * math.sin(2 * a))
    bob = -g["crouch"] + g["bob"] * math.cos(2 * math.tau * (u - g["duty"] / 2))
    return pose, bob


def body_run(u, g):
    a = math.tau * u
    land = math.cos(2 * math.tau * (u - g["duty"] / 2 - 0.04))     # 1 just after each landing
    pelvis = 0.22 + 0.04 * land
    flap = 0.12 * math.sin(2 * a - 0.6)
    pose = {"pelvis": (pelvis, 0.04 * math.sin(a), -0.06 * math.sin(a)),
            "spine": (0.03, 0, 0), "chest": (-0.04 - 0.03 * land, 0, 0),
            "neck1": (0.32 + 0.04 * land, 0, 0), "neck2": (0.06, 0, 0),
            "armUpper.L": (0.3, 0, -0.1 - flap), "armUpper.R": (0.3, 0, 0.1 + flap),
            "armLower.L": (-0.5, 0, 0), "armLower.R": (-0.5, 0, 0),
            "featherArm.L": (0.3, 0, 0), "featherArm.R": (0.3, 0, 0),
            # The plume streams back: the top swings down, the bottom swings up.
            "tailU1": (-0.3 - pelvis + 0.04 * land, 0, 0.05 * math.sin(a)), "tailC1": (-0.05 - pelvis + 0.05 * land, 0, 0.05 * math.sin(a - 0.4)),
            "tailD1": (0.35 - pelvis + 0.05 * land, 0, 0.05 * math.sin(a - 0.8)),
            # The wind combs the crest back.
            "crestF1": (-0.3, 0, 0), "crestU1": (-0.25, 0, 0), "crestB1": (-0.12, 0, 0)}
    level_head(pose, -0.08)
    bob = -g["crouch"] - g["bob"] * land
    return pose, bob


def idle_pose(t):
    a = math.tau * t
    # Glances: the head snaps to a new direction and holds there, like a bird.
    looks = [(0.0, 0.0, 0.0), (0.14, 0.0, 0.0), (0.2, 0.5, 0.15), (0.44, 0.5, 0.15), (0.5, -0.35, -0.1),
             (0.72, -0.35, -0.1), (0.78, 0.0, 0.0), (1.0, 0.0, 0.0)]
    for (t0, y0, r0), (t1, y1, r1) in zip(looks, looks[1:]):
        if t0 <= t <= t1:
            k = smooth((t - t0) / (t1 - t0))
            yaw, tilt = y0 + (y1 - y0) * k, r0 + (r1 - r0) * k
            break
    breath = math.sin(3 * a)
    flick = math.exp(-((t - 0.6) / 0.03) ** 2)        # one quick tail flick
    pose = {"pelvis": (0.0, 0.015 * math.sin(a), 0), "chest": (0.02 * breath, 0, 0),
            "neck1": (0.01 * breath, 0, 0), "neck2": (0, yaw * 0.6, 0), "head": (0, tilt, -yaw * 0.4),
            "armUpper.L": (0.03 * breath, 0, 0), "armUpper.R": (0.03 * breath, 0, 0),
            "crestF1": (0.05 * math.sin(5 * a), 0, 0), "crestU1": (0, 0, 0.05 * math.sin(5 * a + 1)), "crestB1": (0, 0, -0.05 * math.sin(5 * a + 2)),
            "tailU1": (0.02 * math.sin(a), 0, 0.06 * math.sin(a) + 0.25 * flick), "tailC1": (0, 0, 0.07 * math.sin(a - 0.4) + 0.25 * flick),
            "tailD1": (0, 0, 0.07 * math.sin(a - 0.8) + 0.2 * flick)}
    level_head(pose)
    return pose, -0.004 + 0.006 * breath


def align_rolls(rig):
    """Roll every bone so its X axis lines up with world X as closely as it can. Turning a bone about X then always
    swings it front to back; with the default roll a splayed leg also swung inward."""
    with bpy.context.temp_override(active_object=rig, object=rig, selected_objects=[rig], selected_editable_objects=[rig]):
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        for eb in rig.data.edit_bones:
            z = Vector((1, 0, 0)).cross(eb.vector)
            if z.length > 1e-6:
                eb.align_roll(z)
        bpy.ops.object.mode_set(mode="OBJECT")


def pin_feet(ob, rig):
    """The whole pad on the ground (toes, heel and back claw) moves as one piece with the toe bone, and the
    tarsus blends in only above it; otherwise the heel smears into a blade when the tarsus tilts over the toes."""
    for side in ("L", "R"):
        ball = rig.data.bones["toe." + side].head_local
        toe = ob.vertex_groups["toe." + side]
        foot = ob.vertex_groups["foot." + side]
        for v in ob.data.vertices:
            if v.co.x * ball.x <= 0 or (v.co.xy - ball.xy).length > 0.4 or v.co.z > ball.z + 0.12:
                continue
            k = 1 - smooth((v.co.z - (ball.z + 0.04)) / 0.08)      # 1 on the pad, 0 by 12 cm above the ball
            if k <= 0:
                continue
            groups = {g.group: g.weight for g in v.groups}
            for gi in groups:
                if gi not in (toe.index, foot.index):
                    ob.vertex_groups[gi].remove([v.index])
            toe.add([v.index], k, "REPLACE")
            foot.add([v.index], 1 - k, "REPLACE")
            if k >= 1:
                foot.remove([v.index])


def smooth_joints(ob, rig, radius=0.12, iterations=8):
    """Spread each knee and ankle bend over more skin: near the joint, relax the split between the two bones
    across neighbouring vertices (their combined weight stays the same). A sharp switch pinched the ankle spur
    into shards."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    neighbours = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    bm.free()

    def weight(group, i):
        try:
            return group.weight(i)
        except RuntimeError:
            return 0.0

    for side in ("L", "R"):
        for upper, lower in (("thigh", "shin"), ("shin", "foot")):
            ga, gb = ob.vertex_groups[upper + "." + side], ob.vertex_groups[lower + "." + side]
            joint = rig.data.bones[lower + "." + side].head_local
            near = [v.index for v in ob.data.vertices if (v.co - joint).length < radius]
            total = {i: weight(ga, i) + weight(gb, i) for i in near}
            share = {i: weight(ga, i) / total[i] if total[i] > 1e-4 else 0.0 for i in near}
            for _ in range(iterations):
                share = {i: (share[i] + sum(share.get(n, share[i]) for n in neighbours[i])) / (1 + len(neighbours[i]))
                         for i in near}
            for i in near:
                if total[i] > 0.3:
                    ga.add([i], share[i] * total[i], "REPLACE")
                    gb.add([i], (1 - share[i]) * total[i], "REPLACE")


def limit_influences(ob, keep=4):
    """glTF carries 4 bone weights per vertex; trim to the strongest 4 here so Blender and the game deform alike."""
    for v in ob.data.vertices:
        weakest = [g.group for g in sorted(v.groups, key=lambda g: -g.weight)[keep:]]
        for gi in weakest:
            ob.vertex_groups[gi].remove([v.index])
        total = sum(g.weight for g in v.groups)
        if total > 0:
            for g in v.groups:
                g.weight /= total


def animate(rig):
    bpy.context.scene.render.fps = lib["FPS"]
    legs = [leg_rest(rig, "L"), leg_rest(rig, "R")]

    def bake(name, frames, body, targets):
        poses = []
        for f in range(frames + 1):
            u = f / frames
            pose, bob = body(u)
            for leg in legs:
                solve_leg(rig, pose, bob, leg, *targets(u, leg, pose, bob))
            pose["_bob"] = bob
            poses.append(pose)
        lib["key_action"](rig, name, frames, lambda t: poses[round(t * frames)])

    def standing(u, leg, pose, bob):
        return leg_targets(rig, pose, bob, leg, None, 0.0, 0.0)

    bake("Idle", 90, idle_pose, standing)
    for name, body in (("Walk", body_walk), ("Run", body_run)):
        g = GAITS[name]
        contact = {"L": 0.0, "R": 0.5}
        bake(name, g["frames"], lambda u, g=g, body=body: body(u, g),
             lambda u, leg, pose, bob, g=g: leg_targets(rig, pose, bob, leg, g, (u - contact[leg["side"]]) % 1.0, leg["hip"].y + 0.02))
    return {name: round(gait_speed(g), 2) for name, g in GAITS.items()}


def run():
    body = bpy.data.objects.get("ThunderBody")
    if body is not None and "GM Thunder" in bpy.data.scenes:
        # Re-rig the cleaned-up mesh instead of importing again.
        sc, coll = bpy.data.scenes["GM Thunder"], bpy.data.collections["Thunder"]
        bpy.context.window.scene = sc
        for ob in list(coll.objects) + list(sc.collection.objects):
            if ob is not body:
                bpy.data.objects.remove(ob, do_unlink=True)
        body.parent = None
        body.modifiers.clear()
        body.vertex_groups.clear()
    else:
        sc, coll, body = gen["collect_source"]()
        body.name, coll.name = "ThunderBody", "Thunder"
        gen["orient_and_scale"](body)
        gen["decimate"](body)
    ghosts = remove_ghosts(body)
    symmetrize(body)
    m = measure(body)
    ghosts += remove_stray_legs(body, m)
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    lib["BONES"][:] = fit(m)
    rig = lib["armature"](coll)
    rig.name = "ThunderRig"
    align_rolls(rig)
    gen["skin_via_proxy"](rig, body)
    capped = cap_limb_weights(body, rig)
    pin_feet(body, rig)
    smooth_joints(body, rig)
    limit_influences(body)
    speeds = animate(rig)
    cams = lib["preview_setup"](sc)
    for key, cam in cams.items():
        if cam.data.type == "ORTHO":
            cam.data.ortho_scale = 2.45
            cam.location.z = 1.0
        else:
            # Framed for the shorter horse: pull back and aim higher so the crest fits.
            cam.location = (3.3, -3.3, 1.9)
            cam.data.shift_y = 0.06
    gen["rest_pose"](rig, True)
    lib["preview"](sc, cams)
    gen["rest_pose"](rig, False)
    lib["export"](sc, rig)
    out = lib["OUT"]
    for ext in ("glb", "blend"):
        src, dst = os.path.join(out, f"horse.{ext}"), os.path.join(out, f"thunder.{ext}")
        if os.path.exists(src):
            os.replace(src, dst)
    legs = {side: {k: tuple(round(x, 2) for x in v) for k, v in leg.items()} for side, leg in m["legs"].items()}
    return {"triangles": tris, "ghost_verts_removed": ghosts, "limb_weights_capped": capped, "speeds_m_per_s": speeds, "legs": legs}


if globals().get("RUN", True):
    print("GM Thunder Plume Runner:", run())

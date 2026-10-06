# -*- coding: utf-8 -*-
"""
A brush painting よ on paper. Blender 4.x, version-stable.

Run:  blender --background --python blender_yo_brush.py -- --render
      blender --python blender_yo_brush.py                (open the scene)

WHY CURVES AND NOT GREASE PENCIL
Grease Pencil is the obvious tool and it is a trap: Blender 4.3 replaced it with
GPv3 and the data API changed, so a script written today may not run on the next
release. Curves have been stable for a decade and give both things this needs:
  taper_object      -> width along the stroke. This IS brush pressure.
  bevel_factor_end  -> animate 0..1 and the ink draws itself on.

STROKE ORDER
よ is two strokes, and the order is not decorative: the short horizontal comes
first, the brush lifts, then the long stem that falls into the loop and exits
right. Painting them in the wrong order would be visible to anyone who writes
kana, in the same way that drawing an E bottom-up looks wrong without being
able to say why.

PRESSURE
A brush is not a pen. Width follows the hand: an entry that lands and swells,
weight through the belly of a curve, and a tail that lifts off the paper rather
than stopping. The profiles below are read off the guide: tapered entry on the
stem, a swell through the bar with a released exit, weight at the bottom-left of
the loop, and a tail that thins as it leaves.
"""
import bpy, math, sys, os

# "//" is relative to the .blend, and with --factory-startup there is no .blend,
# so it resolves to C:\ and the render dies. Anchor to this file instead.
HERE = os.path.dirname(os.path.abspath(__file__))
from mathutils import Vector

FPS          = 30
BAR_FRAMES   = 22          # the short horizontal: quick
LIFT_FRAMES  = 9           # brush off the paper between strokes
MAIN_FRAMES  = 74          # stem -> loop -> tail: the long one
SETTLE       = 26          # hold on the finished mark
INK          = (0.02, 0.02, 0.026, 1)

# ---------------------------------------------------------------- scene reset
def wipe():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in (bpy.data.objects, bpy.data.meshes, bpy.data.curves, bpy.data.materials):
        for x in list(c):
            c.remove(x)

# --------------------------------------------------------- geometry from the em
# The mark lives in a 100-unit em with y DOWN (SVG convention). Blender is
# y-UP, so flip and centre. Keeping the em coordinates in the source means the
# curve here and the SVG in this repo stay the same object.
def em(x, y, s=0.02):
    return Vector(((x - 50) * s, -(y - 50) * s, 0.0))

BAR = [(43.5,28.0),(60,26.6),(78,25.8),(96.5,25.2)]
MAIN = [(46.0,0.5),(54.2,11.8),(47.9,52.2),(50.7,83.1),
        (46.7,99.0),(10.5,93.4),(18.9,95.4),
        (2.1,93.0),(4.8,81.6),(6.8,79.1),
        (11.6,72.4),(26.2,72.0),(30.5,72.3),
        (38.0,72.6),(46.0,77.0),(50.7,83.1),
        (63.0,86.0),(80.0,89.2),(99.3,88.8)]

def make_curve(name, pts):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 24
    sp = cu.splines.new("BEZIER")
    n = (len(pts) - 1) // 3 + 1
    sp.bezier_points.add(n - 1)
    for i in range(n):
        bp = sp.bezier_points[i]
        bp.co = em(*pts[i * 3])
        bp.handle_left  = em(*pts[i * 3 - 1]) if i > 0 else em(*pts[0])
        bp.handle_right = em(*pts[i * 3 + 1]) if i < n - 1 else em(*pts[-1])
        bp.handle_left_type = bp.handle_right_type = "FREE"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    return ob

def taper(name, profile):
    """A curve whose y is the half-width at each point along the stroke.
    This is the pressure graph, and it is the whole difference between a brush
    and a marker."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(profile) - 1)
    for i, (t, w) in enumerate(profile):
        bp = sp.bezier_points[i]
        bp.co = Vector((t * 2.0 - 1.0, w, 0))
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.hide_viewport = ob.hide_render = True
    return ob

# (t, half-width). Read off the guide, not invented.
BAR_PRESSURE = [(0.00,0.22),(0.10,0.52),(0.45,0.60),(0.75,0.46),(0.92,0.24),(1.00,0.04)]
MAIN_PRESSURE = [(0.00,0.10),(0.04,0.40),(0.10,0.56),   # lands and swells
                 (0.34,0.60),(0.42,0.66),               # weight down the stem
                 (0.52,0.70),(0.60,0.64),               # into the loop, heavy
                 (0.68,0.44),(0.76,0.34),               # thinning round the back
                 (0.82,0.46),                           # crossing the node
                 (0.92,0.34),(1.00,0.03)]               # tail lifts off

def fcurves_of(action):
    """Blender 4.4+ replaced Action.fcurves with slotted actions (layers ->
    strips -> channelbags). 5.2 has no .fcurves at all. Handle both, because
    this script should still run when 6.x lands."""
    if action is None:
        return []
    fc = getattr(action, "fcurves", None)
    if fc is not None:
        try:
            return list(fc)
        except TypeError:
            pass
    out = []
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for cb in getattr(strip, "channelbags", []):
                out.extend(cb.fcurves)
    return out


def ink_material():
    m = bpy.data.materials.new("sumi")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = INK
    b.inputs["Roughness"].default_value = 1.0
    for n in ("Specular IOR Level", "Specular"):
        if n in b.inputs:
            b.inputs[n].default_value = 0.0     # ink does not shine
    if "Metallic" in b.inputs:
        b.inputs["Metallic"].default_value = 0.0
    return m

def build():
    wipe()
    sc = bpy.context.scene
    sc.render.fps = FPS
    ink = ink_material()

    # paper: warm, slightly rough, very slightly bumped
    bpy.ops.mesh.primitive_plane_add(size=4.2)
    paper = bpy.context.object; paper.name = "paper"
    pm = bpy.data.materials.new("paper"); pm.use_nodes = True
    nt = pm.node_tree; bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.965, 0.952, 0.925, 1)
    bsdf.inputs["Roughness"].default_value = 0.95
    tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 380
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.09
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    paper.data.materials.append(pm)

    strokes = []
    for nm, pts, prof, t0, dur in (
            ("bar",  BAR,  BAR_PRESSURE,  1,                              BAR_FRAMES),
            ("main", MAIN, MAIN_PRESSURE, 1 + BAR_FRAMES + LIFT_FRAMES,   MAIN_FRAMES)):
        ob = make_curve(nm, pts)
        ob.data.bevel_depth   = 0.135
        ob.data.bevel_resolution = 8
        ob.data.taper_object  = taper(nm + "_taper", prof)
        ob.data.use_fill_caps = True
        ob.data.materials.append(ink)
        ob.location.z = 0.004
        ob.scale.z = 0.055          # flatten the tube into a stroke on the page
        # the ink draws itself on
        ob.data.bevel_factor_end = 0.0
        ob.data.keyframe_insert("bevel_factor_end", frame=t0)
        ob.data.bevel_factor_end = 1.0
        ob.data.keyframe_insert("bevel_factor_end", frame=t0 + dur)
        for fc in fcurves_of(ob.data.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"
        strokes.append((ob, t0, dur))

    # the brush: a bristle bundle, tapered, riding the tip of each stroke
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.055, radius2=0.004, depth=0.40)
    brush = bpy.context.object; brush.name = "brush"
    bm = bpy.data.materials.new("bristle"); bm.use_nodes = True
    bb = bm.node_tree.nodes["Principled BSDF"]
    bb.inputs["Base Color"].default_value = (0.06, 0.05, 0.05, 1)
    bb.inputs["Roughness"].default_value = 0.8
    brush.data.materials.append(bm)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.038, depth=1.0)
    handle = bpy.context.object; handle.name = "handle"
    hm = bpy.data.materials.new("bamboo"); hm.use_nodes = True
    hm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55,0.42,0.24,1)
    handle.data.materials.append(hm)
    handle.parent = brush
    handle.location = (0, 0, 0.68)

    # Follow Path per stroke, handing off between them, so the brush tracks the
    # exact point where ink is appearing rather than an approximation of it.
    for ob, t0, dur in strokes:
        c = brush.constraints.new("FOLLOW_PATH")
        c.target = ob
        c.use_curve_follow = False
        c.forward_axis = "TRACK_NEGATIVE_Z"
        c.up_axis = "UP_Y"
        ob.data.use_path = True
        ob.data.eval_time = 0
        ob.data.keyframe_insert("eval_time", frame=t0)
        ob.data.eval_time = 100
        ob.data.keyframe_insert("eval_time", frame=t0 + dur)
        c.influence = 0.0
        c.keyframe_insert("influence", frame=t0 - 1); c.influence = 1.0
        c.keyframe_insert("influence", frame=t0)
        c.keyframe_insert("influence", frame=t0 + dur); c.influence = 0.0
        c.keyframe_insert("influence", frame=t0 + dur + 1)

    # brush lifts off the paper between strokes and at the end
    def z(f, v):
        brush.location.z = v; brush.keyframe_insert("location", index=2, frame=f)
    b_end = 1 + BAR_FRAMES
    z(1, 0.30); z(4, 0.06); z(b_end, 0.06); z(b_end + 5, 0.34)
    m0 = b_end + LIFT_FRAMES
    z(m0 - 2, 0.30); z(m0 + 2, 0.05)
    z(m0 + MAIN_FRAMES, 0.05); z(m0 + MAIN_FRAMES + 8, 0.42)
    brush.rotation_euler = (math.radians(11), math.radians(-7), 0)

    # camera, slightly off square. Straight-on reads like a scan, not a hand.
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = 2.75          # mark is ~2.0 wide; leaves a margin
    cam = bpy.data.objects.new("cam", cam_d); bpy.context.collection.objects.link(cam)
    cam.location = (0.0, 0.0, 4.0)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    sc.camera = cam

    key = bpy.data.lights.new("key", "AREA"); key.energy = 900; key.size = 9
    ko = bpy.data.objects.new("key", key); bpy.context.collection.objects.link(ko)
    ko.location = (-0.6, 0.9, 3.6); ko.rotation_euler = (math.radians(9), math.radians(-6), 0)
    w = bpy.context.scene.world or bpy.data.worlds.new("w")
    bpy.context.scene.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.9,0.9,0.92,1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.85

    sc.frame_start = 1
    sc.frame_end = m0 + MAIN_FRAMES + SETTLE
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in \
        {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = 1080
    try:
        sc.view_settings.view_transform = "Standard"   # NOT AgX: ink must be ink
        sc.view_settings.look = "None"
    except Exception as e:
        print("view transform:", e)
    sc.render.film_transparent = False
    print(f"BUILT_OK frames 1..{sc.frame_end} engine={sc.render.engine}")
    return sc

if __name__ == "__main__":
    sc = build()
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--render" in argv:
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"
        sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"
        sc.render.filepath = os.path.join(HERE, "yo_brush.mp4")
        bpy.ops.render.render(animation=True)
        print("RENDER_OK", sc.render.filepath)
    elif "--still" in argv:
        sc.frame_set(sc.frame_end - 5)
        sc.render.filepath = os.path.join(HERE, "yo_still.png")
        bpy.ops.render.render(write_still=True)
        print("STILL_OK", sc.render.filepath)

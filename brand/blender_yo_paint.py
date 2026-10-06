# -*- coding: utf-8 -*-
"""
A 3D brush painting よ, done right. Blender 5.x / 4.x, version-stable.

Why this differs from the earlier attempt (which read as bent vinyl):
- The stroke is a FLAT FILLED calligraphic ribbon (like the logo), not a beveled
  tube. A circular bevel lit from the side is a wire; a flat matte ribbon lying
  on paper is ink.
- The ribbon mesh is built quad-by-quad in ARC-LENGTH ORDER along a SMOOTHED
  centerline (a smoothing spline, so no kinks). A Build modifier then reveals the
  quads in creation order, i.e. tip-first, which is the paint-on.
- A 3D brush rides the growing tip, dipping with the stroke's own pressure.
- Flat top-down ortho, matte sumi shader, warm paper. Standard view transform,
  not AgX, so ink is ink.

Run headless:
  blender --background --factory-startup --python blender_yo_paint.py -- --render
  blender --background --factory-startup --python blender_yo_paint.py -- --still
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
BAR_FRAMES, LIFT, MAIN_FRAMES, SETTLE = 20, 8, 70, 24

# ---- geometry: the same smoothed centerline + pressure as the logo ----------
def _bez(pts, n=200):
    out = []
    for i in range(0, len(pts) - 1, 3):
        p = np.array(pts[i:i+4]); t = np.linspace(0, 1, n)[:, None]
        seg = (1-t)**3*p[0] + 3*(1-t)**2*t*p[1] + 3*(1-t)*t**2*p[2] + t**3*p[3]
        out.append(seg if i == 0 else seg[1:])
    return np.vstack(out)

BAR = [(45.0,27.8),(58,26.7),(71,26.1),(86.0,25.7)]
MAIN = [(46.5,3.0),(49.0,14.0),(48.2,52.2),(50.7,83.1),(46.7,99.0),(10.5,93.4),(18.9,95.4),
        (2.1,93.0),(4.8,81.6),(6.8,79.1),(11.6,72.4),(26.2,72.0),(30.5,72.3),
        (38.0,72.6),(46.0,77.0),(50.7,83.1),(63.0,86.0),(80.0,89.2),(93.5,89.0)]
BAR_W  = [(0.00,1.6),(0.18,2.9),(0.5,3.1),(0.82,2.6),(1.00,1.5)]
MAIN_W = [(0.00,1.5),(0.06,2.7),(0.13,3.4),(0.34,3.6),(0.44,4.0),(0.53,4.2),
          (0.62,3.7),(0.70,2.7),(0.78,2.3),(0.84,2.8),(0.93,2.0),(1.00,1.3)]

# geometry is precomputed by the prep step (scipy) into yo_geom.npz, because
# Blender's bundled Python has numpy but not scipy.
_GEOM = np.load(os.path.join(HERE, "yo_geom.npz"))
def smoothed(which):
    return _GEOM[which+"_c"], _GEOM[which+"_n"], _GEOM[which+"_w"]

def em(x, y):                       # 100-unit em, y-down (SVG) -> Blender y-up, centered
    s = 0.02
    return Vector(((x-50)*s, -(y-50)*s, 0.0))

def build_ribbon(name, which, ink):
    C, N, w = smoothed(which)
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    left = [bm.verts.new(em(*(C[i] + N[i]*w[i]))) for i in range(len(C))]
    right = [bm.verts.new(em(*(C[i] - N[i]*w[i]))) for i in range(len(C))]
    bm.verts.ensure_lookup_table()
    # quads in arc-length order -> Build modifier reveals tip-first
    for i in range(len(C) - 1):
        bm.faces.new((left[i], left[i+1], right[i+1], right[i]))
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(ink)
    ob.location.z = 0.003
    return ob, C

def matte(name, rgb, rough=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    for k in ("Specular IOR Level", "Specular"):
        if k in b.inputs: b.inputs[k].default_value = 0.0
    return m

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps = FPS
    ink = matte("sumi", (0.012, 0.012, 0.016))

    bpy.ops.mesh.primitive_plane_add(size=4.4)
    paper = bpy.context.object
    pm = matte("paper", (0.965, 0.952, 0.925), 0.96)
    nt = pm.node_tree; bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 340
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.06
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    paper.data.materials.append(pm)

    bar_ob, barC   = build_ribbon("bar",  "bar",  ink)
    main_ob, mainC = build_ribbon("main", "main", ink)

    # paint-on via Build modifier, in arc-length (creation) order
    for ob, t0, dur in ((bar_ob, 1, BAR_FRAMES),
                        (main_ob, 1 + BAR_FRAMES + LIFT, MAIN_FRAMES)):
        b = ob.modifiers.new("build", "BUILD")
        b.frame_start = t0; b.frame_duration = dur; b.use_reverse = False
        # hide the stroke until its turn
        ob.hide_render = False
        kf = ob.modifiers["build"]

    # a brush that rides the tip. cone (bristles) + cylinder (handle).
    bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=0.05, radius2=0.004, depth=0.34)
    brush = bpy.context.object; brush.name = "brush"
    brush.data.materials.append(matte("bristle", (0.05, 0.04, 0.04), 0.8))
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.03, depth=0.9)
    handle = bpy.context.object; handle.name = "handle"
    handle.data.materials.append(matte("bamboo", (0.55, 0.42, 0.24), 0.6))
    handle.parent = brush; handle.location = (0, 0, 0.6)
    brush.rotation_euler = (math.radians(12), math.radians(-8), 0)

    def tip(C, frac):
        i = min(len(C)-1, max(0, int(frac*(len(C)-1))))
        return em(*C[i])
    def key_brush(frame, pos, z):
        brush.location = (pos.x, pos.y, z)
        brush.keyframe_insert("location", frame=frame)

    # bar pass
    for f in range(BAR_FRAMES + 1):
        fr = 1 + f; frac = f / BAR_FRAMES
        key_brush(fr, tip(barC, frac), 0.05)
    lift_f = 1 + BAR_FRAMES
    key_brush(lift_f + 1, tip(barC, 1.0), 0.34)              # lift
    m0 = 1 + BAR_FRAMES + LIFT
    key_brush(m0 - 1, tip(mainC, 0.0), 0.32)
    for f in range(MAIN_FRAMES + 1):
        fr = m0 + f; frac = f / MAIN_FRAMES
        key_brush(fr, tip(mainC, frac), 0.05)
    end_f = m0 + MAIN_FRAMES
    key_brush(end_f + 8, tip(mainC, 1.0), 0.4)               # lift off

    # camera: orthographic top-down, tiny tilt for life
    cam_d = bpy.data.cameras.new("cam"); cam_d.type = "ORTHO"; cam_d.ortho_scale = 2.7
    cam = bpy.data.objects.new("cam", cam_d); bpy.context.collection.objects.link(cam)
    cam.location = (0, 0, 4); cam.rotation_euler = (0, 0, 0); sc.camera = cam

    key = bpy.data.lights.new("key", "AREA"); key.energy = 800; key.size = 8
    ko = bpy.data.objects.new("key", key); bpy.context.collection.objects.link(ko)
    ko.location = (-0.7, 1.0, 3.4); ko.rotation_euler = (math.radians(10), math.radians(-6), 0)
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.92, 0.92, 0.93, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5

    sc.frame_start = 1; sc.frame_end = end_f + SETTLE
    engines = {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = 1000
    try:
        sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
    except Exception as e: print("view:", e)
    print(f"BUILT_OK frames 1..{sc.frame_end} engine={sc.render.engine}")
    return sc

if __name__ == "__main__":
    sc = build()
    argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    if "--still" in argv:
        sc.frame_set(sc.frame_end - 4)
        sc.render.filepath = os.path.join(HERE, "yo_paint_still.png")
        bpy.ops.render.render(write_still=True); print("STILL_OK")
    elif "--render" in argv:
        # this build has no FFMPEG output; render a PNG sequence and let ffmpeg
        # (on PATH) stitch it afterwards.
        outdir = os.path.join(HERE, "frames"); os.makedirs(outdir, exist_ok=True)
        sc.render.image_settings.file_format = "PNG"
        sc.render.filepath = os.path.join(outdir, "f")
        bpy.ops.render.render(animation=True)
        print("RENDER_OK", outdir)

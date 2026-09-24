"""
Convert the RehabTwin character FBX to a browser-friendly GLB.

Run with Blender (headless):

    blender -b --python scripts/fbx_to_glb.py -- <in.fbx> <out.glb>

Behaviour:
- Clears the scene and imports the FBX.
- Removes cameras, lights and unused (leaf) empties.
- Dumps armature bone names, parents and rest-pose world head/tail to a
  sibling JSON file next to the GLB (character_bones.json).
- Exports GLB (no animations, skins kept, modifiers NOT applied).
- If the GLB exceeds 15 MB, textures are downscaled to max 1024 px and it is
  re-exported. Only if it is still >15 MB is Draco mesh compression enabled
  (which requires a Draco decoder in the viewer) and a notice is printed.

The source FBX is never modified.
"""
import json
import os
import sys

import bpy

MAX_GLB_BYTES = 15 * 1024 * 1024
# Overridable so a lighter asset can be produced for the browser viewer.
MAX_TEXTURE_DIM = int(os.getenv("GLB_MAX_TEXTURE_DIM", "1024"))


def _script_args():
    if "--" not in sys.argv:
        return []
    return [arg for arg in sys.argv[sys.argv.index("--") + 1:] if arg]


def _clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _remove_unneeded_objects():
    """Remove cameras, lights, and empties that are not needed by the model."""
    doomed = []
    for obj in bpy.data.objects:
        if obj.type in {"CAMERA", "LIGHT"}:
            doomed.append(obj)
        elif obj.type == "EMPTY" and not obj.children:
            # Leaf empties carry no deform or hierarchy information.
            doomed.append(obj)

    for obj in doomed:
        bpy.data.objects.remove(obj, do_unlink=True)


def _dump_bones(out_json):
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    data = {
        "armatures": [],
        "bone_count": 0,
    }
    for arm in armatures:
        matrix_world = arm.matrix_world
        bones = []
        for bone in arm.data.bones:
            head_world = matrix_world @ bone.head_local
            tail_world = matrix_world @ bone.tail_local
            bones.append({
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else None,
                "head": [round(v, 6) for v in bone.head_local],
                "tail": [round(v, 6) for v in bone.tail_local],
                "head_world": [round(v, 6) for v in head_world],
                "tail_world": [round(v, 6) for v in tail_world],
                "length": round(bone.length, 6),
            })
        data["armatures"].append({
            "name": arm.name,
            "bone_count": len(bones),
            "bones": bones,
        })
        data["bone_count"] += len(bones)

    with open(out_json, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    print(f"BONES_JSON {out_json} armatures={len(armatures)} bones={data['bone_count']}")


def _downscale_textures():
    scaled = 0
    for image in bpy.data.images:
        try:
            width, height = image.size
        except Exception:
            continue
        if not width or not height:
            continue
        if width <= MAX_TEXTURE_DIM and height <= MAX_TEXTURE_DIM:
            continue
        scale = MAX_TEXTURE_DIM / float(max(width, height))
        new_w = max(1, int(width * scale))
        new_h = max(1, int(height * scale))
        try:
            image.scale(new_w, new_h)
            scaled += 1
        except Exception as exc:  # pragma: no cover - depends on image source
            print(f"WARN could not scale image '{image.name}': {exc}")
    print(f"TEXTURES_DOWNSCALED {scaled}")


def _export_glb(path, draco=False):
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_animations=False,
        export_skins=True,
        export_apply=False,
        export_draco_mesh_compression_enable=draco,
    )


def main():
    args = _script_args()
    if len(args) < 2:
        print("USAGE: blender -b --python scripts/fbx_to_glb.py -- <in.fbx> <out.glb>")
        sys.exit(1)

    in_fbx = os.path.abspath(args[0])
    out_glb = os.path.abspath(args[1])
    out_dir = os.path.dirname(out_glb)
    os.makedirs(out_dir, exist_ok=True)
    out_json = os.path.join(out_dir, "character_bones.json")

    if not os.path.isfile(in_fbx):
        print(f"ERROR: input FBX not found: {in_fbx}")
        sys.exit(1)

    _clear_scene()
    bpy.ops.import_scene.fbx(filepath=in_fbx)
    print(f"IMPORTED {in_fbx}")

    _remove_unneeded_objects()
    _dump_bones(out_json)

    draco_used = False
    _export_glb(out_glb, draco=False)
    size = os.path.getsize(out_glb)
    print(f"GLB_EXPORT size_mb={size / (1024 * 1024):.2f} draco=False")

    if size > MAX_GLB_BYTES:
        print("GLB over 15 MB — downscaling textures to 1024 px and re-exporting")
        _downscale_textures()
        _export_glb(out_glb, draco=False)
        size = os.path.getsize(out_glb)
        print(f"GLB_EXPORT size_mb={size / (1024 * 1024):.2f} draco=False (scaled)")

    if size > MAX_GLB_BYTES:
        print("GLB still over 15 MB — enabling Draco compression (viewer needs a Draco decoder)")
        _export_glb(out_glb, draco=True)
        draco_used = True
        size = os.path.getsize(out_glb)
        print(f"GLB_EXPORT size_mb={size / (1024 * 1024):.2f} draco=True")

    print(f"FINAL_GLB {out_glb} size_mb={size / (1024 * 1024):.2f} draco={draco_used}")


if __name__ == "__main__":
    main()

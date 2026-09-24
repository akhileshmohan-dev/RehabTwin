"""
Verify a GLB by re-importing it in headless Blender.

    blender -b --python scripts/verify_glb.py -- <file.glb>

Prints mesh count, armature count and total armature bone count.
"""
import os
import sys

import bpy


def main():
    if "--" not in sys.argv:
        print("USAGE: blender -b --python scripts/verify_glb.py -- <file.glb>")
        sys.exit(1)
    args = [a for a in sys.argv[sys.argv.index("--") + 1:] if a]
    if not args:
        print("USAGE: blender -b --python scripts/verify_glb.py -- <file.glb>")
        sys.exit(1)

    glb = os.path.abspath(args[0])
    if not os.path.isfile(glb):
        print(f"ERROR: GLB not found: {glb}")
        sys.exit(1)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    bone_count = sum(len(a.data.bones) for a in armatures)

    print(
        f"GLB_VERIFY file={glb} meshes={len(meshes)} "
        f"armatures={len(armatures)} bones={bone_count}"
    )


if __name__ == "__main__":
    main()

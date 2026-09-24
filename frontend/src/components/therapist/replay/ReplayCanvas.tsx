/**
 * Client-only three.js canvas for the 3D session replay.
 *
 * This module is only ever imported dynamically (client-side) from
 * SessionReplay3D so that three.js never runs during SSR.
 */
import { memo, useEffect, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import { Box3, Bone, Group, Object3D, Quaternion, Vector3 } from "three";
import { clone as cloneSkeleton } from "three/examples/jsm/utils/SkeletonUtils.js";

import type { ReplayFrame } from "./types";
import {
  alignQuaternion,
  dampAlpha,
  key,
  sampleLandmarks,
  targetDirections,
  type LimbKind,
  type Side,
} from "./retarget";

const MODEL_URL = "/models/Character_Model.glb";

// Bone suffix (after the mixamo side prefix) and its chain child.
const CHAIN: Record<LimbKind, { bone: string; child: string; parent: string | null }> = {
  upperArm: { bone: "Arm", child: "ForeArm", parent: "Shoulder" },
  foreArm: { bone: "ForeArm", child: "Hand", parent: "Arm" },
  upperLeg: { bone: "UpLeg", child: "Leg", parent: null },
  lowerLeg: { bone: "Leg", child: "Foot", parent: "UpLeg" },
};

const ORDER: LimbKind[] = ["upperArm", "foreArm", "upperLeg", "lowerLeg"];

function norm(name: string): string {
  return name.replace(/[^a-z0-9]/gi, "").toLowerCase();
}

interface DrivenBone {
  bone: Bone;
  parent: Bone | null;
  restQuat: Quaternion;
  parentRestQuat: Quaternion | null;
  restDir: Vector3;
  prev: Quaternion;
  side: Side;
  kind: LimbKind;
}

function collectBones(root: Object3D): Bone[] {
  const bones: Bone[] = [];
  root.traverse((object) => {
    if ((object as Bone).isBone) bones.push(object as Bone);
  });
  return bones;
}

function buildRig(root: Object3D): DrivenBone[] {
  const bones = collectBones(root);
  if (bones.length === 0) return [];
  root.updateMatrixWorld(true);

  const find = (suffix: string): Bone | null => {
    const target = suffix.toLowerCase();
    return bones.find((bone) => norm(bone.name).endsWith(target)) ?? null;
  };

  const driven: DrivenBone[] = [];
  for (const side of ["left", "right"] as Side[]) {
    const cap = side === "left" ? "Left" : "Right";
    for (const kind of ORDER) {
      const config = CHAIN[kind];
      const bone = find(`${cap}${config.bone}`);
      if (!bone) continue;
      const child = find(`${cap}${config.child}`);
      const parent = config.parent ? find(`${cap}${config.parent}`) : find("Hips");

      const restQuat = bone.getWorldQuaternion(new Quaternion());
      const parentRestQuat = parent ? parent.getWorldQuaternion(new Quaternion()) : null;
      let restDir = child
        ? child
            .getWorldPosition(new Vector3())
            .sub(bone.getWorldPosition(new Vector3()))
            .normalize()
        : new Vector3(0, -1, 0);
      if (restDir.lengthSq() < 1e-9) restDir = new Vector3(0, -1, 0);

      driven.push({
        bone,
        parent,
        restQuat,
        parentRestQuat,
        restDir,
        prev: restQuat.clone(),
        side,
        kind,
      });
    }
  }
  return driven;
}

interface RigProps {
  frames: ReplayFrame[];
  timeRef: MutableRefObject<number>;
}

function Rig({ frames, timeRef }: RigProps) {
  const { scene } = useGLTF(MODEL_URL);
  const cloned = useMemo(() => cloneSkeleton(scene), [scene]);
  const group = useRef<Group>(null);
  const rigRef = useRef<DrivenBone[]>([]);
  const { camera, controls } = useThree();

  useEffect(() => {
    const node = group.current;
    if (!node) return;

    // Place feet on the ground and fit to ~1.8 units tall.
    node.position.set(0, 0, 0);
    node.scale.setScalar(1);
    node.rotation.set(0, 0, 0);
    node.updateMatrixWorld(true);

    const box = new Box3().setFromObject(cloned);
    const size = box.getSize(new Vector3());
    const center = box.getCenter(new Vector3());
    const scale = size.y > 1e-6 ? 1.8 / size.y : 1;
    node.scale.setScalar(scale);
    node.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);
    node.updateMatrixWorld(true);

    rigRef.current = buildRig(cloned);

    // Face the camera from the model's forward direction (foot -> toe).
    const bones = collectBones(cloned);
    const find = (suffix: string) =>
      bones.find((bone) => norm(bone.name).endsWith(suffix.toLowerCase())) ?? null;
    const foot = find("LeftFoot");
    const toe = find("LeftToeBase");
    const forward = new Vector3(0, 0, 1);
    if (foot && toe) {
      forward.copy(
        toe.getWorldPosition(new Vector3()).sub(foot.getWorldPosition(new Vector3()))
      );
      forward.y = 0;
      if (forward.lengthSq() < 1e-9) forward.set(0, 0, 1);
      forward.normalize();
    }

    const distance = 3.6;
    camera.position.set(forward.x * distance, 1.35, forward.z * distance);
    camera.lookAt(0, 0.9, 0);
    const orbit = controls as unknown as { target?: Vector3; update?: () => void } | null;
    if (orbit?.target) {
      orbit.target.set(0, 0.9, 0);
      orbit.update?.();
    }
  }, [cloned, camera, controls]);

  useFrame((_state, delta) => {
    const driven = rigRef.current;
    if (driven.length === 0) return;

    const landmarks = sampleLandmarks(frames, timeRef.current);
    const directions = landmarks ? targetDirections(landmarks) : {};
    const alpha = dampAlpha(delta);
    const world = new Map<Bone, Quaternion>();

    for (const entry of driven) {
      const target = directions[key(entry.side, entry.kind)];
      const parentWorld = entry.parent && world.has(entry.parent)
        ? world.get(entry.parent)!
        : entry.parentRestQuat;

      if (!target) {
        if (parentWorld) world.set(entry.bone, parentWorld.clone().multiply(entry.bone.quaternion));
        continue;
      }

      const align = alignQuaternion(entry.restDir, target);
      const targetWorld = align.multiply(entry.restQuat.clone());
      const local = parentWorld
        ? parentWorld.clone().invert().multiply(targetWorld)
        : targetWorld;
      const smoothed = entry.prev.clone().slerp(local, alpha);
      entry.bone.quaternion.copy(smoothed);
      entry.prev.copy(smoothed);
      world.set(entry.bone, (parentWorld ?? new Quaternion()).clone().multiply(smoothed));
    }
  });

  return (
    <group ref={group}>
      <primitive object={cloned} />
    </group>
  );
}

export interface ReplayCanvasProps {
  frames: ReplayFrame[];
  side: string;
  timeRef: MutableRefObject<number>;
}

function ReplayCanvasImpl({ frames, timeRef }: ReplayCanvasProps) {
  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 1.35, 3.6], fov: 40, near: 0.01, far: 200 }}
      gl={{ preserveDrawingBuffer: false }}
    >
      <color attach="background" args={["#0f1216"]} />
      <hemisphereLight intensity={0.7} groundColor="#20242b" color="#ffffff" />
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 6, 4]} intensity={1.6} />
      <directionalLight position={[-3, 3, -4]} intensity={0.4} />
      <Rig frames={frames} timeRef={timeRef} />
      <OrbitControls enablePan={false} minDistance={1.5} maxDistance={8} target={[0, 0.9, 0]} />
    </Canvas>
  );
}

export default memo(ReplayCanvasImpl);
useGLTF.preload(MODEL_URL);

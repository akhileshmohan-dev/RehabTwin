/**
 * Math helpers for retargeting normalized MediaPipe landmarks onto the
 * Mixamo character rig. Pure data + three.js math; no React.
 *
 * Coordinate conventions (derived from the seeded frames in Phase 1):
 *  - Landmark x in [0,1] increases to the image right; the LEFT_* landmarks
 *    move toward +x for left-limb motion, matching the model's +X (left) side.
 *    => modelX = x - 0.5 (no horizontal mirror).
 *  - Landmark y in [0,1] increases downward; model Y is up
 *    => modelY = 0.5 - y (image Y flipped).
 *  - MediaPipe z is noisy relative depth and is heavily damped.
 */
import { Quaternion, Vector3 } from "three";
import type { ReplayFrame, SessionFrameLandmark } from "./types";

export type Side = "left" | "right";
export type LimbKind = "upperArm" | "foreArm" | "upperLeg" | "lowerLeg";

const Z_DAMP = 0.15;

const LANDMARKS: Record<
  Side,
  { shoulder: string; elbow: string; wrist: string; hip: string; knee: string; ankle: string }
> = {
  left: {
    shoulder: "LEFT_SHOULDER",
    elbow: "LEFT_ELBOW",
    wrist: "LEFT_WRIST",
    hip: "LEFT_HIP",
    knee: "LEFT_KNEE",
    ankle: "LEFT_ANKLE",
  },
  right: {
    shoulder: "RIGHT_SHOULDER",
    elbow: "RIGHT_ELBOW",
    wrist: "RIGHT_WRIST",
    hip: "RIGHT_HIP",
    knee: "RIGHT_KNEE",
    ankle: "RIGHT_ANKLE",
  },
};

export function key(side: Side, kind: LimbKind): string {
  return `${side}:${kind}`;
}

export function toModel(point: SessionFrameLandmark): Vector3 {
  return new Vector3(point.x - 0.5, 0.5 - point.y, -(point.z ?? 0) * Z_DAMP);
}

/** Linear interpolation of landmark positions by time (not frame index). */
export function sampleLandmarks(
  frames: ReplayFrame[],
  timeMs: number
): Record<string, SessionFrameLandmark> | null {
  const first = frames[0];
  if (!first) return null;
  if (timeMs <= first.t_ms) return first.landmarks;

  const last = frames[frames.length - 1];
  if (!last) return null;
  if (timeMs >= last.t_ms) return last.landmarks;

  let lo = 0;
  let hi = frames.length - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if ((frames[mid]?.t_ms ?? Infinity) <= timeMs) lo = mid;
    else hi = mid;
  }

  const f0 = frames[lo]!;
  const f1 = frames[hi]!;
  const span = f1.t_ms - f0.t_ms;
  const t = span > 0 ? (timeMs - f0.t_ms) / span : 0;

  const out: Record<string, SessionFrameLandmark> = {};
  const names = new Set([...Object.keys(f0.landmarks), ...Object.keys(f1.landmarks)]);
  for (const name of names) {
    const a = f0.landmarks[name];
    const b = f1.landmarks[name];
    if (a && b) {
      const landmark: SessionFrameLandmark = {
        x: a.x + (b.x - a.x) * t,
        y: a.y + (b.y - a.y) * t,
        z: (a.z ?? 0) + ((b.z ?? 0) - (a.z ?? 0)) * t,
      };
      if (a.visibility !== undefined) landmark.visibility = a.visibility;
      out[name] = landmark;
    } else if (a ?? b) {
      out[name] = (a ?? b) as SessionFrameLandmark;
    }
  }
  return out;
}

/** Convert landmarks into unit direction vectors for each driven limb. */
export function targetDirections(
  landmarks: Record<string, SessionFrameLandmark>
): Record<string, Vector3> {
  const result: Record<string, Vector3> = {};

  const direction = (from: string, to: string): Vector3 | null => {
    const a = landmarks[from];
    const b = landmarks[to];
    if (!a || !b) return null;
    const v = toModel(b).sub(toModel(a));
    return v.lengthSq() > 1e-12 ? v.normalize() : null;
  };

  (["left", "right"] as Side[]).forEach((side) => {
    const lm = LANDMARKS[side];
    const upperArm = direction(lm.shoulder, lm.elbow);
    if (upperArm) result[key(side, "upperArm")] = upperArm;
    const foreArm = direction(lm.elbow, lm.wrist);
    if (foreArm) result[key(side, "foreArm")] = foreArm;
    const upperLeg = direction(lm.hip, lm.knee);
    if (upperLeg) result[key(side, "upperLeg")] = upperLeg;
    const lowerLeg = direction(lm.knee, lm.ankle);
    if (lowerLeg) result[key(side, "lowerLeg")] = lowerLeg;
  });

  return result;
}

/** Minimal rotation taking a rest direction to a target direction. */
export function alignQuaternion(restDir: Vector3, targetDir: Vector3): Quaternion {
  return new Quaternion().setFromUnitVectors(restDir, targetDir);
}

/** Frame-rate independent slerp factor. */
export function dampAlpha(dtSeconds: number): number {
  const dt = Math.max(0, Math.min(dtSeconds, 0.1));
  return 1 - Math.exp(-14 * dt);
}

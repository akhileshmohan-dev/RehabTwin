import type { Patient, Session } from "@/types/rehab";

export const patients: Patient[] = [
  {
    id: "P001",
    name: "Patient 001",
    age: 45,
    gender: "Male",
    condition: "Post-Stroke Hemiparesis (Right Side)",
    startDate: "2026-06-15",
    sessionCount: 5,
    recoveryScore: 72,
    status: "Good",
    avatarSeed: "p001",
  },
  {
    id: "P002",
    name: "Patient 002",
    age: 38,
    gender: "Female",
    condition: "Rotator Cuff Repair Rehabilitation",
    startDate: "2026-05-28",
    sessionCount: 6,
    recoveryScore: 81,
    status: "Excellent",
    avatarSeed: "p002",
  },
  {
    id: "P003",
    name: "Patient 003",
    age: 61,
    gender: "Male",
    condition: "Total Knee Arthroplasty Recovery",
    startDate: "2026-06-02",
    sessionCount: 5,
    recoveryScore: 58,
    status: "Attention",
    avatarSeed: "p003",
  },
  {
    id: "P004",
    name: "Patient 004",
    age: 52,
    gender: "Female",
    condition: "Cervical Radiculopathy",
    startDate: "2026-06-20",
    sessionCount: 4,
    recoveryScore: 76,
    status: "Good",
    avatarSeed: "p004",
  },
  {
    id: "P005",
    name: "Patient 005",
    age: 34,
    gender: "Male",
    condition: "ACL Reconstruction Rehabilitation",
    startDate: "2026-07-01",
    sessionCount: 5,
    recoveryScore: 69,
    status: "Good",
    avatarSeed: "p005",
  },
];

const exerciseByPatient: Record<string, string> = {
  P001: "Elbow Flexion",
  P002: "Shoulder Abduction",
  P003: "Knee Extension",
  P004: "Neck Rotation",
  P005: "Hamstring Curl",
};

interface Point {
  rom: number;
  score: number;
  reps: number;
  date: string;
}

const seriesByPatient: Record<string, Point[]> = {
  P001: [
    { rom: 130.0, score: 72, reps: 8, date: "2026-06-12T09:20:00" },
    { rom: 134.5, score: 71, reps: 9, date: "2026-07-20T10:00:00" },
    { rom: 138.0, score: 76, reps: 9, date: "2026-07-28T09:45:00" },
    { rom: 142.0, score: 81, reps: 10, date: "2026-08-05T11:10:00" },
    { rom: 148.5, score: 87, reps: 10, date: "2026-08-17T10:30:00" },
  ],
  P002: [
    { rom: 118.0, score: 68, reps: 8, date: "2026-06-10T09:00:00" },
    { rom: 126.0, score: 73, reps: 9, date: "2026-06-24T09:30:00" },
    { rom: 134.0, score: 78, reps: 10, date: "2026-07-12T10:15:00" },
    { rom: 141.0, score: 84, reps: 11, date: "2026-08-01T10:45:00" },
    { rom: 152.0, score: 91, reps: 12, date: "2026-08-16T09:15:00" },
  ],
  P003: [
    { rom: 88.0, score: 52, reps: 6, date: "2026-06-08T14:00:00" },
    { rom: 92.0, score: 55, reps: 6, date: "2026-06-25T14:20:00" },
    { rom: 95.5, score: 54, reps: 7, date: "2026-07-14T13:30:00" },
    { rom: 99.0, score: 57, reps: 7, date: "2026-08-02T15:00:00" },
    { rom: 103.0, score: 61, reps: 8, date: "2026-08-15T14:10:00" },
  ],
  P004: [
    { rom: 62.0, score: 64, reps: 7, date: "2026-06-22T11:00:00" },
    { rom: 68.5, score: 70, reps: 8, date: "2026-07-08T11:20:00" },
    { rom: 73.0, score: 74, reps: 9, date: "2026-07-27T10:40:00" },
    { rom: 78.5, score: 80, reps: 10, date: "2026-08-14T11:50:00" },
  ],
  P005: [
    { rom: 96.0, score: 60, reps: 8, date: "2026-07-03T16:00:00" },
    { rom: 104.0, score: 64, reps: 9, date: "2026-07-17T16:20:00" },
    { rom: 110.5, score: 67, reps: 10, date: "2026-07-31T15:30:00" },
    { rom: 116.0, score: 71, reps: 11, date: "2026-08-11T16:10:00" },
    { rom: 121.0, score: 75, reps: 12, date: "2026-08-18T15:45:00" },
  ],
};

function qualityFor(score: number) {
  if (score >= 85) return "Excellent" as const;
  if (score >= 72) return "Good" as const;
  if (score >= 60) return "Fair" as const;
  return "Poor" as const;
}

export const sessions: Session[] = Object.entries(seriesByPatient).flatMap(
  ([patientId, points]) =>
    points.map((p, i) => ({
      id: i + 1,
      patientId,
      dateTime: p.date,
      exercise: exerciseByPatient[patientId] ?? "Exercise",
      repetitions: p.reps,
      rom: p.rom,
      quality: qualityFor(p.score),
      score: p.score,
    })),
);

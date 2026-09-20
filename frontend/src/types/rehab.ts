export type MovementQuality = "Poor" | "Fair" | "Good" | "Excellent";

export type PatientStatus = "Excellent" | "Good" | "Attention";

export interface Session {
  id: number;
  patientId: string;
  dateTime: string; // ISO string
  exercise: string;
  repetitions: number;
  rom: number;
  quality: MovementQuality;
  score: number;
}

export interface Patient {
  id: string;
  name: string;
  age: number;
  gender: "Male" | "Female";
  condition: string;
  startDate: string; // ISO string
  sessionCount: number;
  recoveryScore: number;
  status: PatientStatus;
  avatarSeed: string;
}

export interface DashboardStats {
  totalPatients: number;
  totalSessionsThisWeek: number;
  improving: number;
  needAttention: number;
  avgRecoveryScore: number;
}

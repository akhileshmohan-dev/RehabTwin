export type MovementQuality = "Poor" | "Fair" | "Good" | "Excellent";

export type SessionStatus = "ACTIVE" | "COMPLETED" | (string & {});

export interface Session {
  id: number;
  rawSessionId: string;
  patientId: string;
  dateTime: string; // ISO string (started_at)
  endedAt?: string;
  exercise: string;
  exerciseId: string;
  side: "left" | "right";
  repetitions: number;
  rom: number;
  quality?: MovementQuality;
  score: number | null;
  status: SessionStatus;
  hasResult: boolean;
  feedback?: string;
}

export interface Patient {
  id: string;
  name: string;
  sessionCount: number;
  activeSessions: number;
  completedSessions: number;
  avgPerformanceScore: number | null;
  lastActive?: string;
}

export interface DashboardStats {
  totalPatients: number;
  totalSessions: number;
  activePatients: number;
  avgPerformanceScore: number | null;
}

export interface Exercise {
  id: string;
  name: string;
  joint_angle: string;
  movement_type: string;
  description: string;
  supported_sides?: ("left" | "right")[];
  side?: "left" | "right" | string;
}

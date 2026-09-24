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
  age?: number | null;
  gender?: string | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
  status?: "ACTIVE" | "INACTIVE" | string;
  created_at?: string;
  updated_at?: string;
}

export interface PatientAssignment {
  id: number;
  patient_id: string;
  exercise_id: string;
  exercise_name: string;
  side: "left" | "right";
  target_rom: number | null;
  target_repetitions: number | null;
  sessions_per_day: number;
  notes: string;
  active: boolean;
  assigned_at?: string;
  updated_at?: string;
}

export interface PatientCreatePayload {
  patient_id: string;
  name: string;
  age?: number | null;
  gender?: string | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
}

export interface PatientUpdatePayload {
  name?: string;
  age?: number | null;
  gender?: string | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
  status?: "ACTIVE" | "INACTIVE" | string;
}

export interface AssignmentCreatePayload {
  exercise_id: string;
  side: "left" | "right";
  target_rom?: number | null;
  target_repetitions?: number | null;
  sessions_per_day?: number | null;
  notes?: string;
}

export interface AssignmentUpdatePayload {
  target_rom?: number | null;
  target_repetitions?: number | null;
  sessions_per_day?: number | null;
  notes?: string;
  active?: boolean;
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

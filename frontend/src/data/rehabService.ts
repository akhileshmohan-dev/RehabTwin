/**
 * Data access layer for RehabTwin.
 * Purely backend-driven — no mock data or synthetic clinical metrics.
 */
import type {
  DashboardStats,
  Patient,
  Session,
  SessionStatus,
  Exercise,
  MovementQuality,
  PatientAssignment,
  PatientCreatePayload,
  PatientUpdatePayload,
  AssignmentCreatePayload,
  AssignmentUpdatePayload,
} from "@/types/rehab";

export const API_BASE_URL = import.meta.env["VITE_API_BASE_URL"] || "http://127.0.0.1:8000";

export function getWebSocketUrl(sessionId: string): string {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  return `${wsBase}/api/analysis/ws/${sessionId}`;
}

export async function fetchExercises(): Promise<Exercise[]> {
  const response = await fetch(`${API_BASE_URL}/api/analysis/exercises`);
  if (!response.ok) {
    throw new Error("Failed to fetch exercises");
  }
  const data = await response.json();
  return data.exercises || [];
}

export interface PatientsOverviewResponse {
  stats: DashboardStats;
  patients: Patient[];
}

export async function fetchPatientsOverview(): Promise<PatientsOverviewResponse> {
  const response = await fetch(`${API_BASE_URL}/api/patients`);
  if (!response.ok) throw new Error("Failed to fetch patients");

  const data = await response.json();

  const stats: DashboardStats = {
    totalPatients: data.total_patients ?? 0,
    totalSessions: data.total_sessions ?? 0,
    activePatients: data.active_patients ?? 0,
    avgPerformanceScore: data.average_performance_score ?? null,
  };

  const patients: Patient[] = (data.patients || []).map((p: any) => ({
    id: p.patient_id,
    name: p.name || p.patient_id,
    sessionCount: p.total_sessions ?? 0,
    activeSessions: p.active_sessions ?? 0,
    completedSessions: p.completed_sessions ?? 0,
    avgPerformanceScore: p.average_performance_score ?? null,
    lastActive: p.last_active,
    age: p.age,
    gender: p.gender,
    phone: p.phone,
    email: p.email,
    notes: p.notes,
    status: p.status || "ACTIVE",
    created_at: p.created_at,
    updated_at: p.updated_at,
  }));

  return { stats, patients };
}

export async function fetchPatients(): Promise<Patient[]> {
  const overview = await fetchPatientsOverview();
  return overview.patients;
}

export async function fetchPatient(patientId: string): Promise<Patient> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}`);
  if (!response.ok) throw new Error(`Failed to fetch patient ${patientId}`);
  const p = await response.json();
  return {
    id: p.patient_id,
    name: p.name || p.patient_id,
    sessionCount: 0,
    activeSessions: 0,
    completedSessions: 0,
    avgPerformanceScore: null,
    age: p.age,
    gender: p.gender,
    phone: p.phone,
    email: p.email,
    notes: p.notes,
    status: p.status || "ACTIVE",
    created_at: p.created_at,
    updated_at: p.updated_at,
  };
}

export async function createPatient(data: PatientCreatePayload): Promise<Patient> {
  const response = await fetch(`${API_BASE_URL}/api/patients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    let errorMsg = `Failed to create patient: ${response.statusText}`;
    try {
      const err = await response.json();
      if (err.detail) errorMsg = err.detail;
    } catch {}
    throw new Error(errorMsg);
  }
  const p = await response.json();
  return {
    id: p.patient_id,
    name: p.name,
    sessionCount: 0,
    activeSessions: 0,
    completedSessions: 0,
    avgPerformanceScore: null,
    age: p.age,
    gender: p.gender,
    phone: p.phone,
    email: p.email,
    notes: p.notes,
    status: p.status || "ACTIVE",
    created_at: p.created_at,
    updated_at: p.updated_at,
  };
}

export async function updatePatient(patientId: string, updates: PatientUpdatePayload): Promise<Patient> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!response.ok) {
    let errorMsg = `Failed to update patient: ${response.statusText}`;
    try {
      const err = await response.json();
      if (err.detail) errorMsg = err.detail;
    } catch {}
    throw new Error(errorMsg);
  }
  const p = await response.json();
  return {
    id: p.patient_id,
    name: p.name,
    sessionCount: 0,
    activeSessions: 0,
    completedSessions: 0,
    avgPerformanceScore: null,
    age: p.age,
    gender: p.gender,
    phone: p.phone,
    email: p.email,
    notes: p.notes,
    status: p.status || "ACTIVE",
    created_at: p.created_at,
    updated_at: p.updated_at,
  };
}

export async function deactivatePatient(patientId: string): Promise<Patient> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    let errorMsg = `Failed to deactivate patient: ${response.statusText}`;
    try {
      const err = await response.json();
      if (err.detail) errorMsg = err.detail;
    } catch {}
    throw new Error(errorMsg);
  }
  const p = await response.json();
  return {
    id: p.patient_id,
    name: p.name,
    sessionCount: 0,
    activeSessions: 0,
    completedSessions: 0,
    avgPerformanceScore: null,
    age: p.age,
    gender: p.gender,
    phone: p.phone,
    email: p.email,
    notes: p.notes,
    status: p.status || "INACTIVE",
    created_at: p.created_at,
    updated_at: p.updated_at,
  };
}

export async function fetchPatientAssignments(patientId: string, activeOnly = false): Promise<PatientAssignment[]> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}/exercises?active_only=${activeOnly}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch exercise assignments for ${patientId}`);
  }
  const data = await response.json();
  return data.assignments || [];
}

export async function assignExercise(patientId: string, data: AssignmentCreatePayload): Promise<PatientAssignment> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}/exercises`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    let errorMsg = `Failed to assign exercise: ${response.statusText}`;
    try {
      const err = await response.json();
      if (err.detail) errorMsg = err.detail;
    } catch {}
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function updateAssignment(patientId: string, assignmentId: number, data: AssignmentUpdatePayload): Promise<PatientAssignment> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}/exercises/${assignmentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    let errorMsg = `Failed to update assignment: ${response.statusText}`;
    try {
      const err = await response.json();
      if (err.detail) errorMsg = err.detail;
    } catch {}
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function deactivateAssignment(patientId: string, assignmentId: number): Promise<PatientAssignment> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}/exercises/${assignmentId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    let errorMsg = `Failed to deactivate assignment: ${response.statusText}`;
    try {
      const err = await response.json();
      if (err.detail) errorMsg = err.detail;
    } catch {}
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function fetchPatientSessions(patientId: string): Promise<Session[]> {
  const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}/sessions`);

  if (!response.ok) {
    throw new Error(`Failed to fetch sessions for ${patientId}`);
  }

  const data = await response.json();

  const mappedSessions: Session[] = (data.sessions || []).map(
    (
      session: {
        session_id: string;
        patient_id: string;
        exercise: string;
        side?: string;
        started_at?: string;
        ended_at?: string;
        status: string;
        results?: any[];
      },
      index: number
    ) => {
      const result = session.results && session.results.length > 0 ? session.results[0] : null;
      const rawSide = (session.side || (result && result.side) || "left").trim().toLowerCase();
      const side: "left" | "right" = rawSide === "right" ? "right" : "left";

      const hasResult = result !== null && result !== undefined;
      const reps = hasResult ? Number(result.repetitions || 0) : 0;
      const rom =
        hasResult && result.rom_max != null && result.rom_min != null
          ? Math.round(result.rom_max - result.rom_min)
          : 0;
      const score =
        hasResult && result.performance_score != null ? Math.round(result.performance_score) : null;

      let quality: MovementQuality | undefined = undefined;
      if (score !== null) {
        if (score >= 85) quality = "Excellent";
        else if (score >= 70) quality = "Good";
        else if (score >= 55) quality = "Fair";
        else quality = "Poor";
      }

      return {
        id: index + 1,
        rawSessionId: session.session_id,
        patientId: session.patient_id,
        dateTime: session.started_at || new Date().toISOString(),
        endedAt: session.ended_at,
        exercise: session.exercise
          .split("_")
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" "),
        exerciseId: session.exercise,
        side: side,
        repetitions: reps,
        rom: rom,
        quality: quality,
        score: score,
        status: (session.status || "ACTIVE") as SessionStatus,
        hasResult: hasResult,
        feedback: result?.feedback || "",
      };
    }
  );

  // Explicit newest-first sorting guarantee by started_at timestamp
  return mappedSessions.sort(
    (a, b) => new Date(b.dateTime).getTime() - new Date(a.dateTime).getTime()
  );
}

// Session execution functions preserved for the Patient Portal
export async function startSession(
  patientId: string,
  assignmentId?: number,
  exercise?: string,
  side?: string
) {
  const payload: any = { patient_id: patientId };
  if (assignmentId !== undefined && assignmentId !== null) {
    payload.assignment_id = assignmentId;
  }
  if (exercise) {
    payload.exercise = exercise;
  }
  if (side) {
    payload.side = side;
  }

  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      if (errorJson?.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {}
    console.error(`Error starting session (${response.status}):`, errorDetail);
    throw new Error(errorDetail || `Failed to start session: ${response.statusText}`);
  }

  return await response.json();
}

export async function endSession(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/end`, {
    method: "POST",
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      if (errorJson?.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // ignore JSON parse error
    }
    console.error(`Error ending session ${sessionId} (${response.status}):`, errorDetail);
    throw new Error(errorDetail || `Failed to end session: ${response.statusText}`);
  }

  return await response.json();
}

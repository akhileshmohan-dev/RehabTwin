import { createFileRoute } from '@tanstack/react-router'
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  TrendingUp,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Sidebar } from "@/components/therapist/layout/Sidebar";
import { Header } from "@/components/therapist/layout/Header";
import { MetricCard } from "@/components/therapist/dashboard/MetricCard";
import { PatientList } from "@/components/therapist/patients/PatientList";
import { PatientDetails } from "@/components/therapist/patients/PatientDetails";
import { LatestSession } from "@/components/therapist/sessions/LatestSession";
import { ProgressCharts } from "@/components/therapist/dashboard/ProgressCharts";
import { SessionComparison } from "@/components/therapist/dashboard/SessionComparison";
import { RecentSessions } from "@/components/therapist/sessions/RecentSessions";
import { ScrollReveal } from "@/components/animations/ScrollReveal";
import { SkeletonPatientDetails } from "@/components/ui/SkeletonLoader";
import {
  fetchPatientSessions,
  fetchPatientsOverview,
} from "@/data/rehabService";
import type { DashboardStats, Patient, Session } from "@/types/rehab";

export const Route = createFileRoute("/therapist")({
  head: () => ({
    meta: [
      { title: "RehabTwin — Therapist Dashboard" },
      {
        name: "description",
        content:
          "Track patient rehabilitation progress: ROM trends, performance scores, session comparison and recent sessions.",
      },
      { property: "og:title", content: "RehabTwin — Therapist Dashboard" },
      {
        property: "og:description",
        content:
          "Clinical dashboard for physiotherapists to monitor patient recovery, ROM and performance trends.",
      },
    ],
  }),
  component: Dashboard,
});

export function Dashboard() {
  const [nav, setNav] = useState("Dashboard");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [stats, setStats] = useState<DashboardStats>({
    totalPatients: 0,
    totalSessions: 0,
    activePatients: 0,
    avgPerformanceScore: null,
  });
  const [isSidebarMobileOpen, setIsSidebarMobileOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  // Dual-guard race condition protection refs
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const requestSeqRef = useRef(0);

  const loadSessions = useCallback(async (patientId: string) => {
    if (!patientId) {
      setSessions([]);
      return;
    }
    const seq = ++requestSeqRef.current;
    try {
      const data = await fetchPatientSessions(patientId);
      // Dual guard: verify request token AND selected patient identity
      if (seq === requestSeqRef.current && patientId === selectedIdRef.current) {
        setSessions(data);
      }
    } catch (err) {
      if (seq === requestSeqRef.current && patientId === selectedIdRef.current) {
        console.error("Failed to fetch patient sessions:", err);
        setSessions([]);
      }
    }
  }, []);

  const loadData = useCallback(async (isInitial = false) => {
    try {
      const overview = await fetchPatientsOverview();
      setIsError(false);
      setStats(overview.stats);
      setPatients(overview.patients);

      let currentSelected = selectedIdRef.current;
      if (!currentSelected && overview.patients.length > 0 && overview.patients[0]) {
        currentSelected = overview.patients[0].id;
        setSelectedId(currentSelected);
        selectedIdRef.current = currentSelected;
      } else if (currentSelected && !overview.patients.some((p) => p.id === currentSelected)) {
        currentSelected = overview.patients[0]?.id || "";
        setSelectedId(currentSelected);
        selectedIdRef.current = currentSelected;
      }

      if (currentSelected) {
        await loadSessions(currentSelected);
      } else {
        setSessions([]);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
      setIsError(true);
    } finally {
      if (isInitial) {
        setIsLoading(false);
      }
    }
  }, [loadSessions]);

  useEffect(() => {
    setIsLoading(true);
    loadData(true);

    const interval = setInterval(() => {
      loadData(false);
    }, 5000);

    return () => clearInterval(interval);
  }, [loadData]);

  const handleSelectPatient = (id: string) => {
    if (id === selectedId) return;
    setSelectedId(id);
    selectedIdRef.current = id;
    loadSessions(id);
  };

  const patient = useMemo(() => {
    return patients.find((p) => p.id === selectedId);
  }, [patients, selectedId]);

  // Sessions are newest-first, so sessions[0] is latest
  const latest = useMemo(
    () => (sessions.length > 0 ? sessions[0] : undefined),
    [sessions],
  );

  return (
    <div className="flex min-h-screen w-full bg-background relative overflow-x-hidden">
      {/* Mobile Drawer Sidebar */}
      {isSidebarMobileOpen ? (
        <div
          className="fixed inset-0 z-45 bg-black/40 backdrop-blur-xs md:hidden animate-backdrop-fade"
          onClick={() => setIsSidebarMobileOpen(false)}
        />
      ) : null}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 md:hidden sidebar-slide-in",
          isSidebarMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <Sidebar active={nav} onSelect={setNav} onClose={() => setIsSidebarMobileOpen(false)} />
      </div>

      {/* Desktop Sidebar */}
      <div className="hidden md:block md:w-[260px] md:shrink-0">
        <div className="fixed inset-y-0 left-0 z-30 w-[260px]">
          <Sidebar active={nav} onSelect={setNav} />
        </div>
      </div>

      <main className="min-w-0 flex-1 p-6 flex flex-col justify-between page-fade-in">
        <div>
          <Header onToggleSidebar={() => setIsSidebarMobileOpen(true)} />

          {/* Connection Error State */}
          {isError && (
            <div className="mb-6 p-4 rounded-lg border border-destructive/50 bg-destructive/10 text-destructive flex flex-col items-center justify-center">
              <AlertTriangle className="h-8 w-8 mb-2" />
              <h3 className="font-semibold text-lg">Connection Error</h3>
              <p className="text-sm">Could not connect to the backend API. Please ensure the server is running.</p>
              <button 
                className="mt-4 px-4 py-2 bg-destructive text-destructive-foreground rounded-md text-sm font-medium hover:bg-destructive/90 transition-colors"
                onClick={() => loadData(true)}
              >
                Retry Connection
              </button>
            </div>
          )}

          {/* Metric Cards Grid */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <ScrollReveal className="w-full" delay={0}>
              <MetricCard
                icon={Users}
                label="Total Patients"
                value={String(stats.totalPatients)}
                sub="Registered in thread"
              />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={60}>
              <MetricCard
                icon={CalendarDays}
                label="Total Sessions"
                value={String(stats.totalSessions)}
                sub="Executed sessions"
              />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={120}>
              <MetricCard
                icon={Activity}
                label="Active Patients"
                value={String(stats.activePatients)}
                sub={stats.activePatients > 0 ? "Currently in session" : "No active sessions"}
                tone={stats.activePatients > 0 ? "warning" : "default"}
              />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={180}>
              <MetricCard
                icon={TrendingUp}
                label="Average Performance Score"
                value={stats.avgPerformanceScore !== null ? `${stats.avgPerformanceScore}%` : "—"}
                sub="Completed with results"
                tone="success"
              />
            </ScrollReveal>
          </div>

          {/* Empty State Banner if no patients exist */}
          {!isLoading && !isError && patients.length === 0 && (
            <div className="mt-6 p-6 rounded-xl border border-dashed border-border bg-card/50 text-center">
              <Users className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <h3 className="font-medium text-base text-foreground">No patients registered in the digital thread</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Start a session in the Patient Portal to initialize patient rehabilitation records.
              </p>
            </div>
          )}

          {/* Patient Details & Trends */}
          <div className="mt-5 grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_minmax(0,1.05fr)]">
            <ScrollReveal className="w-full" delay={100}>
              <PatientList
                patients={patients}
                selectedId={selectedId}
                onSelect={handleSelectPatient}
              />
            </ScrollReveal>

            <div className="space-y-5">
              <ScrollReveal className="w-full" delay={150}>
                {isLoading ? (
                  <SkeletonPatientDetails />
                ) : patient ? (
                  <PatientDetails patient={patient} />
                ) : (
                  <div className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground text-center">
                    Select a patient to view clinical profile
                  </div>
                )}
              </ScrollReveal>
              
              <ScrollReveal className="w-full" delay={200}>
                {isLoading ? (
                  <div className="rounded-2xl border border-border bg-card p-5 animate-shimmer h-[160px]" />
                ) : (
                  <LatestSession session={latest} />
                )}
              </ScrollReveal>
            </div>

            <ScrollReveal className="w-full" delay={250}>
              <ProgressCharts sessions={sessions} />
            </ScrollReveal>
          </div>

          {/* Comparisons & Recent Sessions */}
          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <ScrollReveal className="w-full" delay={300}>
              <SessionComparison sessions={sessions} />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={350}>
              <RecentSessions sessions={sessions} />
            </ScrollReveal>
          </div>
        </div>

        <footer className="mt-8 flex flex-wrap justify-end gap-3 text-xs text-muted-foreground border-t border-border/40 pt-4">
          <span>RehabTwin © 2026</span>
          <span>|</span>
          <span>Therapist Dashboard (Live Digital Thread)</span>
        </footer>
      </main>
    </div>
  );
}

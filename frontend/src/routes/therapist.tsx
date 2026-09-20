import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
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
import { AddPatientModal } from "@/components/therapist/patients/AddPatientModal";
import { LatestSession } from "@/components/therapist/sessions/LatestSession";
import { ProgressCharts } from "@/components/therapist/dashboard/ProgressCharts";
import { SessionComparison } from "@/components/therapist/dashboard/SessionComparison";
import { RecentSessions } from "@/components/therapist/sessions/RecentSessions";
import { ScrollReveal } from "@/components/animations/ScrollReveal";
import { SkeletonPatientDetails } from "@/components/ui/SkeletonLoader";
import {
  getLatestSession,
  getPatients,
  getSessions,
} from "@/data/rehabService";
import type { Patient } from "@/types/rehab";

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

function Dashboard() {
  const [nav, setNav] = useState("Dashboard");
  const [patients, setPatients] = useState<Patient[]>(() => getPatients());
  const [selectedId, setSelectedId] = useState(patients[0]?.id ?? "");
  const [isSidebarMobileOpen, setIsSidebarMobileOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const patient = useMemo(() => {
    return patients.find((p) => p.id === selectedId);
  }, [patients, selectedId]);

  const sessions = useMemo(() => getSessions(selectedId), [selectedId]);
  const latest = useMemo(() => getLatestSession(selectedId), [selectedId]);
  
  const stats = useMemo(() => {
    const total = patients.length;
    const improving = patients.filter((p) => p.status !== "Attention").length;
    const needAttention = total - improving;
    const avg = total > 0 
      ? Math.round(patients.reduce((sum, p) => sum + p.recoveryScore, 0) / total) 
      : 0;
    
    return {
      totalPatients: total,
      totalSessionsThisWeek: 24 + (patients.length - 5) * 2, // Mock adjustment
      improving,
      needAttention,
      avgRecoveryScore: avg,
    };
  }, [patients]);

  const handleSelectPatient = (id: string) => {
    setIsLoading(true);
    setSelectedId(id);
    setTimeout(() => {
      setIsLoading(false);
    }, 450);
  };

  const handleAddPatient = (newPatient: Patient) => {
    setPatients((prev) => [...prev, newPatient]);
    setSelectedId(newPatient.id);
  };

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

          {/* Metric Cards Grid */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <ScrollReveal className="w-full" delay={0}>
              <MetricCard
                icon={Users}
                label="Total Patients"
                value={String(stats.totalPatients)}
                sub="All Patients"
              />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={60}>
              <MetricCard
                icon={CalendarDays}
                label="Total Sessions"
                value={String(stats.totalSessionsThisWeek)}
                sub="This Week"
              />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={120}>
              <MetricCard
                icon={TrendingUp}
                label="Patients Improving"
                value={String(stats.improving)}
                sub={`${Math.round((stats.improving / (stats.totalPatients || 1)) * 100)}% of total`}
                tone="success"
              />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={180}>
              <MetricCard
                icon={AlertTriangle}
                label="Need Attention"
                value={String(stats.needAttention)}
                sub={`${Math.round((stats.needAttention / (stats.totalPatients || 1)) * 100)}% of total`}
                tone="warning"
              />
            </ScrollReveal>
            <ScrollReveal className="w-full" delay={240}>
              <MetricCard
                icon={TrendingUp}
                label="Avg. Recovery Score"
                value={`${stats.avgRecoveryScore}%`}
                sub="Overall Average"
              />
            </ScrollReveal>
          </div>

          {/* Patient Details & Trends */}
          <div className="mt-5 grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_minmax(0,1.05fr)]">
            <ScrollReveal className="w-full" delay={100}>
              <PatientList
                patients={patients}
                selectedId={selectedId}
                onSelect={handleSelectPatient}
                onAddNew={() => setIsModalOpen(true)}
              />
            </ScrollReveal>

            <div className="space-y-5">
              <ScrollReveal className="w-full" delay={150}>
                {isLoading ? (
                  <SkeletonPatientDetails />
                ) : patient ? (
                  <PatientDetails patient={patient} />
                ) : null}
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
          <span>Therapist Dashboard (Demo Mode)</span>
        </footer>
      </main>

      {/* Add Patient Modal */}
      <AddPatientModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAdd={handleAddPatient}
      />
    </div>
  );
}

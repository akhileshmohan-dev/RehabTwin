import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import {
  Activity,
  ArrowRight,
  Sparkles,
  Stethoscope,
  User,
} from "lucide-react";
import { ScrollReveal } from "@/components/animations/ScrollReveal";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "RehabTwin — Portal Hub" },
      {
        name: "description",
        content:
          "Select your portal: Therapist Dashboard or Patient rehabilitation progress tracking.",
      },
    ],
  }),
  component: PortalHub,
});

function PortalHub() {
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const handlePatientClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setToastMessage("Patient Portal is currently under construction. Stay tuned!");
    setTimeout(() => setToastMessage(null), 3000);
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12 overflow-x-hidden font-sans">
      {/* Decorative Radial Background Gradients */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,var(--color-primary-soft),transparent_50%)] opacity-70 pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,var(--color-secondary),transparent_50%)] opacity-30 pointer-events-none" />

      {/* Main Container */}
      <div className="z-10 w-full max-w-4xl text-center space-y-12">
        {/* Header */}
        <ScrollReveal className="space-y-4" delay={0}>
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-4 py-1.5 text-sm font-semibold text-primary">
            <Activity className="size-4 animate-pulse" />
            <span>Next-Gen Physical Rehabilitation</span>
          </div>
          
          <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-6xl">
            Welcome to <span className="bg-gradient-to-r from-primary to-emerald-600 bg-clip-text text-transparent">RehabTwin</span>
          </h1>
          <p className="mx-auto max-w-2xl text-lg text-muted-foreground sm:text-xl">
            A comprehensive clinical platform for therapists and patients. Monitor Range of Motion, track bio-feedback sessions, and optimize recovery paths.
          </p>
        </ScrollReveal>

        {/* Portal Grid */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Therapist Portal Card */}
          <ScrollReveal className="w-full" delay={100}>
            <Link
              to="/therapist"
              className="group relative flex h-full flex-col justify-between rounded-3xl border border-border bg-card p-8 text-left shadow-card hover:border-primary/40 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-1"
            >
              <div className="absolute top-4 right-4 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                Active Portal
              </div>

              <div className="space-y-4">
                <div className="flex size-14 items-center justify-center rounded-2xl bg-primary-soft border border-primary/10 text-primary group-hover:scale-110 transition-transform duration-300">
                  <Stethoscope className="size-7" />
                </div>

                <div className="space-y-2">
                  <h2 className="text-2xl font-bold text-foreground">Therapist Portal</h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Access the clinician dashboard to review patient recovery scores, graph ROM (Range of Motion) progress, analyze latest bio-feedback session values, and register new patients.
                  </p>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between text-sm font-bold text-primary">
                <span>Enter Therapist View</span>
                <ArrowRight className="size-4 transform group-hover:translate-x-1.5 transition-transform" />
              </div>
            </Link>
          </ScrollReveal>

          {/* Patient Portal Card */}
          <ScrollReveal className="w-full" delay={200}>
            <Link
              to="/patient"
              search={{ patientId: undefined }}
              className="group relative flex h-full flex-col justify-between rounded-3xl border border-border bg-card p-8 text-left shadow-card hover:border-emerald-600/30 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-1"
            >
              <div className="absolute top-4 right-4 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                Active Portal
              </div>

              <div className="space-y-4">
                <div className="flex size-14 items-center justify-center rounded-2xl bg-emerald-500/10 border border-emerald-500/10 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform duration-300">
                  <User className="size-7" />
                </div>

                <div className="space-y-2">
                  <h2 className="text-2xl font-bold text-foreground">Patient Portal</h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Perform assigned clinical exercises, record bio-feedback metrics using sensor twins, track joint angles, and consult personalized therapy routines.
                  </p>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between text-sm font-bold text-emerald-600 dark:text-emerald-400">
                <span>Enter Patient View</span>
                <ArrowRight className="size-4 transform group-hover:translate-x-1.5 transition-transform" />
              </div>
            </Link>
          </ScrollReveal>
        </div>

        {/* Footer */}
        <ScrollReveal className="text-xs text-muted-foreground pt-6 border-t border-border/40" delay={300}>
          <p>RehabTwin Project Hub © 2026 · Group Mini Project</p>
        </ScrollReveal>
      </div>
    </div>
  );
}

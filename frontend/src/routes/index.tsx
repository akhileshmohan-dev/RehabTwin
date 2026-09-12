import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Activity,
  ArrowRight,
  Crosshair,
  ScanLine,
  ShieldCheck,
  Stethoscope,
  User,
  Waves,
} from "lucide-react";
import { ScrollReveal } from "@/components/animations/ScrollReveal";
import { Logo } from "@/components/common/Logo";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "RehabTwin — Motion Intelligence" },
      {
        name: "description",
        content:
          "RehabTwin brings motion capture, clinical insight, and your digital body model into one rehabilitation platform.",
      },
    ],
  }),
  component: PortalHub,
});

function BodyTwin() {
  return (
    <div className="twin-stage" aria-label="Illustration of a digital rehabilitation body model">
      <div className="twin-orbit twin-orbit-one" />
      <div className="twin-orbit twin-orbit-two" />
      <div className="twin-grid" />
      <div className="twin-scanline" />
      <div className="twin-model" aria-hidden="true">
        <span className="twin-head" />
        <span className="twin-neck" />
        <span className="twin-torso" />
        <span className="twin-arm twin-arm-left" />
        <span className="twin-arm twin-arm-right" />
        <span className="twin-leg twin-leg-left" />
        <span className="twin-leg twin-leg-right" />
        <i className="twin-joint twin-joint-shoulder-left" />
        <i className="twin-joint twin-joint-shoulder-right" />
        <i className="twin-joint twin-joint-elbow-left" />
        <i className="twin-joint twin-joint-elbow-right" />
        <i className="twin-joint twin-joint-knee-left" />
        <i className="twin-joint twin-joint-knee-right" />
      </div>
      <div className="twin-reading twin-reading-top"><span>SHOULDER</span><strong>142°</strong></div>
      <div className="twin-reading twin-reading-side"><span>SYNC</span><strong>98.4%</strong></div>
      <div className="twin-status"><span className="twin-status-dot" /> LIVE MOTION CAPTURE</div>
    </div>
  );
}

function PortalHub() {
  return (
    <main className="twin-home min-h-screen overflow-hidden px-5 py-6 sm:px-8 lg:px-12">
      <div className="twin-noise" />
      <nav className="relative z-10 mx-auto flex max-w-7xl items-center justify-between">
        <Logo variant="horizontal" size="md" />
        <div className="hidden items-center gap-7 text-sm text-slate-400 md:flex">
          <span>Motion intelligence</span>
          <span>Clinical workspace</span>
          <span className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 font-semibold text-cyan-100">System online</span>
        </div>
      </nav>

      <section className="relative z-10 mx-auto grid max-w-7xl items-center gap-12 pb-12 pt-14 lg:grid-cols-[1.05fr_0.95fr] lg:py-20">
        <ScrollReveal className="max-w-2xl" delay={0}>
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 text-xs font-bold tracking-[0.16em] text-cyan-100">
            <ScanLine className="size-3.5" /> DIGITAL REHABILITATION TWIN
          </div>
          <h1 className="text-5xl font-extrabold leading-[0.96] tracking-[-0.055em] text-white sm:text-6xl lg:text-7xl">
            See recovery in<br />
            <span className="twin-gradient-text">another dimension.</span>
          </h1>
          <p className="mt-7 max-w-xl text-base leading-7 text-slate-300 sm:text-lg">
            RehabTwin turns each movement into a living clinical model—bringing pose tracking, range-of-motion analysis, and care decisions into one precise workspace.
          </p>
          <div className="mt-9 flex flex-wrap gap-3 text-sm">
            <span className="twin-feature"><Crosshair className="size-4" /> Kinematic tracking</span>
            <span className="twin-feature"><Waves className="size-4" /> Real-time feedback</span>
            <span className="twin-feature"><ShieldCheck className="size-4" /> Clinical oversight</span>
          </div>
        </ScrollReveal>

        <ScrollReveal className="w-full" delay={140}>
          <BodyTwin />
        </ScrollReveal>
      </section>

      <section className="relative z-10 mx-auto max-w-7xl pb-8">
        <div className="grid gap-4 md:grid-cols-2">
          <ScrollReveal className="w-full" delay={200}>
            <Link to="/therapist" className="twin-portal-card twin-portal-therapist group">
              <div className="flex items-start justify-between gap-4">
                <div className="twin-icon"><Stethoscope className="size-6" /></div>
                <span className="twin-card-label">CLINICIAN VIEW</span>
              </div>
              <div className="mt-10">
                <h2>Build the recovery picture.</h2>
                <p>Review patient movement data, compare sessions, and make confident care decisions from one command center.</p>
              </div>
              <div className="twin-card-action">Open therapist workspace <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" /></div>
            </Link>
          </ScrollReveal>

          <ScrollReveal className="w-full" delay={280}>
            <Link to="/patient" search={{ patientId: undefined }} className="twin-portal-card twin-portal-patient group">
              <div className="flex items-start justify-between gap-4">
                <div className="twin-icon twin-icon-lilac"><User className="size-6" /></div>
                <span className="twin-card-label">PATIENT VIEW</span>
              </div>
              <div className="mt-10">
                <h2>Move with clear guidance.</h2>
                <p>Follow your prescribed program, view live form feedback, and watch progress take shape over time.</p>
              </div>
              <div className="twin-card-action">Start your session <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" /></div>
            </Link>
          </ScrollReveal>
        </div>
        <footer className="mt-8 flex items-center justify-between border-t border-white/10 pt-5 text-xs text-slate-500">
          <span>REHABTWIN / MOTION INTELLIGENCE</span>
          <span className="flex items-center gap-1.5"><Activity className="size-3 text-cyan-300" /> Secure clinical workspace</span>
        </footer>
      </section>
    </main>
  );
}

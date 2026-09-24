/**
 * Therapist-facing modal that plays back a completed session on the 3D model.
 *
 * The heavy three.js viewer is lazy-loaded (client-only) so opening the
 * dashboard does not pull the 3D bundle until the therapist asks for a replay.
 */
import { Suspense, lazy, useEffect, useState } from "react";
import { AlertCircle, Download, Loader2, X } from "lucide-react";

import { API_BASE_URL, getSessionFrames } from "@/data/rehabService";
import { formatDateTime } from "@/lib/format";
import type { Patient, Session, SessionFramesResponse } from "@/types/rehab";

const SessionReplay3D = lazy(() => import("./SessionReplay3D"));

export interface SessionReplayModalProps {
  isOpen: boolean;
  onClose: () => void;
  session: Session | null;
  patient?: Patient | undefined;
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
      <span className="block text-[11px] font-medium text-muted-foreground">{label}</span>
      <span className="text-sm font-bold text-foreground">{value}</span>
    </div>
  );
}

export function SessionReplayModal({ isOpen, onClose, session, patient }: SessionReplayModalProps) {
  const [data, setData] = useState<SessionFramesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const sessionId = session?.rawSessionId;

  useEffect(() => {
    if (!isOpen || !sessionId) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setData(null);
    (async () => {
      try {
        const frames = await getSessionFrames(sessionId);
        if (!cancelled) setData(frames);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load session frames");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen, sessionId]);

  if (!isOpen || !session) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs animate-backdrop-fade"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        className="relative z-10 w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border bg-white dark:bg-card p-6 shadow-2xl animate-modal-scale-in"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="3D session replay"
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          aria-label="Close"
        >
          <X className="size-5" />
        </button>

        <div className="mb-4 pr-10">
          <h2 className="text-xl font-bold tracking-tight text-foreground">3D Session Replay</h2>
          <p className="text-xs text-muted-foreground">
            {patient ? `${patient.name} (${patient.id})` : session.patientId} · {session.exercise} ·{" "}
            {session.side}
          </p>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <InfoCell label="Date" value={formatDateTime(session.dateTime)} />
          <InfoCell label="Repetitions" value={session.hasResult ? String(session.repetitions) : "—"} />
          <InfoCell label="ROM Excursion" value={session.hasResult ? `${session.rom.toFixed(1)}°` : "—"} />
          <InfoCell
            label="Score"
            value={session.hasResult && session.score !== null ? `${session.score}%` : "—"}
          />
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <a
            href={`${API_BASE_URL}/api/sessions/${session.rawSessionId}/export.csv`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Download className="size-3.5" />
            Export CSV
          </a>
          <span className="text-xs text-muted-foreground">{session.rawSessionId}</span>
        </div>

        {error ? (
          <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-xs text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : loading || !data ? (
          <div className="flex h-72 items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <span className="text-xs">Loading session frames…</span>
          </div>
        ) : (
          <Suspense
            fallback={
              <div className="flex h-72 items-center justify-center gap-2 text-muted-foreground">
                <Loader2 className="size-5 animate-spin" />
                <span className="text-xs">Loading 3D viewer…</span>
              </div>
            }
          >
            <SessionReplay3D
              frames={data.frames}
              exercise={data.exercise}
              side={data.side}
              sessionId={data.session_id}
            />
          </Suspense>
        )}
      </div>
    </div>
  );
}

export default SessionReplayModal;

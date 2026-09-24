import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { fetchPatientSessions, fetchSessionFrames } from "@/data/rehabService";
import SessionReplay3D from "@/components/therapist/replay/SessionReplay3D";
import type { Session, SessionFramesResponse } from "@/types/rehab";

export const Route = createFileRoute("/replay-dev")({
  head: () => ({
    meta: [{ title: "RehabTwin — 3D Replay (dev)" }],
  }),
  component: ReplayDevPage,
});

const DEV = import.meta.env.DEV;

function ReplayDevPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [data, setData] = useState<SessionFramesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!DEV) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const list = await fetchPatientSessions("DEMO_001");
        if (cancelled) return;
        setSessions(list);
        const first = list[0];
        if (first) {
          setSelectedId(first.rawSessionId);
          setData(await fetchSessionFrames(first.rawSessionId));
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load demo sessions");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSelect = async (rawId: string) => {
    setSelectedId(rawId);
    setLoading(true);
    setError("");
    try {
      setData(await fetchSessionFrames(rawId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load frames");
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  if (!DEV) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-8">
        <p className="text-sm text-muted-foreground">The 3D replay dev page is only available in development.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-foreground">3D Replay — Dev</h1>
            <p className="text-xs text-muted-foreground">
              Loads seeded sessions for patient DEMO_001 (scripts/seed_demo_session.py).
            </p>
          </div>
          <select
            value={selectedId}
            onChange={(event) => handleSelect(event.target.value)}
            className="rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground"
          >
            <option value="" disabled>
              Select a session
            </option>
            {sessions.map((session) => (
              <option key={session.rawSessionId} value={session.rawSessionId}>
                {session.exercise} · {session.side} · {session.rawSessionId}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading && !data ? (
          <div className="flex h-80 items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <span className="text-xs">Loading frames…</span>
          </div>
        ) : data ? (
          <SessionReplay3D
            frames={data.frames}
            exercise={data.exercise}
            side={data.side}
            sessionId={data.session_id}
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            No seeded session found. Run <code>python scripts/seed_demo_session.py</code> first.
          </div>
        )}
      </div>
    </div>
  );
}

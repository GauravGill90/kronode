"use client";

import type { TaskEvent, TaskStatus } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import EventLine from "./EventLine";

interface ProgressStreamProps {
  liveEvents: TaskEvent[];
  historicalEvents: TaskEvent[];
  connected: boolean;
  status: TaskStatus;
}

export default function ProgressStream({ liveEvents, historicalEvents, connected, status }: ProgressStreamProps) {
  // Merge live + historical, deduplicate by id, sort by created_at
  const seen = new Set<string | number>();
  const merged: TaskEvent[] = [];
  for (const e of [...historicalEvents, ...liveEvents]) {
    const key = e.id ?? `${e.agent_name}-${e.event_type}-${e.message}`;
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(e);
    }
  }
  merged.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  if (merged.length === 0 && status === "queued") {
    return (
      <div
        className="rounded-2xl p-5 flex items-center gap-3 text-sm"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(99,102,241,0.15)", color: "#64748b" }}
      >
        <Spinner size="sm" />
        <span>Waiting to start…</span>
      </div>
    );
  }

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(99,102,241,0.15)" }}
    >
      <div
        className="px-5 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
      >
        <span className="text-sm font-medium" style={{ color: "#94a3b8" }}>Agent activity</span>
        {connected && (
          <span className="flex items-center gap-1.5 text-xs" style={{ color: "#34d399" }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "#34d399" }}></span>
            Live
          </span>
        )}
      </div>
      <div>
        {merged.length === 0 ? (
          <div className="px-5 py-4 text-sm" style={{ color: "#475569" }}>No activity yet.</div>
        ) : (
          merged.map((event, i) => <EventLine key={event.id ?? i} event={event} />)
        )}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import type { TaskEvent, TaskStatus } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import EventLine, { shouldShowEvent } from "./EventLine";

interface ProgressStreamProps {
  liveEvents: TaskEvent[];
  historicalEvents: TaskEvent[];
  connected: boolean;
  status: TaskStatus;
}

interface GroupedEvent {
  type: "single";
  event: TaskEvent;
}

interface GroupedProgress {
  type: "progress_group";
  agent_name: string;
  events: TaskEvent[];
}

type DisplayItem = GroupedEvent | GroupedProgress;

function groupEvents(events: TaskEvent[]): DisplayItem[] {
  const items: DisplayItem[] = [];
  let i = 0;

  while (i < events.length) {
    const event = events[i];

    // Group consecutive progress events from the same agent
    if (event.event_type === "progress") {
      const group: TaskEvent[] = [event];
      while (
        i + 1 < events.length &&
        events[i + 1].event_type === "progress" &&
        events[i + 1].agent_name === event.agent_name
      ) {
        i++;
        group.push(events[i]);
      }
      if (group.length > 1) {
        items.push({ type: "progress_group", agent_name: event.agent_name, events: group });
      } else {
        items.push({ type: "single", event });
      }
    } else {
      items.push({ type: "single", event });
    }
    i++;
  }
  return items;
}

export default function ProgressStream({ liveEvents, historicalEvents, connected, status }: ProgressStreamProps) {
  const seen = new Set<string | number>();
  const merged: TaskEvent[] = [];
  for (const e of [...historicalEvents, ...liveEvents]) {
    const key = e.id ?? `${e.agent_name}-${e.event_type}-${e.message}`;
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(e);
    }
  }
  merged.sort((a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime());

  // Filter out "starting..." events
  const visible = merged.filter(shouldShowEvent);

  if (visible.length === 0 && (status === "queued" || status === "running")) {
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

  const grouped = groupEvents(visible);

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
        {visible.length === 0 ? (
          <div className="px-5 py-4 text-sm" style={{ color: "#475569" }}>No activity yet.</div>
        ) : (
          grouped.map((item, i) =>
            item.type === "single" ? (
              <EventLine key={item.event.id ?? i} event={item.event} />
            ) : (
              <ProgressGroup key={`pg-${i}`} agent={item.agent_name} events={item.events} />
            )
          )
        )}
      </div>
    </div>
  );
}

const AGENT_ICONS: Record<string, string> = {
  router: "🗺️",
  ticket_interpreter: "🎫",
  context_builder: "📂",
  guardrails_agent: "🛡️",
  clarification_agent: "❓",
  planner_agent: "📋",
  plan_approval_agent: "📢",
  coder_agent: "💻",
  tester_agent: "🧪",
  execution_verifier: "✅",
  reviewer_agent: "🔍",
  memory_agent: "🧠",
  pipeline: "⚙️",
};

function ProgressGroup({ agent, events }: { agent: string; events: TaskEvent[] }) {
  const [expanded, setExpanded] = useState(false);
  const icon = AGENT_ICONS[agent] || "•";
  const latest = events[events.length - 1];
  const startTime = events[0].ts || events[0].created_at || "";
  const endTime = latest.ts || latest.created_at || "";

  return (
    <div style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
      <div
        className="flex items-start gap-3 px-5 py-3"
        style={{ cursor: "pointer" }}
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-base leading-none mt-0.5 flex-shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium capitalize" style={{ color: "#64748b" }}>
              {agent.replace(/_/g, " ")}
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{
                background: "rgba(99,102,241,0.1)",
                color: "#818cf8",
                border: "1px solid rgba(99,102,241,0.2)",
              }}
            >
              {events.length} steps
            </span>
          </div>
          <p className="text-sm mt-0.5" style={{ color: "#94a3b8" }}>
            {latest.message}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
          <span className="text-xs" style={{ color: "#818cf8" }}>
            {expanded ? "▾" : "▸"}
          </span>
          <span className="text-xs" style={{ color: "#334155" }}>
            {new Date(endTime).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        </div>
      </div>

      {expanded && (
        <div
          className="mx-5 mb-3 rounded-lg overflow-auto text-xs font-mono"
          style={{
            background: "rgba(0,0,0,0.25)",
            border: "1px solid rgba(99,102,241,0.1)",
            maxHeight: "300px",
          }}
        >
          {events.map((e, i) => (
            <div
              key={e.id ?? i}
              className="flex items-start gap-2 px-3 py-1.5"
              style={{ borderBottom: i < events.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}
            >
              <span style={{ color: "#334155", flexShrink: 0 }}>
                {new Date(e.ts || e.created_at || "").toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </span>
              <span style={{ color: "#94a3b8" }}>{e.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import type { TaskEvent } from "@/lib/types";

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

export default function EventLine({ event }: { event: TaskEvent }) {
  const [expanded, setExpanded] = useState(false);
  const icon = AGENT_ICONS[event.agent_name] || "•";
  const isError = event.event_type === "failed";
  const isComplete = event.event_type === "completed";
  const hasPayload = event.payload && Object.keys(event.payload).length > 0;

  return (
    <div
      style={{
        borderBottom: "1px solid rgba(255,255,255,0.04)",
        background: isError ? "rgba(239,68,68,0.06)" : "transparent",
      }}
    >
      <div
        className="flex items-start gap-3 px-5 py-3"
        style={{ cursor: hasPayload ? "pointer" : "default" }}
        onClick={() => hasPayload && setExpanded(!expanded)}
      >
        <span className="text-base leading-none mt-0.5 flex-shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium capitalize" style={{ color: "#64748b" }}>
              {event.agent_name.replace(/_/g, " ")}
            </span>
            {isComplete && <span className="text-xs" style={{ color: "#34d399" }}>✓</span>}
            {isError && <span className="text-xs" style={{ color: "#f87171" }}>✗</span>}
          </div>
          <p className="text-sm mt-0.5" style={{ color: isError ? "#f87171" : "#94a3b8" }}>
            {event.message}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
          {hasPayload && (
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{
                background: "rgba(99,102,241,0.1)",
                color: "#818cf8",
                border: "1px solid rgba(99,102,241,0.2)",
              }}
            >
              {expanded ? "▾" : "▸"} data
            </span>
          )}
          <span className="text-xs" style={{ color: "#334155" }}>
            {new Date(event.ts || event.created_at || "").toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        </div>
      </div>

      {expanded && hasPayload && (
        <div
          className="px-5 pb-4"
          style={{ paddingLeft: "3.25rem" }}
        >
          <div
            className="rounded-lg p-3 overflow-auto text-xs font-mono"
            style={{
              background: "rgba(0,0,0,0.3)",
              border: "1px solid rgba(99,102,241,0.12)",
              color: "#94a3b8",
              maxHeight: "400px",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {formatPayload(event.payload!)}
          </div>
        </div>
      )}
    </div>
  );
}

function formatPayload(payload: Record<string, unknown>): string {
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

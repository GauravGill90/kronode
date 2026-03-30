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

// Hide "starting..." events — they add noise
export function shouldShowEvent(event: TaskEvent): boolean {
  if (event.event_type === "started") return false;
  return true;
}

export default function EventLine({ event }: { event: TaskEvent }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const icon = AGENT_ICONS[event.agent_name] || "•";
  const isError = event.event_type === "failed";
  const isComplete = event.event_type === "completed";
  const hasPayload = event.payload && Object.keys(event.payload).length > 0;

  function handleCopy() {
    if (!event.payload) return;
    navigator.clipboard.writeText(JSON.stringify(event.payload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

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
            className="rounded-lg overflow-auto text-xs font-mono relative"
            style={{
              background: "rgba(0,0,0,0.3)",
              border: "1px solid rgba(99,102,241,0.12)",
              color: "#94a3b8",
              maxHeight: "400px",
            }}
          >
            <button
              onClick={(e) => { e.stopPropagation(); handleCopy(); }}
              className="absolute top-2 right-2 text-xs px-2 py-1 rounded transition-colors"
              style={{
                background: copied ? "rgba(52,211,153,0.15)" : "rgba(99,102,241,0.15)",
                color: copied ? "#34d399" : "#818cf8",
                border: `1px solid ${copied ? "rgba(52,211,153,0.3)" : "rgba(99,102,241,0.25)"}`,
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <pre className="p-3 whitespace-pre-wrap break-words">
              {formatPayload(event.payload!)}
            </pre>
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

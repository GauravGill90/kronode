import type { TaskEvent } from "@/lib/types";

const AGENT_ICONS: Record<string, string> = {
  router: "🗺️",
  context_builder: "📂",
  guardrails_agent: "🛡️",
  clarification_agent: "❓",
  planner_agent: "📋",
  coder_agent: "💻",
  tester_agent: "🧪",
  execution_verifier: "✅",
  reviewer_agent: "🔍",
  memory_agent: "🧠",
  pipeline: "⚙️",
};

export default function EventLine({ event }: { event: TaskEvent }) {
  const icon = AGENT_ICONS[event.agent_name] || "•";
  const isError = event.event_type === "failed";
  const isComplete = event.event_type === "completed";

  return (
    <div
      className="flex items-start gap-3 px-5 py-3"
      style={{
        borderBottom: "1px solid rgba(255,255,255,0.04)",
        background: isError ? "rgba(239,68,68,0.06)" : "transparent",
      }}
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
      <span className="text-xs flex-shrink-0 mt-0.5" style={{ color: "#334155" }}>
        {new Date(event.ts || event.created_at || "").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>
    </div>
  );
}

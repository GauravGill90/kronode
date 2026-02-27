import type { TaskEvent } from "@/lib/types";
import { clsx } from "clsx";

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
    <div className={clsx("flex items-start gap-3 px-5 py-3", isError && "bg-red-50")}>
      <span className="text-base leading-none mt-0.5 flex-shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500 capitalize">
            {event.agent_name.replace(/_/g, " ")}
          </span>
          {isComplete && <span className="text-xs text-green-600">✓</span>}
          {isError && <span className="text-xs text-red-600">✗</span>}
        </div>
        <p className={clsx("text-sm mt-0.5", isError ? "text-red-700" : "text-gray-700")}>
          {event.message}
        </p>
      </div>
      <span className="text-xs text-gray-300 flex-shrink-0 mt-0.5">
        {new Date(event.ts || event.created_at || "").toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>
    </div>
  );
}

import type { IntegrationStatus } from "@/lib/types";

const INTEGRATIONS = [
  { key: "github", label: "GitHub" },
  { key: "jira", label: "Jira" },
  { key: "slack", label: "Slack" },
  { key: "docs", label: "Docs" },
] as const;

export default function IntegrationRow({ integrations }: { integrations: IntegrationStatus }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {INTEGRATIONS.map(({ key, label }) => {
        const connected = integrations[key];
        return (
          <a
            key={key}
            href="/settings"
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full font-medium transition-all"
            style={
              connected
                ? { background: "rgba(52,211,153,0.08)", color: "#34d399", border: "1px solid rgba(52,211,153,0.2)" }
                : { background: "rgba(255,255,255,0.03)", color: "#475569", border: "1px solid rgba(255,255,255,0.06)" }
            }
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: connected ? "#34d399" : "#334155" }}
            ></span>
            {label}
          </a>
        );
      })}
    </div>
  );
}

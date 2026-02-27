interface AgentUnderstandingProps {
  agentName: string | null;
  agentAvatar: string | null;
  repoName: string | null;
  capabilities: Record<string, Record<string, boolean>> | null;
  guardrails: {
    restricted_paths: string[];
    max_files_per_task: number;
    risk_level: string;
  } | null;
  projectContext: string;
}

export default function AgentUnderstanding({
  agentName,
  agentAvatar,
  repoName,
  capabilities,
  guardrails,
  projectContext,
}: AgentUnderstandingProps) {
  const enabledCount = capabilities
    ? Object.values(capabilities).reduce(
        (sum, cat) => sum + Object.values(cat).filter(Boolean).length,
        0
      )
    : 0;

  const hasAnything = agentName || repoName || enabledCount || guardrails || projectContext;

  return (
    <div
      className="rounded-2xl p-5 space-y-4"
      style={{
        background: "rgba(99,102,241,0.03)",
        border: "1px solid rgba(99,102,241,0.12)",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <div
          className="w-2 h-2 rounded-full"
          style={{ background: hasAnything ? "#34d399" : "#1e293b" }}
        />
        <h3
          className="text-xs font-semibold uppercase tracking-wider"
          style={{ color: "#475569" }}
        >
          Agent Understanding
        </h3>
      </div>

      {/* Agent identity */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
          style={{
            background: "rgba(99,102,241,0.1)",
            border: "1px solid rgba(99,102,241,0.18)",
          }}
        >
          {agentAvatar || "🤖"}
        </div>
        <div>
          <div
            className="text-sm font-semibold"
            style={{ color: agentName ? "#e2e8f0" : "#1e293b" }}
          >
            {agentName || "Unnamed"}
          </div>
          <div className="text-xs" style={{ color: "#334155" }}>
            Autonomous developer
          </div>
        </div>
      </div>

      <div className="h-px" style={{ background: "rgba(99,102,241,0.08)" }} />

      {/* Fields */}
      <div className="space-y-2.5">
        <Row label="Repo" value={repoName || "—"} />
        <Row
          label="Capabilities"
          value={enabledCount ? `${enabledCount} enabled` : "—"}
        />
        <Row
          label="Off-limits"
          value={
            guardrails?.restricted_paths.length
              ? guardrails.restricted_paths.slice(0, 2).join(", ") +
                (guardrails.restricted_paths.length > 2 ? ` +${guardrails.restricted_paths.length - 2}` : "")
              : "—"
          }
        />
        <Row label="Risk level" value={guardrails?.risk_level || "—"} />

        {projectContext ? (
          <div>
            <div className="text-xs mb-1" style={{ color: "#475569" }}>
              Context
            </div>
            <p
              className="text-xs leading-relaxed"
              style={{ color: "#64748b" }}
            >
              {projectContext.slice(0, 130)}
              {projectContext.length > 130 ? "…" : ""}
            </p>
          </div>
        ) : (
          <Row label="Context" value="—" />
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const empty = value === "—";
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-xs flex-shrink-0" style={{ color: "#475569" }}>
        {label}
      </span>
      <span
        className="text-xs text-right truncate"
        style={{ color: empty ? "#1e293b" : "#94a3b8" }}
      >
        {value}
      </span>
    </div>
  );
}

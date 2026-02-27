interface SetupCardProps {
  icon: string;
  title: string;
  description: string;
  status: "completed" | "pending" | "optional" | "failed";
  index?: number;
  onClick: () => void;
}

export default function SetupCard({
  icon,
  title,
  description,
  status,
  index,
  onClick,
}: SetupCardProps) {
  const borderColor =
    status === "completed"
      ? "rgba(52,211,153,0.35)"
      : status === "failed"
      ? "rgba(239,68,68,0.35)"
      : status === "optional"
      ? "rgba(255,255,255,0.08)"
      : "rgba(99,102,241,0.2)";

  return (
    <button
      onClick={onClick}
      className="w-full text-left p-4 rounded-xl transition-all group"
      style={{
        background: status === "failed" ? "rgba(239,68,68,0.04)" : "rgba(255,255,255,0.02)",
        border: `1px solid ${borderColor}`,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.borderColor =
          status === "completed"
            ? "rgba(52,211,153,0.6)"
            : status === "failed"
            ? "rgba(239,68,68,0.6)"
            : "rgba(99,102,241,0.45)";
        (e.currentTarget as HTMLButtonElement).style.background =
          status === "failed" ? "rgba(239,68,68,0.07)" : "rgba(255,255,255,0.04)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.borderColor = borderColor;
        (e.currentTarget as HTMLButtonElement).style.background =
          status === "failed" ? "rgba(239,68,68,0.04)" : "rgba(255,255,255,0.02)";
      }}
    >
      <div className="flex items-start gap-3">
        {/* Icon ring */}
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-lg"
          style={{
            background:
              status === "completed"
                ? "rgba(52,211,153,0.1)"
                : status === "failed"
                ? "rgba(239,68,68,0.1)"
                : "rgba(99,102,241,0.1)",
            border:
              status === "completed"
                ? "1px solid rgba(52,211,153,0.3)"
                : status === "failed"
                ? "1px solid rgba(239,68,68,0.3)"
                : "1px solid rgba(99,102,241,0.2)",
          }}
        >
          {status === "completed" ? (
            <span style={{ color: "#34d399" }}>✓</span>
          ) : status === "failed" ? (
            <span style={{ color: "#f87171" }}>✗</span>
          ) : (
            icon
          )}
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
              {title}
            </span>
            {status === "completed" && (
              <span
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{ background: "rgba(52,211,153,0.1)", color: "#34d399" }}
              >
                Done
              </span>
            )}
            {status === "failed" && (
              <span
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}
              >
                Connection failed
              </span>
            )}
            {status === "optional" && (
              <span
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{ background: "rgba(255,255,255,0.05)", color: "#475569" }}
              >
                Optional
              </span>
            )}
            {status === "pending" && index != null && (
              <span
                className="text-xs w-4 h-4 rounded-full flex items-center justify-center ml-auto"
                style={{ background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }}
              >
                {index}
              </span>
            )}
          </div>
          <p className="text-xs mt-0.5" style={{ color: status === "failed" ? "#ef4444" : "#64748b" }}>
            {description}
          </p>
        </div>

        {/* Arrow hint */}
        <span
          className="text-xs opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5"
          style={{ color: status === "failed" ? "#f87171" : "#6366f1" }}
        >
          {status === "completed" ? "Edit" : status === "failed" ? "Retry" : "Set up"} →
        </span>
      </div>
    </button>
  );
}

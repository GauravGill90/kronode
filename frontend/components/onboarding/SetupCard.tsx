import React from "react";

interface SetupCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  status: "completed" | "pending" | "optional" | "failed";
  index?: number;
  onClick: () => void;
}

export default function SetupCard({ icon, title, description, status, index, onClick }: SetupCardProps) {
  const borderColor =
    status === "completed" ? "rgba(74,222,128,0.3)"
    : status === "failed" ? "rgba(248,113,113,0.3)"
    : status === "optional" ? "rgba(255,255,255,0.06)"
    : "rgba(212,168,83,0.2)";

  return (
    <button
      onClick={onClick}
      className="w-full text-left p-4 rounded-xl transition-all group"
      style={{
        background: status === "failed" ? "rgba(248,113,113,0.04)" : "rgba(255,255,255,0.02)",
        border: `1px solid ${borderColor}`,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.borderColor =
          status === "completed" ? "rgba(74,222,128,0.5)"
          : status === "failed" ? "rgba(248,113,113,0.5)"
          : "rgba(212,168,83,0.4)";
        (e.currentTarget as HTMLButtonElement).style.background =
          status === "failed" ? "rgba(248,113,113,0.06)" : "rgba(255,255,255,0.04)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.borderColor = borderColor;
        (e.currentTarget as HTMLButtonElement).style.background =
          status === "failed" ? "rgba(248,113,113,0.04)" : "rgba(255,255,255,0.02)";
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-lg"
          style={{
            background:
              status === "completed" ? "rgba(74,222,128,0.1)"
              : status === "failed" ? "rgba(248,113,113,0.1)"
              : "rgba(212,168,83,0.1)",
            border:
              status === "completed" ? "1px solid rgba(74,222,128,0.25)"
              : status === "failed" ? "1px solid rgba(248,113,113,0.25)"
              : "1px solid rgba(212,168,83,0.2)",
          }}
        >
          {status === "completed" ? (
            <span style={{ color: "#4ade80" }}>✓</span>
          ) : status === "failed" ? (
            <span style={{ color: "#f87171" }}>✗</span>
          ) : (
            icon
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-sm font-semibold" style={{ color: "#e7e0d8" }}>{title}</span>
            {status === "completed" && (
              <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ background: "rgba(74,222,128,0.1)", color: "#4ade80" }}>Done</span>
            )}
            {status === "failed" && (
              <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ background: "rgba(248,113,113,0.1)", color: "#f87171" }}>Failed</span>
            )}
            {status === "optional" && (
              <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ background: "rgba(255,255,255,0.05)", color: "#6b6560" }}>Optional</span>
            )}
            {status === "pending" && index != null && (
              <span className="text-xs w-4 h-4 rounded-full flex items-center justify-center ml-auto" style={{ background: "rgba(212,168,83,0.2)", color: "#d4a853" }}>{index}</span>
            )}
          </div>
          <p className="text-xs mt-0.5" style={{ color: status === "failed" ? "#f87171" : "#6b6560" }}>{description}</p>
        </div>

        <span className="text-xs opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5" style={{ color: status === "failed" ? "#f87171" : "#d4a853" }}>
          {status === "completed" ? "Edit" : status === "failed" ? "Retry" : "Set up"} →
        </span>
      </div>
    </button>
  );
}

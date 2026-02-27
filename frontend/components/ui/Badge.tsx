import { clsx } from "clsx";

type BadgeVariant = "default" | "success" | "warning" | "error" | "info" | "queued" | "running";

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

const VARIANT_STYLES: Record<BadgeVariant, React.CSSProperties> = {
  default: { background: "rgba(255,255,255,0.06)", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.08)" },
  queued:  { background: "rgba(255,255,255,0.05)", color: "#64748b", border: "1px solid rgba(255,255,255,0.06)" },
  success: { background: "rgba(52,211,153,0.1)",   color: "#34d399", border: "1px solid rgba(52,211,153,0.2)"  },
  warning: { background: "rgba(234,179,8,0.1)",    color: "#facc15", border: "1px solid rgba(234,179,8,0.2)"   },
  error:   { background: "rgba(239,68,68,0.1)",    color: "#f87171", border: "1px solid rgba(239,68,68,0.2)"   },
  info:    { background: "rgba(59,130,246,0.1)",   color: "#60a5fa", border: "1px solid rgba(59,130,246,0.2)"  },
  running: { background: "rgba(99,102,241,0.12)",  color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.25)" },
};

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
        variant === "running" && "animate-pulse",
        className
      )}
      style={VARIANT_STYLES[variant]}
    >
      {children}
    </span>
  );
}

export function statusToBadge(status: string): BadgeVariant {
  switch (status) {
    case "done":    return "success";
    case "failed":  return "error";
    case "paused":  return "warning";
    case "running": return "running";
    case "queued":  return "queued";
    default:        return "default";
  }
}

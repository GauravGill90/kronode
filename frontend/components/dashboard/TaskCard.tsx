import Link from "next/link";
import type { TaskSummary } from "@/lib/types";
import { Badge, statusToBadge } from "@/components/ui/Badge";

export default function TaskCard({ task }: { task: TaskSummary }) {
  return (
    <Link
      href={`/task/${task.id}`}
      className="block rounded-xl px-4 py-3.5 transition-all"
      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(99,102,241,0.12)" }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.borderColor = "rgba(99,102,241,0.35)"; (e.currentTarget as HTMLAnchorElement).style.background = "rgba(255,255,255,0.04)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.borderColor = "rgba(99,102,241,0.12)"; (e.currentTarget as HTMLAnchorElement).style.background = "rgba(255,255,255,0.02)"; }}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm line-clamp-2 flex-1" style={{ color: "#e2e8f0" }}>{task.description}</p>
        <Badge variant={statusToBadge(task.status)}>{task.status}</Badge>
      </div>
      <div className="flex items-center gap-3 mt-1.5 flex-wrap">
        <span className="text-xs" style={{ color: "#334155" }}>
          {new Date(task.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
        </span>
        {task.pr_url && (
          <a
            href={task.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs"
            style={{ color: "#6366f1" }}
            onClick={(e) => e.stopPropagation()}
          >
            PR
          </a>
        )}
        {task.cost_usd != null && (
          <span className="text-xs" style={{ color: "#475569" }}>
            ${task.cost_usd.toFixed(2)}
          </span>
        )}
        {task.num_turns != null && (
          <span className="text-xs" style={{ color: "#475569" }}>
            {task.num_turns} turns
          </span>
        )}
      </div>
    </Link>
  );
}

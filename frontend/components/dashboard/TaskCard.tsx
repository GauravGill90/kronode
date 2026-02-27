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
      <p className="text-xs mt-1.5" style={{ color: "#334155" }}>
        {new Date(task.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
      </p>
    </Link>
  );
}

import Link from "next/link";
import type { TaskSummary } from "@/lib/types";
import { Badge, statusToBadge } from "@/components/ui/Badge";

export default function TaskCard({ task }: { task: TaskSummary }) {
  return (
    <Link href={`/task/${task.id}`} className="block bg-white rounded-xl border border-gray-200 px-4 py-3.5 hover:border-brand-300 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-gray-900 line-clamp-2 flex-1">{task.description}</p>
        <Badge variant={statusToBadge(task.status)}>{task.status}</Badge>
      </div>
      <p className="text-xs text-gray-400 mt-1.5">
        {new Date(task.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
      </p>
    </Link>
  );
}

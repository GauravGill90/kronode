"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useTask } from "@/lib/hooks/useTasks";
import { useSSE } from "@/lib/hooks/useSSE";
import { Badge, statusToBadge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import ProgressStream from "./ProgressStream";
import AppShell from "@/components/layout/AppShell";
import { cancelTask } from "@/lib/api";
import type { TaskStatus } from "@/lib/types";

const queryClient = new QueryClient();

export default function TaskDetailClient({ taskId }: { taskId: string }) {
  return (
    <QueryClientProvider client={queryClient}>
      <TokenSync />
      <TaskDetail taskId={taskId} />
    </QueryClientProvider>
  );
}

function TokenSync() {
  const { getToken } = useAuth();
  useEffect(() => {
    getToken().then((t) => {
      if (t) (window as Window & { __clerkToken?: string }).__clerkToken = t;
    });
  }, [getToken]);
  return null;
}

function TaskDetail({ taskId }: { taskId: string }) {
  const [terminalStatus, setTerminalStatus] = useState<TaskStatus | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const { data: task, isLoading, refetch } = useTask(taskId);

  const isActive = task?.status === "running" || task?.status === "queued" || task?.status === "waiting_clarification" || task?.status === "in_review";

  async function handleCancel() {
    setCancelling(true);
    try {
      await cancelTask(taskId);
      setTerminalStatus("cancelled");
      refetch();
    } catch {
      // ignore — status badge will update via SSE if it goes through
    } finally {
      setCancelling(false);
    }
  }
  const { events, connected } = useSSE({
    taskId: isActive ? taskId : null,
    onTerminal: (s) => setTerminalStatus(s as TaskStatus),
  });

  const displayStatus = terminalStatus || task?.status || "queued";

  if (isLoading) {
    return (
      <AppShell>
        <div className="min-h-[80vh] flex items-center justify-center"><Spinner size="lg" /></div>
      </AppShell>
    );
  }

  if (!task) {
    return (
      <AppShell>
        <div className="min-h-[80vh] flex items-center justify-center text-sm" style={{ color: "#6b6560" }}>
          Task not found.{" "}
          <Link href="/dashboard" className="ml-2 underline" style={{ color: "#d4a853" }}>
            Back to dashboard
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-5">

        {/* Back link */}
        <Link
          href="/dashboard"
          className="text-sm inline-block transition-colors"
          style={{ color: "#475569" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = "#a39e96"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = "#475569"; }}
        >
          ← Dashboard
        </Link>

        {/* Task card */}
        <div
          className="rounded-2xl p-5 space-y-3"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(212,168,83,0.15)" }}
        >
          <div className="flex items-start justify-between gap-3">
            <h1 className="text-base font-semibold flex-1" style={{ color: "#e7e0d8" }}>{task.description}</h1>
            <div className="flex items-center gap-2 flex-shrink-0">
              {isActive && (
                <button
                  onClick={handleCancel}
                  disabled={cancelling}
                  className="text-xs px-2.5 py-1 rounded-lg transition-colors"
                  style={{
                    background: "rgba(239,68,68,0.08)",
                    border: "1px solid rgba(239,68,68,0.25)",
                    color: cancelling ? "#475569" : "#f87171",
                    cursor: cancelling ? "not-allowed" : "pointer",
                  }}
                >
                  {cancelling ? "Cancelling…" : "Cancel"}
                </button>
              )}
              <Badge variant={statusToBadge(displayStatus)}>{displayStatus}</Badge>
            </div>
          </div>
          {task.jira_ticket_id && (
            <span
              className="inline-block text-xs px-2 py-0.5 rounded"
              style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa", border: "1px solid rgba(59,130,246,0.2)" }}
            >
              {task.jira_ticket_id}
            </span>
          )}
          <p className="text-xs" style={{ color: "#334155" }}>
            Started {new Date(task.created_at).toLocaleString()}
          </p>
        </div>

        {/* Live stream */}
        <ProgressStream
          liveEvents={events}
          historicalEvents={task.events}
          connected={connected}
          status={displayStatus}
        />

        {/* Result — PR link + cost */}
        {task.result?.pr_url && (
          <div
            className="rounded-xl p-4 space-y-2"
            style={{ background: "rgba(52,211,153,0.07)", border: "1px solid rgba(52,211,153,0.2)" }}
          >
            <p className="text-sm font-semibold" style={{ color: "#34d399" }}>Pull request opened</p>
            <a
              href={task.result.pr_url as string}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm underline break-all"
              style={{ color: "#d4a853" }}
            >
              {task.result.pr_url as string}
            </a>
            {task.result.slack_summary && (
              <p className="text-sm mt-2" style={{ color: "#6b6560" }}>{task.result.slack_summary as string}</p>
            )}
          </div>
        )}

        {/* Cost tracker */}
        {task.result && (typeof task.result.cost_usd === "number" || task.result.num_turns) && (
          <div
            className="rounded-xl p-4 flex items-center gap-4"
            style={{ background: "rgba(212,168,83,0.05)", border: "1px solid rgba(212,168,83,0.15)" }}
          >
            {typeof task.result.cost_usd === "number" && (
              <div className="text-center">
                <p className="text-lg font-semibold" style={{ color: "#d4a853" }}>
                  ${(task.result.cost_usd as number).toFixed(4)}
                </p>
                <p className="text-xs" style={{ color: "#475569" }}>Cost</p>
              </div>
            )}
            {task.result.num_turns && (
              <div className="text-center">
                <p className="text-lg font-semibold" style={{ color: "#d4a853" }}>
                  {task.result.num_turns as number}
                </p>
                <p className="text-xs" style={{ color: "#475569" }}>Turns</p>
              </div>
            )}
            {task.result.files_changed && (
              <div className="text-center">
                <p className="text-lg font-semibold" style={{ color: "#d4a853" }}>
                  {(task.result.files_changed as string[]).length}
                </p>
                <p className="text-xs" style={{ color: "#475569" }}>Files</p>
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {task.error && (
          <div
            className="rounded-xl p-4"
            style={{ background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.2)" }}
          >
            <p className="text-sm font-semibold" style={{ color: "#f87171" }}>Task paused</p>
            <p className="text-sm mt-1" style={{ color: "#a39e96" }}>{task.error}</p>
          </div>
        )}
      </div>
    </AppShell>
  );
}

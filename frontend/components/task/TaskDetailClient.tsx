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
  const { data: task, isLoading } = useTask(taskId);

  const isActive = task?.status === "running" || task?.status === "queued";
  const { events, connected } = useSSE({
    taskId: isActive ? taskId : null,
    onTerminal: (s) => setTerminalStatus(s as TaskStatus),
  });

  const displayStatus = terminalStatus || task?.status || "queued";

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center"><Spinner size="lg" /></div>;
  }

  if (!task) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500 text-sm">
        Task not found. <Link href="/dashboard" className="ml-2 text-brand-500 underline">Back to dashboard</Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-5">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-gray-400 hover:text-gray-600 text-sm">← Dashboard</Link>
        </div>

        {/* Task card */}
        <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <h1 className="text-base font-semibold text-gray-900 flex-1">{task.description}</h1>
            <Badge variant={statusToBadge(displayStatus)}>{displayStatus}</Badge>
          </div>
          {task.jira_ticket_id && (
            <span className="inline-block text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
              {task.jira_ticket_id}
            </span>
          )}
          <p className="text-xs text-gray-400">
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

        {/* Result — PR link */}
        {task.result?.pr_url && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 space-y-1">
            <p className="text-sm font-semibold text-green-800">Pull request opened</p>
            <a
              href={task.result.pr_url as string}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-brand-600 underline break-all"
            >
              {task.result.pr_url as string}
            </a>
            {task.result.slack_summary && (
              <p className="text-sm text-green-700 mt-2">{task.result.slack_summary as string}</p>
            )}
          </div>
        )}

        {/* Error */}
        {task.error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <p className="text-sm font-semibold text-red-800">Task paused</p>
            <p className="text-sm text-red-700 mt-1">{task.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

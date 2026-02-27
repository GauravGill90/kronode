"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useCreateTask } from "@/lib/hooks/useTasks";

interface Props {
  prefill?: { description: string; jiraId: string } | null;
  onPrefillConsumed?: () => void;
}

export default function TaskInput({ prefill, onPrefillConsumed }: Props) {
  const router = useRouter();
  const [description, setDescription] = useState("");
  const [jiraId, setJiraId] = useState("");
  const { mutateAsync, isPending } = useCreateTask();

  useEffect(() => {
    if (prefill) {
      setDescription(prefill.description);
      setJiraId(prefill.jiraId);
      onPrefillConsumed?.();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  function handleClear() {
    setJiraId("");
    setDescription("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!jiraId) return;
    const result = await mutateAsync({
      description: description.trim(),
      jira_ticket_id: jiraId.trim(),
    });
    router.push(`/task/${result.task_id}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl p-5 space-y-3"
      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(99,102,241,0.15)" }}
    >
      {jiraId ? (
        /* Ticket selected */
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "#94a3b8" }}>Assigned ticket</span>
            <button
              type="button"
              onClick={handleClear}
              className="text-xs transition-colors"
              style={{ color: "#475569" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#94a3b8"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#475569"; }}
            >
              ✕ Clear
            </button>
          </div>
          <div
            className="rounded-xl px-4 py-3 space-y-1"
            style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)" }}
          >
            <span className="text-xs font-mono font-semibold" style={{ color: "#6366f1" }}>{jiraId}</span>
            <p className="text-sm" style={{ color: "#e2e8f0" }}>{description}</p>
          </div>
          <button
            type="submit"
            disabled={isPending}
            className="w-full py-3 rounded-xl font-semibold text-white text-sm transition-all"
            style={{
              background: isPending ? "rgba(99,102,241,0.2)" : "linear-gradient(135deg, #6366f1, #a78bfa)",
              cursor: isPending ? "not-allowed" : "pointer",
              opacity: isPending ? 0.7 : 1,
            }}
          >
            {isPending ? "Sending…" : "Send to agent →"}
          </button>
        </div>
      ) : (
        /* No ticket selected */
        <p className="text-sm text-center py-2" style={{ color: "#475569" }}>
          Select a ticket from the backlog below to assign it to your agent.
        </p>
      )}
    </form>
  );
}

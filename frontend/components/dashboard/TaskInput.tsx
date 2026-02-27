"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useCreateTask } from "@/lib/hooks/useTasks";

export default function TaskInput() {
  const router = useRouter();
  const [description, setDescription] = useState("");
  const [jiraId, setJiraId] = useState("");
  const [showJira, setShowJira] = useState(false);
  const { mutateAsync, isPending } = useCreateTask();

  const valid = description.trim().length >= 5;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    const result = await mutateAsync({
      description: description.trim(),
      jira_ticket_id: jiraId.trim() || undefined,
    });
    router.push(`/task/${result.task_id}`);
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-200 p-5 space-y-3">
      <label className="block text-sm font-medium text-gray-700">What should your agent build?</label>
      <textarea
        className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
        placeholder="Add a forgot password screen that sends a reset email via the existing SendGrid integration."
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      {showJira ? (
        <input
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="Jira ticket ID e.g. KR-42 (optional)"
          value={jiraId}
          onChange={(e) => setJiraId(e.target.value)}
        />
      ) : (
        <button type="button" className="text-xs text-gray-400 hover:text-gray-600" onClick={() => setShowJira(true)}>
          + Link a Jira ticket
        </button>
      )}
      <Button type="submit" size="lg" className="w-full" loading={isPending} disabled={!valid}>
        Send to agent
      </Button>
    </form>
  );
}

"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import AgentHeader from "./AgentHeader";
import TaskInput from "./TaskInput";
import TaskCard from "./TaskCard";
import IntegrationRow from "./IntegrationRow";
import WelcomeBanner from "./WelcomeBanner";
import { Spinner } from "@/components/ui/Spinner";
import { useDashboard } from "@/lib/hooks/useTasks";
import AppShell from "@/components/layout/AppShell";
import type { JiraTicket } from "@/lib/api";
import JiraTickets from "./JiraTickets";
import PRStatsCard from "./PRStats";

const queryClient = new QueryClient();

export default function DashboardClient() {
  return (
    <QueryClientProvider client={queryClient}>
      <TokenSync />
      <DashboardInner />
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

function DashboardInner() {
  const { data, isLoading } = useDashboard();
  const [prefill, setPrefill] = useState<{ description: string; jiraId: string } | null>(null);

  function handleTicketSelect(ticket: JiraTicket) {
    setPrefill({ description: ticket.summary, jiraId: ticket.id });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="min-h-[80vh] flex items-center justify-center">
          <Spinner size="lg" />
        </div>
      </AppShell>
    );
  }

  if (!data?.onboarding_complete) {
    return (
      <AppShell>
        <div className="min-h-[80vh] flex items-center justify-center">
          <div className="text-center space-y-4">
            <p className="text-sm" style={{ color: "#64748b" }}>Complete setup to get started.</p>
            <a
              href="/onboarding"
              className="inline-block text-white px-5 py-2.5 rounded-xl text-sm font-semibold"
              style={{ background: "linear-gradient(135deg, #6366f1, #a78bfa)" }}
            >
              Finish setup
            </a>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <WelcomeBanner userName={data.user_name ?? null} />
        {data.agent && <AgentHeader agent={data.agent} />}
        <IntegrationRow integrations={data.integrations} />
        <PRStatsCard stats={data.pr_stats} />
        <div className="flex gap-2">
          <a
            href="/dashboard/conventions"
            className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-full font-medium"
            style={{ background: "rgba(99,102,241,0.08)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.2)" }}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: "#6366f1" }}></span>
            Conventions
          </a>
        </div>
        <TaskInput prefill={prefill} onPrefillConsumed={() => setPrefill(null)} />
        <JiraTickets onSelect={handleTicketSelect} />
        <div className="space-y-3">
          {data.recent_tasks.length === 0 ? (
            <p className="text-sm text-center py-8" style={{ color: "#475569" }}>
              No tasks yet. Give your agent something to build.
            </p>
          ) : (
            data.recent_tasks.map((task) => <TaskCard key={task.id} task={task} />)
          )}
        </div>
      </div>
    </AppShell>
  );
}

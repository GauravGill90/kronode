"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/Spinner";
import { useDashboard } from "@/lib/hooks/useTasks";
import AppShell from "@/components/layout/AppShell";
import StatCard from "./StatCard";
import MCPTools from "./MCPTools";
import RecentActivity from "./RecentActivity";
import TopConventions from "./TopConventions";
import DocSources from "./DocSources";

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
    const sync = () => {
      getToken().then((t) => {
        if (t) (window as Window & { __clerkToken?: string }).__clerkToken = t;
      });
    };
    sync();
    const interval = setInterval(sync, 50_000); // refresh before 60s expiry
    return () => clearInterval(interval);
  }, [getToken]);
  return null;
}

function DashboardInner() {
  const { data, isLoading } = useDashboard();

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
            <p className="text-sm text-zinc-500">Complete setup to get started.</p>
            <a
              href="/onboarding"
              className="inline-block text-white px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-indigo-600 to-purple-500"
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
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">
              {data.org_name || "Kronode"}
            </h1>
            <p className="text-sm text-zinc-500">
              Organizational memory{data.user_name ? ` — ${data.user_name}` : ""}
            </p>
          </div>
          <a
            href="/settings"
            className="text-xs px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400"
          >
            Settings
          </a>
        </div>

        {/* Stat Cards — 2 rows of 3 */}
        <div className="grid grid-cols-3 gap-3">
          <StatCard
            label="Conventions"
            value={data.convention_count}
            sublabel={`${data.enforced_convention_count} enforced`}
            color="indigo"
          />
          <StatCard
            label="Doc Chunks"
            value={data.doc_chunk_count}
            sublabel={`${data.doc_source_count} source${data.doc_source_count !== 1 ? "s" : ""}`}
            color="blue"
          />
          <StatCard
            label="MCP Calls"
            value={data.mcp_calls_this_month}
            sublabel="this month"
            color="green"
          />
          <StatCard
            label="Reviewer Patterns"
            value={data.reviewer_pattern_count}
            sublabel="extracted"
            color="purple"
          />
          <StatCard
            label="Failures Recorded"
            value={data.failure_count}
            sublabel="learning from mistakes"
            color="amber"
          />
          <StatCard
            label="API Keys"
            value={data.active_api_key_count}
            sublabel="active"
            color="red"
          />
        </div>

        {/* Connected Sources */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-3">Connected Sources</h3>
          <div className="flex flex-wrap gap-2">
            {[
              { key: "git", detail: data.integrations.git },
              { key: "docs", detail: data.integrations.docs },
              { key: "issues", detail: data.integrations.issues },
              { key: "slack", detail: data.integrations.slack },
            ].map(({ key, detail }) => (
              <div
                key={key}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${
                  detail.connected
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border-zinc-700 bg-zinc-800/50 text-zinc-600"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${detail.connected ? "bg-emerald-400" : "bg-zinc-700"}`} />
                {detail.connected ? (
                  <>
                    {detail.provider && <span className="capitalize">{detail.provider}</span>}
                    {detail.name && <span className="text-zinc-500">({detail.name})</span>}
                  </>
                ) : (
                  <span className="capitalize">{key}</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* MCP Tools */}
        <MCPTools tools={data.mcp_tools || []} />

        {/* Recent Activity */}
        <RecentActivity activity={data.recent_activity || []} />

        {/* Top Conventions */}
        <TopConventions
          conventions={data.top_conventions || []}
          total={data.convention_count}
        />

        {/* Doc Sources */}
        <DocSources
          sources={data.doc_sources || []}
          totalChunks={data.doc_chunk_count}
        />
      </div>
    </AppShell>
  );
}

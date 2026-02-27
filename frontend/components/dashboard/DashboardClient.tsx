"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useEffect } from "react";
import AgentHeader from "./AgentHeader";
import TaskInput from "./TaskInput";
import TaskCard from "./TaskCard";
import IntegrationRow from "./IntegrationRow";
import { Spinner } from "@/components/ui/Spinner";
import TopBar from "@/components/TopBar";
import { useDashboard } from "@/lib/hooks/useTasks";

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

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!data?.onboarding_complete) {
    return (
      <div className="min-h-screen flex flex-col">
        <TopBar theme="light" />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-4">
            <p className="text-gray-600">Complete setup to get started.</p>
            <a
              href="/onboarding/1"
              className="inline-block bg-brand-500 text-white px-5 py-2.5 rounded-xl text-sm font-medium"
            >
              Finish setup
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <TopBar theme="light" />
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {data.agent && <AgentHeader agent={data.agent} />}
        <IntegrationRow integrations={data.integrations} />
        <TaskInput />
        <div className="space-y-3">
          {data.recent_tasks.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">
              No tasks yet. Give your agent something to build.
            </p>
          ) : (
            data.recent_tasks.map((task) => <TaskCard key={task.id} task={task} />)
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createTask, getDashboard, getTask } from "../api";
import type { DashboardData, Task, TaskCreated } from "../types";

export function useDashboard() {
  return useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const res = await getDashboard();
      return res.data;
    },
    staleTime: 30_000,
  });
}

export function useTask(taskId: string | null) {
  return useQuery<Task>({
    queryKey: ["task", taskId],
    queryFn: async () => {
      const res = await getTask(taskId!);
      return res.data;
    },
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "queued" ? 3000 : false;
    },
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation<TaskCreated, Error, { description: string; jira_ticket_id?: string }>({
    mutationFn: async (data) => {
      const res = await createTask(data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

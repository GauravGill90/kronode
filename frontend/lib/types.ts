// ── Task types ─────────────────────────────────────────────────────────────────

export type TaskStatus = "queued" | "running" | "in_review" | "done" | "failed" | "paused" | "cancelled" | "waiting_clarification";

export interface TaskEvent {
  id: number;
  agent_name: string;
  event_type: "started" | "progress" | "completed" | "failed" | "terminal";
  message: string;
  payload: Record<string, unknown> | null;
  ts?: string;
  created_at?: string;
}

export interface Task {
  id: string;
  description: string;
  status: TaskStatus;
  jira_ticket_id: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  events: TaskEvent[];
}

export interface TaskCreated {
  task_id: string;
  status: TaskStatus;
}

// ── Dashboard types ─────────────────────────────────────────────────────────────

export interface IntegrationStatus {
  github: boolean;
  jira: boolean;
  slack: boolean;
  docs: boolean;
}

export interface AgentConfig {
  agent_name: string;
  agent_avatar: string;
  capabilities: Record<string, Record<string, boolean>> | null;
  guardrails: {
    restricted_paths: string[];
    max_files_per_task: number;
    risk_level: string;
  } | null;
}

export interface TaskSummary {
  id: string;
  description: string;
  status: TaskStatus;
  pr_url: string | null;
  cost_usd: number | null;
  num_turns: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface PRStats {
  total_prs: number;
  merged: number;
  in_review: number;
  rejected: number;
  failed: number;
  acceptance_rate: number | null;
  avg_cost_usd: number | null;
  avg_turns: number | null;
}

export interface DashboardData {
  user_name: string | null;
  agent: AgentConfig | null;
  integrations: IntegrationStatus;
  recent_tasks: TaskSummary[];
  pr_stats: PRStats;
  onboarding_complete: boolean;
}

// ── Onboarding types ────────────────────────────────────────────────────────────

export interface OnboardingStatus {
  completed: boolean;
  current_step: number;
  agent_name: string | null;
}

export interface OnboardingState {
  currentStep: number;
  agentProfile: { profile_key: string; profile_name: string } | null;
  skills: { id: number; key: string; name: string; category: string }[] | null;
  account: { name: string; company_name: string; role: string } | null;
  repo: { provider: string; repo_url: string; repo_name: string; fork_repo_url?: string } | null;
  jira: { workspace_url: string; project_key: string; email: string; api_token: string } | null;
  slack: { channel_id: string; channel_name: string; bot_token: string } | null;
  docs: { provider: string; scope: string } | null;
  capabilities: Record<string, Record<string, boolean>> | null;
  guardrails: { restricted_paths: string[]; max_files_per_task: number; risk_level: string } | null;
  agent: { agent_name: string; agent_avatar: string } | null;
  projectContext: string;
  codingStandards: string;
}

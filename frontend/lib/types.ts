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

export interface IntegrationDetail {
  connected: boolean;
  provider: string;
  name: string;
}

export interface IntegrationsStatus {
  git: IntegrationDetail;
  docs: IntegrationDetail;
  issues: IntegrationDetail;
  slack: IntegrationDetail;
}

export interface MCPTool {
  name: string;
  description: string;
}

export interface ActivityItem {
  action: string;
  resource: string | null;
  details: Record<string, unknown> | null;
  timestamp: string;
}

export interface ConventionSummary {
  id: number;
  rule: string;
  category: string;
  confidence: number;
  enforced_by: string[] | null;
}

export interface DocSourceSummary {
  source_type: string;
  source_count: number;
  chunk_count: number;
  last_updated: string | null;
}

export interface DashboardData {
  org_name: string;
  user_name: string | null;
  onboarding_complete: boolean;

  // Stats
  convention_count: number;
  enforced_convention_count: number;
  doc_chunk_count: number;
  doc_source_count: number;
  reviewer_pattern_count: number;
  failure_count: number;
  active_api_key_count: number;
  mcp_calls_this_month: number;

  // Integrations
  integrations: IntegrationsStatus;

  // MCP tools
  mcp_tools: MCPTool[];

  // Recent activity
  recent_activity: ActivityItem[];

  // Top conventions
  top_conventions: ConventionSummary[];

  // Doc sources
  doc_sources: DocSourceSummary[];
}

// Legacy types (kept for backward compat with task pages)
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

// ── Onboarding types ────────────────────────────────────────────────────────────

export interface OnboardingStatus {
  completed: boolean;
  current_step: number;
  agent_name: string | null;
}

export interface OnboardingState {
  currentStep: number;
  account: { name: string; company_name: string; role: string } | null;
  repo: { provider: string; repo_url: string; repo_name: string; fork_repo_url?: string } | null;
  jira: { workspace_url: string; project_key: string; email: string; api_token: string } | null;
  slack: { channel_id: string; channel_name: string; bot_token: string } | null;
  docs: { provider: string; scope: string } | null;
  projectContext: string;
  codingStandards: string;
  ingestionDone: boolean;
  apiKeyGenerated: boolean;
  // Legacy fields (kept for backward compat)
  agentProfile: { profile_key: string; profile_name: string } | null;
  skills: { id: number; key: string; name: string; category: string }[] | null;
  capabilities: Record<string, Record<string, boolean>> | null;
  guardrails: { restricted_paths: string[]; max_files_per_task: number; risk_level: string } | null;
  agent: { agent_name: string; agent_avatar: string } | null;
}

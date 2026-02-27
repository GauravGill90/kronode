import axios from "axios";

const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/v1`,
  headers: { "Content-Type": "application/json" },
});

// Inject Clerk token on every request (set window.__clerkToken from a useAuth hook in your layout)
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = (window as Window & { __clerkToken?: string }).__clerkToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export default api;

// ── Onboarding ─────────────────────────────────────────────────────────────────

export const saveAccount = (data: { name: string; company_name: string; role: string }) =>
  api.post("/onboarding/account", data);

export const saveRepo = (data: { provider: string; repo_url: string; repo_name: string }) =>
  api.post("/onboarding/repo", data);

export const saveJira = (data: { workspace_url: string; project_key: string; email: string; api_token: string; status_mappings?: Record<string, string> }) =>
  api.post("/onboarding/jira", data);

export const testJira = (data: { workspace_url: string; project_key: string; email: string; api_token: string }) =>
  api.post<{ ok: boolean; error?: string; user?: string; project?: string }>("/onboarding/test-jira", data);

export const saveSlack = (data: { channel_id: string; channel_name: string; bot_token: string }) =>
  api.post("/onboarding/slack", data);

export const testSlack = (data: { bot_token: string; channel_name: string }) =>
  api.post<{ ok: boolean; error?: string; workspace?: string; bot?: string }>("/onboarding/test-slack", data);

export const testGithubToken = (data: { token: string; repo_url: string }) =>
  api.post<{ ok: boolean; error?: string; repo?: string; login?: string }>("/onboarding/test-github-token", data);

export const saveDocs = (data: { provider: string; scope: string }) =>
  api.post("/onboarding/docs", data);

export const saveCapabilities = (data: Record<string, Record<string, boolean>>) =>
  api.post("/onboarding/capabilities", data);

export const saveGuardrails = (data: { restricted_paths: string[]; max_files_per_task: number; risk_level: string }) =>
  api.post("/onboarding/guardrails", data);

export const saveAgent = (data: { agent_name: string; agent_avatar: string }) =>
  api.post("/onboarding/agent", data);

export const saveAgentProfile = (data: { profile_key: string }) =>
  api.post("/onboarding/agent-profile", data);

export const saveContext = (data: { project_context: string; coding_standards?: string }) =>
  api.post("/onboarding/context", data);

export const saveGithubToken = (data: { token: string }) =>
  api.post("/onboarding/github-token", data);

export const completeOnboarding = () =>
  api.post("/onboarding/complete");

export const getOnboardingStatus = () =>
  api.get("/onboarding/status");

export const getOnboardingConfig = () =>
  api.get("/onboarding/config");

// ── Dashboard ──────────────────────────────────────────────────────────────────

export const getDashboard = () =>
  api.get("/dashboard");

// ── Tasks ──────────────────────────────────────────────────────────────────────

export const createTask = (data: { description: string; jira_ticket_id?: string }) =>
  api.post("/task", data);

export const getTask = (taskId: string) =>
  api.get(`/task/${taskId}`);

export const cancelTask = (taskId: string) =>
  api.post(`/task/${taskId}/cancel`);

// ── Jira ───────────────────────────────────────────────────────────────────────

export interface JiraTicket {
  id: string;
  summary: string;
  status: string;
  status_category: string;
  assignee: string | null;
  priority: string | null;
  url: string;
}

export const getJiraTickets = () =>
  api.get<{ tickets: JiraTicket[]; configured: boolean }>("/jira/tickets");

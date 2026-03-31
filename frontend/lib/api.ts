import axios from "axios";

const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/v1`,
  headers: { "Content-Type": "application/json" },
});

// Inject Clerk token on every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = (window as Window & { __clerkToken?: string }).__clerkToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Retry once on 401 — token may have expired, refresh and retry
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry && typeof window !== "undefined") {
      original._retry = true;
      // Try to get a fresh token from Clerk
      const w = window as Window & { __clerkGetToken?: () => Promise<string | null> };
      if (w.__clerkGetToken) {
        const freshToken = await w.__clerkGetToken();
        if (freshToken) {
          (window as Window & { __clerkToken?: string }).__clerkToken = freshToken;
          original.headers.Authorization = `Bearer ${freshToken}`;
          return api(original);
        }
      }
    }
    return Promise.reject(error);
  }
);

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

export const testBitbucketToken = (data: { token: string; repo_url: string }) =>
  api.post<{ ok: boolean; error?: string; repo?: string; login?: string }>("/onboarding/test-bitbucket-token", data);

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

export const testRepoToken = (data: { token: string; repo_url: string }) =>
  api.post("/onboarding/test-repo-token", data);

export const generateApiKey = (data: { name?: string } = {}) =>
  api.post("/api-keys", data);

export const listApiKeys = () =>
  api.get("/api-keys");

export const revokeApiKey = (keyId: number) =>
  api.delete(`/api-keys/${keyId}`);

export const completeOnboarding = () =>
  api.post("/onboarding/complete");

export const refreshAllIngestion = () =>
  api.post("/onboarding/refresh-all");

export const getIngestionStatus = () =>
  api.get("/onboarding/ingestion-status");

export const getOnboardingStatus = () =>
  api.get("/onboarding/status");

export const getOnboardingConfig = () =>
  api.get("/onboarding/config");

// ── Dashboard ──────────────────────────────────────────────────────────────────

export const getDashboard = () =>
  api.get("/dashboard");

// ── Tasks ──────────────────────────────────────────────────────────────────────

export const createTask = (data: { description: string; jira_ticket_id?: string; action?: string }) =>
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

export const getJiraTickets = (params?: { epic?: string }) =>
  api.get<{ tickets: JiraTicket[]; configured: boolean }>("/jira/tickets", { params });

// ── Skills ────────────────────────────────────────────────────────────────────

export interface SkillInfo {
  id: number;
  key: string;
  name: string;
  description: string | null;
  category: string;
  stack_chips: string[];
  is_preset: boolean;
  assigned?: boolean;
}

export const getSkills = (category?: string) =>
  api.get<{ skills: SkillInfo[] }>("/skills/", { params: category ? { category } : {} });

export const getSkillPresets = () =>
  api.get<{ presets: Record<string, string[]> }>("/skills/presets");

export const getAssignedSkills = () =>
  api.get<{ skills: SkillInfo[] }>("/onboarding/skills");

export const saveSkills = (data: { skill_ids: number[]; preset?: string }) =>
  api.post("/onboarding/skills", data);

// ── Conventions ───────────────────────────────────────────────────────────────

export interface Convention {
  id: number;
  rule: string;
  category: string;
  examples: string[];
  frequency: number;
  confidence: number;
  layer: string;
  source_prs: string[];
  enforced_by?: string[];
  suppressed: boolean;
  created_at: string | null;
}

export const getConventions = (params?: { category?: string; layer?: string; page?: number }) =>
  api.get<{ conventions: Convention[]; total: number; page: number; page_size: number }>("/conventions", { params });

export const updateConvention = (id: number, data: { rule?: string; category?: string }) =>
  api.put(`/conventions/${id}`, data);

export const suppressConvention = (id: number) =>
  api.delete(`/conventions/${id}`);

export const triggerExtraction = () =>
  api.post("/conventions/extract");

export const triggerBaseExtraction = () =>
  api.post("/conventions/extract-base");

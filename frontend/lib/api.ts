const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1";

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

// ── Onboarding config ──────────────────────────────────────────────────────

export interface OnboardingConfig {
  repo_url: string | null;
  repo_provider: string | null;
  jira_project_key: string | null;
  jira_workspace_url: string | null;
  jira_status_mappings: Record<string, string> | null;
  slack_channel_id: string | null;
  slack_channel_name: string | null;
  confluence_base_url: string | null;
  confluence_space_keys: string[] | null;
  confluence_include_labels: string[] | null;
  docs_provider: string | null;
  docs_scope: string | null;
  capabilities: Record<string, boolean> | null;
  guardrails: Record<string, unknown> | null;
  agent_name: string | null;
  agent_avatar: string | null;
  project_context: string | null;
  completed_at: string | null;
}

export async function getOnboardingConfig(): Promise<OnboardingConfig> {
  return apiFetch<OnboardingConfig>("/onboarding/config");
}

// ── Confluence ─────────────────────────────────────────────────────────────

export interface ConfluenceConfigPayload {
  base_url: string;
  space_keys: string[];
  include_labels: string[];
}

export interface ConfluenceSpaceResult {
  key: string;
  name: string;
  page_count: number;
}

export interface ConfluenceTestResult {
  connected: boolean;
  spaces: ConfluenceSpaceResult[];
}

export async function saveConfluenceConfig(
  payload: ConfluenceConfigPayload
): Promise<OnboardingConfig> {
  return apiFetch<OnboardingConfig>("/onboarding/confluence", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function testConfluenceConnection(
  payload: ConfluenceConfigPayload
): Promise<ConfluenceTestResult> {
  return apiFetch<ConfluenceTestResult>("/onboarding/test-confluence", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

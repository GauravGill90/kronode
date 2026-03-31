"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUser, useAuth } from "@clerk/nextjs";
import { useOnboardingStore } from "@/lib/store";
import type { OnboardingState } from "@/lib/types";
import {
  saveRepo,
  saveGithubToken,
  saveContext,
  saveAccount,
  saveJira,
  saveSlack,
  saveDocs,
  testSlack,
  testJira,
  testRepoToken,
  completeOnboarding,
  getOnboardingStatus,
  getOnboardingConfig,
  refreshAllIngestion,
  getIngestionStatus,
} from "@/lib/api";
import SetupCard from "./SetupCard";
import StepMCPSetup from "./StepMCPSetup";
import Modal from "@/components/ui/Modal";
import {
  User, GitBranch, FileText, AlignLeft, FlaskConical,
  Brain, Tag, MessageSquare,
} from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const inputCls: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(212,168,83,0.2)",
  borderRadius: "10px",
  color: "#e7e0d8",
  padding: "10px 14px",
  fontSize: "14px",
  width: "100%",
  outline: "none",
};

function focusBorder(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
  e.currentTarget.style.borderColor = "rgba(212,168,83,0.5)";
}
function blurBorder(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
  e.currentTarget.style.borderColor = "rgba(212,168,83,0.2)";
}

function SaveBtn({
  onClick,
  loading,
  disabled,
  label = "Save",
}: {
  onClick: () => void;
  loading: boolean;
  disabled: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className="w-full py-3 rounded-xl font-semibold text-white text-sm transition-all mt-5"
      style={{
        background: disabled || loading ? "rgba(212,168,83,0.2)" : "#d4a853",
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: loading ? 0.7 : 1,
      }}
    >
      {loading ? "Saving…" : label}
    </button>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="text-sm font-medium block mb-1.5" style={{ color: "#a39e96" }}>
      {children}
    </label>
  );
}

// ─── Account Form ────────────────────────────────────────────────────────────

function AccountForm({ onSave }: { onSave: () => void }) {
  const store = useOnboardingStore();
  const [form, setForm] = useState({
    name: store.account?.name || "",
    company_name: store.account?.company_name || "",
    role: store.account?.role || "",
  });
  const [loading, setLoading] = useState(false);
  const valid = form.name.trim().length > 0 && form.company_name.trim().length > 0;

  async function handleSave() {
    setLoading(true);
    try {
      await saveAccount(form);
      store.setAccount(form);
      onSave();
    } catch {}
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Your name</FieldLabel>
        <input style={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="Jane Smith" />
      </div>
      <div>
        <FieldLabel>Company name</FieldLabel>
        <input style={inputCls} value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="Acme Corp" />
      </div>
      <div>
        <FieldLabel>Role</FieldLabel>
        <input style={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="Engineering Lead" />
      </div>
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Repo Form ───────────────────────────────────────────────────────────────

function RepoForm({ onSave, onFail }: { onSave: () => void; onFail: () => void }) {
  const store = useOnboardingStore();
  const [form, setForm] = useState({
    provider: store.repo?.provider || "github",
    repo_url: store.repo?.repo_url || "",
    token: "",
  });
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState("");
  const valid = form.repo_url.startsWith("http") && form.token.length > 0;

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testRepoToken({ token: form.token, repo_url: form.repo_url });
      setTestResult({ ok: res.data.ok, message: res.data.ok ? `Connected to ${res.data.repo}` : res.data.error });
    } catch (e: any) {
      setTestResult({ ok: false, message: e?.response?.data?.error || "Connection failed" });
    }
    setTesting(false);
  }

  async function handleSave() {
    setLoading(true);
    setError("");
    try {
      // Auto-detect provider from URL
      let provider = form.provider;
      const url = form.repo_url.toLowerCase();
      if (url.includes("gitlab")) provider = "gitlab";
      else if (url.includes("bitbucket")) provider = "bitbucket";
      else provider = "github";

      const repoName = form.repo_url.split("/").slice(-2).join("/").replace(".git", "");
      await saveRepo({ provider, repo_url: form.repo_url, repo_name: repoName });
      await saveGithubToken({ token: form.token });
      store.setRepo({ provider, repo_url: form.repo_url, repo_name: repoName });
      onSave();
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to save");
      onFail();
    }
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Repository URL</FieldLabel>
        <input style={inputCls} value={form.repo_url} onChange={(e) => setForm({ ...form, repo_url: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="https://github.com/org/repo" />
        <p className="text-xs mt-1" style={{ color: "#475569" }}>GitHub, Bitbucket, or GitLab — provider auto-detected from URL</p>
      </div>
      <div>
        <FieldLabel>Access Token</FieldLabel>
        <input style={inputCls} type="password" value={form.token} onChange={(e) => setForm({ ...form, token: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="ghp_... or app password" />
        <p className="text-xs mt-1" style={{ color: "#475569" }}>Needs read access to repo, PRs, and branches</p>
      </div>
      {valid && (
        <button type="button" onClick={handleTest} disabled={testing} className="w-full py-2 rounded-lg text-sm font-medium transition-all" style={{ background: "rgba(212,168,83,0.1)", border: "1px solid rgba(212,168,83,0.3)", color: "#d4a853" }}>
          {testing ? "Testing…" : "Test connection"}
        </button>
      )}
      {testResult && (
        <div className="flex items-start gap-2 text-sm rounded-lg px-3 py-2.5" style={{ background: testResult.ok ? "rgba(52,211,153,0.07)" : "rgba(239,68,68,0.07)", border: `1px solid ${testResult.ok ? "rgba(52,211,153,0.25)" : "rgba(239,68,68,0.25)"}`, color: testResult.ok ? "#34d399" : "#f87171" }}>
          <span>{testResult.ok ? "✓" : "✗"}</span>
          <span>{testResult.message}</span>
        </div>
      )}
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Docs Form ───────────────────────────────────────────────────────────────

function DocsForm({ onSave }: { onSave: () => void }) {
  const store = useOnboardingStore();
  const [form, setForm] = useState({
    provider: store.docs?.provider || "confluence",
    scope: store.docs?.scope || "",
  });
  const [loading, setLoading] = useState(false);
  const valid = form.scope.trim().length > 0;

  async function handleSave() {
    setLoading(true);
    try {
      await saveDocs(form);
      store.setDocs(form);
      onSave();
    } catch {}
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Documentation Provider</FieldLabel>
        <select style={inputCls} value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} onFocus={focusBorder as any} onBlur={blurBorder as any}>
          <option value="confluence">Confluence</option>
          <option value="notion">Notion</option>
          <option value="gdrive">Google Drive</option>
        </select>
      </div>
      <div>
        <FieldLabel>{form.provider === "confluence" ? "Space key or URL" : form.provider === "notion" ? "Workspace token" : "Folder ID or URL"}</FieldLabel>
        <input style={inputCls} value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder={form.provider === "confluence" ? "SIDC or https://yoursite.atlassian.net/wiki/spaces/SIDC" : form.provider === "notion" ? "ntn_..." : "folder:1x2y3z"} />
        <p className="text-xs mt-1" style={{ color: "#475569" }}>
          {form.provider === "confluence" ? "All pages in this space will be ingested" : form.provider === "notion" ? "All pages accessible to the integration" : "All Google Docs in this folder"}
        </p>
      </div>
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Context Form ────────────────────────────────────────────────────────────

function ContextForm({ onSave }: { onSave: () => void }) {
  const store = useOnboardingStore();
  const [context, setContext] = useState(store.projectContext || "");
  const [standards, setStandards] = useState(store.codingStandards || "");
  const [loading, setLoading] = useState(false);
  const valid = context.length >= 20;

  async function handleSave() {
    setLoading(true);
    try {
      await saveContext({ project_context: context, coding_standards: standards || undefined });
      store.setProjectContext(context);
      store.setCodingStandards(standards);
      onSave();
    } catch {}
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Project context</FieldLabel>
        <textarea style={{ ...inputCls, minHeight: 100 }} value={context} onChange={(e) => setContext(e.target.value)} onFocus={focusBorder} onBlur={blurBorder} placeholder="Describe your project — what it does, the tech stack, any important patterns. This helps Kronode rank conventions and docs more accurately." />
        <p className="text-xs mt-1" style={{ color: "#475569" }}>{context.length}/20 characters minimum</p>
      </div>
      <div>
        <FieldLabel>Coding standards (optional)</FieldLabel>
        <textarea style={{ ...inputCls, minHeight: 80 }} value={standards} onChange={(e) => setStandards(e.target.value)} onFocus={focusBorder} onBlur={blurBorder} placeholder="Any team-specific rules not captured in PR history — e.g., 'Always use Tamagui styled() instead of StyleSheet'" />
      </div>
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Jira Form ───────────────────────────────────────────────────────────────

function JiraForm({ onSave, onFail }: { onSave: () => void; onFail: () => void }) {
  const store = useOnboardingStore();
  const [form, setForm] = useState({
    workspace_url: store.jira?.workspace_url || "",
    project_key: store.jira?.project_key || "",
    email: store.jira?.email || "",
    api_token: store.jira?.api_token || "",
  });
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const valid = form.workspace_url && form.project_key && form.email && form.api_token && form.api_token !== "••••••••";

  async function handleTest() {
    setTesting(true);
    try {
      const res = await testJira(form);
      setTestResult({ ok: res.data.ok, message: res.data.ok ? `Connected to ${form.project_key}` : (res.data.error || "Connection failed") });
    } catch (e: any) {
      setTestResult({ ok: false, message: "Connection failed" });
    }
    setTesting(false);
  }

  async function handleSave() {
    setLoading(true);
    try {
      await saveJira(form);
      store.setJira(form);
      onSave();
    } catch { onFail(); }
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Workspace URL</FieldLabel>
        <input style={inputCls} value={form.workspace_url} onChange={(e) => setForm({ ...form, workspace_url: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="https://yourteam.atlassian.net" />
      </div>
      <div>
        <FieldLabel>Project key</FieldLabel>
        <input style={inputCls} value={form.project_key} onChange={(e) => setForm({ ...form, project_key: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="PROJ" />
      </div>
      <div>
        <FieldLabel>Email</FieldLabel>
        <input style={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="you@company.com" />
      </div>
      <div>
        <FieldLabel>API token</FieldLabel>
        <input style={inputCls} type="password" value={form.api_token} onChange={(e) => setForm({ ...form, api_token: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="Atlassian API token" />
      </div>
      {valid && (
        <button type="button" onClick={handleTest} disabled={testing} className="w-full py-2 rounded-lg text-sm font-medium" style={{ background: "rgba(212,168,83,0.1)", border: "1px solid rgba(212,168,83,0.3)", color: "#d4a853" }}>
          {testing ? "Testing…" : "Test connection"}
        </button>
      )}
      {testResult && (
        <div className="flex items-start gap-2 text-sm rounded-lg px-3 py-2.5" style={{ background: testResult.ok ? "rgba(52,211,153,0.07)" : "rgba(239,68,68,0.07)", color: testResult.ok ? "#34d399" : "#f87171" }}>
          <span>{testResult.ok ? "✓" : "✗"}</span>
          <span>{testResult.message}</span>
        </div>
      )}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Slack Form ──────────────────────────────────────────────────────────────

function SlackForm({ onSave, onFail }: { onSave: () => void; onFail: () => void }) {
  const store = useOnboardingStore();
  const [form, setForm] = useState({
    channel_name: store.slack?.channel_name || "",
    bot_token: store.slack?.bot_token || "",
  });
  const [loading, setLoading] = useState(false);
  const valid = form.channel_name && form.bot_token && form.bot_token !== "••••••••";

  async function handleSave() {
    setLoading(true);
    try {
      await saveSlack({ channel_id: form.channel_name, channel_name: form.channel_name, bot_token: form.bot_token });
      store.setSlack({ channel_id: form.channel_name, channel_name: form.channel_name, bot_token: form.bot_token });
      onSave();
    } catch { onFail(); }
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Channel name</FieldLabel>
        <input style={inputCls} value={form.channel_name} onChange={(e) => setForm({ ...form, channel_name: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="#engineering" />
      </div>
      <div>
        <FieldLabel>Bot token</FieldLabel>
        <input style={inputCls} type="password" value={form.bot_token} onChange={(e) => setForm({ ...form, bot_token: e.target.value })} onFocus={focusBorder} onBlur={blurBorder} placeholder="xoxb-..." />
      </div>
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Ingestion Form ──────────────────────────────────────────────────────────

function IngestionForm({ onSave }: { onSave: () => void }) {
  const store = useOnboardingStore();
  const [status, setStatus] = useState<"idle" | "running" | "done">("idle");
  const [stats, setStats] = useState<{ doc_chunks: number; conventions: number; reviewer_patterns: number } | null>(null);

  async function handleRun() {
    setStatus("running");
    try {
      await refreshAllIngestion();
      // Poll for completion
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        try {
          const res = await getIngestionStatus();
          setStats(res.data);
          if (res.data.conventions > 0 || res.data.doc_chunks > 0) {
            setStatus("done");
            store.setIngestionDone(true);
            break;
          }
        } catch {}
      }
      if (status !== "done") {
        setStatus("done");
        store.setIngestionDone(true);
      }
    } catch {
      setStatus("done");
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: "#a39e96" }}>
        Kronode will analyze your PR history to extract team conventions, ingest documentation, and learn reviewer patterns. This takes 1-3 minutes.
      </p>

      {status === "idle" && (
        <button type="button" onClick={handleRun} className="w-full py-3 rounded-xl font-semibold text-white text-sm" style={{ background: "#d4a853" }}>
          Start Ingestion
        </button>
      )}

      {status === "running" && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm" style={{ color: "#d4a853" }}>Analyzing PRs, ingesting docs, extracting conventions...</p>
          </div>
          {stats && (
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg p-2" style={{ background: "rgba(99,102,241,0.08)" }}>
                <p className="text-lg font-bold text-indigo-300">{stats.conventions}</p>
                <p className="text-[10px] text-zinc-500">conventions</p>
              </div>
              <div className="rounded-lg p-2" style={{ background: "rgba(99,102,241,0.08)" }}>
                <p className="text-lg font-bold text-blue-300">{stats.doc_chunks}</p>
                <p className="text-[10px] text-zinc-500">doc chunks</p>
              </div>
              <div className="rounded-lg p-2" style={{ background: "rgba(99,102,241,0.08)" }}>
                <p className="text-lg font-bold text-purple-300">{stats.reviewer_patterns}</p>
                <p className="text-[10px] text-zinc-500">patterns</p>
              </div>
            </div>
          )}
        </div>
      )}

      {status === "done" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm rounded-lg px-3 py-2.5" style={{ background: "rgba(52,211,153,0.07)", color: "#34d399" }}>
            <span>✓</span>
            <span>Ingestion complete</span>
          </div>
          {stats && (
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg p-2" style={{ background: "rgba(52,211,153,0.08)" }}>
                <p className="text-lg font-bold text-emerald-300">{stats.conventions}</p>
                <p className="text-[10px] text-zinc-500">conventions</p>
              </div>
              <div className="rounded-lg p-2" style={{ background: "rgba(52,211,153,0.08)" }}>
                <p className="text-lg font-bold text-emerald-300">{stats.doc_chunks}</p>
                <p className="text-[10px] text-zinc-500">doc chunks</p>
              </div>
              <div className="rounded-lg p-2" style={{ background: "rgba(52,211,153,0.08)" }}>
                <p className="text-lg font-bold text-emerald-300">{stats.reviewer_patterns}</p>
                <p className="text-[10px] text-zinc-500">patterns</p>
              </div>
            </div>
          )}
          <button type="button" onClick={onSave} className="w-full py-3 rounded-xl font-semibold text-white text-sm" style={{ background: "#d4a853" }}>
            Continue
          </button>
        </div>
      )}
    </div>
  );
}

// ─── MCP Setup Form (wraps StepMCPSetup) ─────────────────────────────────────

function MCPSetupForm({ onSave }: { onSave: () => void }) {
  const store = useOnboardingStore();

  function handleDone() {
    store.setApiKeyGenerated(true);
    onSave();
  }

  return <StepMCPSetup onDone={handleDone} />;
}

// ─── Stage computation ───────────────────────────────────────────────────────

function computeStage(store: OnboardingState): number {
  if (!store.account) return 1;                                              // Account
  if (!store.repo) return 2;                                                 // Repo
  if (!store.projectContext || store.projectContext.length < 20) return 3;   // Context
  if (!store.ingestionDone) return 4;                                        // Ingestion
  if (!store.apiKeyGenerated) return 5;                                      // MCP Setup
  return 6;                                                                   // Done
}

const STAGE_LABELS = ["Account", "Repository", "Context", "Ingestion", "MCP Setup", "Ready"];

// ─── Main component ──────────────────────────────────────────────────────────

const MODAL_TITLES: Record<string, string> = {
  account: "Your account",
  repo: "Connect repository",
  docs: "Connect documentation",
  context: "Project context",
  ingestion: "Run ingestion",
  mcp_setup: "Connect your AI tool",
  jira: "Connect Jira",
  slack: "Connect Slack",
};

export default function OnboardingDashboard({ isSettings = false }: { isSettings?: boolean }) {
  const store = useOnboardingStore();
  const router = useRouter();
  const { user } = useUser();
  const { getToken } = useAuth();
  const firstName = user?.firstName || user?.fullName?.split(" ")[0] || "";
  const [openCard, setOpenCard] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);
  const [failedCards, setFailedCards] = useState<Set<string>>(new Set());

  function markFailed(cardId: string) {
    setFailedCards((prev) => new Set([...prev, cardId]));
  }
  function markSaved(cardId: string) {
    setFailedCards((prev) => { const s = new Set(prev); s.delete(cardId); return s; });
    setOpenCard(null);
  }

  useEffect(() => {
    async function init() {
      try {
        const t = await getToken();
        if (t) (window as Window & { __clerkToken?: string }).__clerkToken = t;

        if (isSettings) {
          const res = await getOnboardingConfig();
          const c = res.data;
          if (c.user_name) store.setAccount({ name: c.user_name, company_name: c.company_name || "", role: c.user_role || "" });
          if (c.repo_url) store.setRepo({ provider: c.repo_provider || "github", repo_url: c.repo_url, repo_name: c.repo_name || "" });
          if (c.project_context) store.setProjectContext(c.project_context);
          if (c.coding_standards) store.setCodingStandards(c.coding_standards);
          if (c.docs_provider) store.setDocs({ provider: c.docs_provider, scope: c.docs_scope || "" });
          if (c.jira_workspace_url && c.has_jira_token) {
            store.setJira({ workspace_url: c.jira_workspace_url, project_key: c.jira_project_key || "", email: c.jira_email || "", api_token: "••••••••" });
          }
          if (c.slack_channel_id && c.has_slack_token) {
            store.setSlack({ channel_id: c.slack_channel_id, channel_name: c.slack_channel_name || "", bot_token: "••••••••" });
          }
          return;
        }

        const res = await getOnboardingStatus();
        if (res.data?.completed) router.replace("/dashboard");
      } catch {}
    }
    init();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken, router, isSettings]);

  const currentStage = computeStage(store);
  const requiredDone = currentStage >= 5;

  async function handleLaunch() {
    setLaunching(true);
    try { await completeOnboarding(); } catch {}
    store.reset();
    router.push("/dashboard");
  }

  const iconCls = "w-5 h-5";
  const cards = [
    {
      id: "account",
      icon: <User className={iconCls} />,
      title: "Your account",
      description: store.account ? `${store.account.name} · ${store.account.company_name}` : "Name and company",
      required: true,
      completed: !!store.account,
    },
    {
      id: "repo",
      icon: <GitBranch className={iconCls} />,
      title: "Connect repository",
      description: store.repo ? `${store.repo.provider} · ${store.repo.repo_name}` : "GitHub, Bitbucket, or GitLab",
      required: true,
      completed: !!store.repo,
    },
    {
      id: "docs",
      icon: <FileText className={iconCls} />,
      title: "Connect documentation",
      description: store.docs ? `${store.docs.provider} · ${store.docs.scope}` : "Confluence, Notion, or Google Drive",
      required: false,
      completed: !!store.docs,
    },
    {
      id: "context",
      icon: <AlignLeft className={iconCls} />,
      title: "Project context",
      description: store.projectContext.length >= 20 ? store.projectContext.slice(0, 60) + "…" : "Describe your project",
      required: true,
      completed: store.projectContext.length >= 20,
    },
    {
      id: "ingestion",
      icon: <FlaskConical className={iconCls} />,
      title: "Run ingestion",
      description: store.ingestionDone ? "Conventions + docs extracted" : "Analyze PR history and ingest docs",
      required: true,
      completed: store.ingestionDone,
    },
    {
      id: "mcp_setup",
      icon: <Brain className={iconCls} />,
      title: "Connect AI tool",
      description: store.apiKeyGenerated ? "API key generated" : "Set up MCP in Claude Code, Cursor, etc.",
      required: true,
      completed: store.apiKeyGenerated,
    },
    {
      id: "jira",
      icon: <Tag className={iconCls} />,
      title: "Connect Jira",
      description: store.jira ? `${store.jira.project_key}` : "Issue tracking (optional)",
      required: false,
      completed: !!store.jira,
    },
    {
      id: "slack",
      icon: <MessageSquare className={iconCls} />,
      title: "Connect Slack",
      description: store.slack ? store.slack.channel_name : "Notifications (optional)",
      required: false,
      completed: !!store.slack,
    },
  ];

  let pendingIdx = 0;
  const cardsWithIdx = cards.map((card) => ({
    ...card,
    index: card.completed ? 0 : ++pendingIdx,
  }));

  return (
    <>
      <div className="space-y-8">
        {/* Header */}
        {isSettings ? (
          <div>
            <a href="/dashboard" className="text-sm font-medium inline-flex items-center gap-1.5 mb-3" style={{ color: "#d4a853" }}>
              ← Back to dashboard
            </a>
            <h1 className="text-2xl font-bold" style={{ color: "#e7e0d8" }}>Settings</h1>
            <p className="text-sm mt-1" style={{ color: "#6b6560" }}>Update your integrations and configuration.</p>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium mb-1" style={{ color: "#d4a853" }}>
              {firstName ? `Welcome, ${firstName}!` : "Welcome!"}
            </p>
            <h1 className="text-2xl font-bold" style={{ color: "#e7e0d8" }}>
              Set up Kronode
            </h1>
            <p className="text-sm mt-1" style={{ color: "#6b6560" }}>
              Connect your repo and docs. Kronode learns your team's conventions, then serves them to any AI coding tool.
            </p>
          </div>
        )}

        {/* Progress — onboarding only */}
        {!isSettings && (
          <div className="flex items-center gap-1">
            {STAGE_LABELS.map((label, i) => (
              <div key={i} className="flex items-center gap-1">
                <div
                  className={`h-1.5 rounded-full transition-all ${i < currentStage ? "bg-indigo-500" : "bg-zinc-800"}`}
                  style={{ width: i < currentStage ? 40 : 20 }}
                />
              </div>
            ))}
            <span className="text-xs ml-2" style={{ color: "#475569" }}>{STAGE_LABELS[Math.min(currentStage - 1, 5)]}</span>
          </div>
        )}

        {/* Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {cardsWithIdx.map((card) => (
            <SetupCard
              key={card.id}
              icon={card.icon}
              title={card.title}
              description={card.description}
              status={card.completed ? "completed" : failedCards.has(card.id) ? "failed" : card.required ? "pending" : "optional"}
              index={card.index}
              onClick={() => setOpenCard(card.id)}
            />
          ))}
        </div>

        {/* Launch CTA — onboarding only */}
        {!isSettings && requiredDone && (
          <button
            onClick={handleLaunch}
            disabled={launching}
            className="w-full py-4 rounded-xl font-semibold text-white text-sm transition-all"
            style={{
              background: "#d4a853",
              boxShadow: "0 0 30px rgba(212,168,83,0.25)",
              opacity: launching ? 0.7 : 1,
            }}
          >
            {launching ? "Launching…" : "Go to Dashboard →"}
          </button>
        )}

        {!isSettings && !requiredDone && (
          <p className="text-xs text-center" style={{ color: "#6b6560" }}>
            {cards.filter((c) => c.required && !c.completed).length} required {cards.filter((c) => c.required && !c.completed).length === 1 ? "step" : "steps"} remaining
          </p>
        )}
      </div>

      {/* Modal */}
      {openCard && (
        <Modal open onClose={() => setOpenCard(null)} title={MODAL_TITLES[openCard] || ""}>
          {openCard === "account" && <AccountForm onSave={() => setOpenCard(null)} />}
          {openCard === "repo" && <RepoForm onSave={() => markSaved("repo")} onFail={() => markFailed("repo")} />}
          {openCard === "docs" && <DocsForm onSave={() => setOpenCard(null)} />}
          {openCard === "context" && <ContextForm onSave={() => setOpenCard(null)} />}
          {openCard === "ingestion" && <IngestionForm onSave={() => setOpenCard(null)} />}
          {openCard === "mcp_setup" && <MCPSetupForm onSave={() => setOpenCard(null)} />}
          {openCard === "jira" && <JiraForm onSave={() => markSaved("jira")} onFail={() => markFailed("jira")} />}
          {openCard === "slack" && <SlackForm onSave={() => markSaved("slack")} onFail={() => markFailed("slack")} />}
        </Modal>
      )}
    </>
  );
}

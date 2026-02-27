"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { useOnboardingStore } from "@/lib/store";
import type { OnboardingState } from "@/lib/types";
import {
  saveAgent,
  saveRepo,
  saveCapabilities,
  saveGuardrails,
  saveContext,
  saveAccount,
  saveJira,
  saveSlack,
  completeOnboarding,
} from "@/lib/api";
import StageBar from "./StageBar";
import SetupCard from "./SetupCard";
import AgentUnderstanding from "./AgentUnderstanding";
import Modal from "@/components/ui/Modal";
import LogoutButton from "@/components/LogoutButton";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const inputCls: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(99,102,241,0.2)",
  borderRadius: "10px",
  color: "#e2e8f0",
  padding: "10px 14px",
  fontSize: "14px",
  width: "100%",
  outline: "none",
};

function focusBorder(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
  e.currentTarget.style.borderColor = "rgba(99,102,241,0.6)";
}
function blurBorder(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
  e.currentTarget.style.borderColor = "rgba(99,102,241,0.2)";
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
        background:
          disabled || loading
            ? "rgba(99,102,241,0.2)"
            : "linear-gradient(135deg, #6366f1, #a78bfa)",
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
    <label className="text-sm font-medium block mb-1.5" style={{ color: "#94a3b8" }}>
      {children}
    </label>
  );
}

// ─── Modal forms ──────────────────────────────────────────────────────────────

const SUGGESTIONS = ["Forge", "Relay", "Scout", "Hatch", "Stride"];
const AVATARS = ["🤖", "🛠️", "⚡", "🚀", "🔮", "🧠"];

function AgentForm({ onSave }: { onSave: () => void }) {
  const { agent, setAgent } = useOnboardingStore();
  const [name, setName] = useState(agent?.agent_name || "");
  const [avatar, setAvatar] = useState(agent?.agent_avatar || AVATARS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const valid = name.trim().length >= 2;

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      await saveAgent({ agent_name: name, agent_avatar: avatar });
      setAgent({ agent_name: name, agent_avatar: avatar });
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <FieldLabel>Avatar</FieldLabel>
        <div className="flex gap-2">
          {AVATARS.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setAvatar(a)}
              className="w-10 h-10 text-xl rounded-xl transition-all"
              style={{
                border: `2px solid ${avatar === a ? "#6366f1" : "rgba(99,102,241,0.2)"}`,
                background: avatar === a ? "rgba(99,102,241,0.15)" : "transparent",
              }}
            >
              {a}
            </button>
          ))}
        </div>
      </div>
      <div>
        <FieldLabel>Agent name</FieldLabel>
        <input
          style={inputCls}
          placeholder="e.g. Forge"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
        <div className="flex gap-2 flex-wrap mt-2">
          <span className="text-xs" style={{ color: "#475569" }}>Suggestions:</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setName(s)}
              className="text-xs underline"
              style={{ color: "#6366f1" }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
      {name && (
        <div
          className="flex items-center gap-3 rounded-xl p-3"
          style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)" }}
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
            style={{ background: "rgba(99,102,241,0.2)" }}
          >
            {avatar}
          </div>
          <div>
            <div className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>{name}</div>
            <div className="text-xs" style={{ color: "#64748b" }}>Your autonomous developer</div>
          </div>
          <div className="ml-auto w-2 h-2 rounded-full" style={{ background: "#34d399" }} />
        </div>
      )}
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

function RepoForm({ onSave }: { onSave: () => void }) {
  const { repo, setRepo } = useOnboardingStore();
  const [provider, setProvider] = useState<"github" | "gitlab">(
    (repo?.provider as "github" | "gitlab") || "github"
  );
  const [repoUrl, setRepoUrl] = useState(repo?.repo_url || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const repoName = repoUrl.split("/").slice(-1)[0]?.replace(".git", "") || "";
  const valid = repoUrl.trim().startsWith("http");

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      await saveRepo({ provider, repo_url: repoUrl, repo_name: repoName });
      setRepo({ provider, repo_url: repoUrl, repo_name: repoName });
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Provider</FieldLabel>
        <div className="flex gap-3">
          {(["github", "gitlab"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setProvider(p)}
              className="flex-1 py-2 rounded-xl text-sm font-medium transition-all capitalize"
              style={{
                border: `1px solid ${provider === p ? "#6366f1" : "rgba(99,102,241,0.2)"}`,
                background: provider === p ? "rgba(99,102,241,0.15)" : "transparent",
                color: provider === p ? "#a78bfa" : "#64748b",
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <div>
        <FieldLabel>Repository URL</FieldLabel>
        <input
          style={inputCls}
          placeholder="https://github.com/org/repo"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

function JiraForm({ onSave }: { onSave: () => void }) {
  const { jira, setJira } = useOnboardingStore();
  const [workspaceUrl, setWorkspaceUrl] = useState(jira?.workspace_url || "");
  const [projectKey, setProjectKey] = useState(jira?.project_key || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const valid = workspaceUrl.trim().startsWith("http") && projectKey.trim().length >= 1;

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      await saveJira({ workspace_url: workspaceUrl, project_key: projectKey });
      setJira({ workspace_url: workspaceUrl, project_key: projectKey });
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Jira workspace URL</FieldLabel>
        <input
          style={inputCls}
          placeholder="https://yourcompany.atlassian.net"
          value={workspaceUrl}
          onChange={(e) => setWorkspaceUrl(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Project key</FieldLabel>
        <input
          style={inputCls}
          placeholder="ENG"
          value={projectKey}
          onChange={(e) => setProjectKey(e.target.value.toUpperCase())}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

function SlackForm({ onSave }: { onSave: () => void }) {
  const { slack, setSlack } = useOnboardingStore();
  const [channelId, setChannelId] = useState(slack?.channel_id || "");
  const [channelName, setChannelName] = useState(slack?.channel_name || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const valid = channelId.trim().length >= 1 && channelName.trim().length >= 1;

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      await saveSlack({ channel_id: channelId, channel_name: channelName });
      setSlack({ channel_id: channelId, channel_name: channelName });
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Channel ID</FieldLabel>
        <input
          style={inputCls}
          placeholder="C0123456789"
          value={channelId}
          onChange={(e) => setChannelId(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Channel name</FieldLabel>
        <input
          style={inputCls}
          placeholder="#engineering"
          value={channelName}
          onChange={(e) => setChannelName(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

function CapabilitiesForm({ onSave }: { onSave: () => void }) {
  const { capabilities, setCapabilities } = useOnboardingStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const defaultCaps = capabilities || {
    code: { write: true, review: true, refactor: true },
    tickets: { read: true, comment: true, transition: false },
    prs: { open: true, merge: false },
  };

  const [caps, setCaps] = useState(defaultCaps);

  function toggle(group: string, key: string) {
    setCaps((prev) => ({
      ...prev,
      [group]: { ...prev[group], [key]: !prev[group][key] },
    }));
  }

  async function handleSave() {
    setLoading(true);
    setError("");
    try {
      await saveCapabilities(caps);
      setCapabilities(caps);
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {Object.entries(caps).map(([group, keys]) => (
        <div key={group}>
          <FieldLabel>{group.charAt(0).toUpperCase() + group.slice(1)}</FieldLabel>
          <div className="flex flex-wrap gap-2">
            {Object.entries(keys).map(([key, val]) => (
              <button
                key={key}
                type="button"
                onClick={() => toggle(group, key)}
                className="text-xs px-3 py-1.5 rounded-lg transition-all"
                style={{
                  border: `1px solid ${val ? "#6366f1" : "rgba(99,102,241,0.2)"}`,
                  background: val ? "rgba(99,102,241,0.15)" : "transparent",
                  color: val ? "#a78bfa" : "#64748b",
                }}
              >
                {key}
              </button>
            ))}
          </div>
        </div>
      ))}
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={false} />
    </div>
  );
}

function GuardrailsForm({ onSave }: { onSave: () => void }) {
  const { guardrails, setGuardrails } = useOnboardingStore();
  const [paths, setPaths] = useState(guardrails?.restricted_paths?.join(", ") || "");
  const [maxFiles, setMaxFiles] = useState(String(guardrails?.max_files_per_task || 20));
  const [riskLevel, setRiskLevel] = useState(guardrails?.risk_level || "medium");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSave() {
    setLoading(true);
    setError("");
    const data = {
      restricted_paths: paths.split(",").map((p) => p.trim()).filter(Boolean),
      max_files_per_task: parseInt(maxFiles) || 20,
      risk_level: riskLevel,
    };
    try {
      await saveGuardrails(data);
      setGuardrails(data);
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Restricted paths (comma-separated)</FieldLabel>
        <input
          style={inputCls}
          placeholder="/secrets, /infra"
          value={paths}
          onChange={(e) => setPaths(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Max files per task</FieldLabel>
        <input
          style={inputCls}
          type="number"
          min={1}
          max={100}
          value={maxFiles}
          onChange={(e) => setMaxFiles(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Risk level</FieldLabel>
        <div className="flex gap-3">
          {["low", "medium", "high"].map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRiskLevel(r)}
              className="flex-1 py-2 rounded-xl text-sm font-medium capitalize transition-all"
              style={{
                border: `1px solid ${riskLevel === r ? "#6366f1" : "rgba(99,102,241,0.2)"}`,
                background: riskLevel === r ? "rgba(99,102,241,0.15)" : "transparent",
                color: riskLevel === r ? "#a78bfa" : "#64748b",
              }}
            >
              {r}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={false} />
    </div>
  );
}

function ContextForm({ onSave }: { onSave: () => void }) {
  const { projectContext, setProjectContext } = useOnboardingStore();
  const [context, setContext] = useState(projectContext || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSave() {
    setLoading(true);
    setError("");
    try {
      await saveContext({ project_context: context });
      setProjectContext(context);
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Project context</FieldLabel>
        <textarea
          style={{ ...inputCls, minHeight: "120px", resize: "vertical" }}
          placeholder="Describe your project, tech stack, conventions, and anything your agent should know…"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          onFocus={focusBorder as unknown as React.FocusEventHandler<HTMLTextAreaElement>}
          onBlur={blurBorder as unknown as React.FocusEventHandler<HTMLTextAreaElement>}
        />
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={false} label="Save context" />
    </div>
  );
}

function AccountForm({ onSave }: { onSave: () => void }) {
  const { user } = useUser();
  const { account, setAccount } = useOnboardingStore();
  const [name, setName] = useState(account?.name || user?.fullName || "");
  const [company, setCompany] = useState(account?.company_name || "");
  const [role, setRole] = useState(account?.role || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const valid = name.trim().length >= 1 && company.trim().length >= 1;

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      await saveAccount({ name, company_name: company, role });
      setAccount({ name, company_name: company, role });
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <FieldLabel>Your name</FieldLabel>
        <input
          style={inputCls}
          placeholder="Jane Smith"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Company</FieldLabel>
        <input
          style={inputCls}
          placeholder="Acme Corp"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Role</FieldLabel>
        <input
          style={inputCls}
          placeholder="CTO, Engineering Manager, etc."
          value={role}
          onChange={(e) => setRole(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Stage config ─────────────────────────────────────────────────────────────

interface Stage {
  id: string;
  title: string;
  subtitle: string;
  icon: string;
  cta: string;
  form: (onSave: () => void) => React.ReactNode;
}

const STAGES: Stage[] = [
  {
    id: "account",
    title: "Your account",
    subtitle: "Tell us a bit about you and your company.",
    icon: "👤",
    cta: "Set up account",
    form: (onSave) => <AccountForm onSave={onSave} />,
  },
  {
    id: "repo",
    title: "Connect your repo",
    subtitle: "Point Kronode at the codebase it will work in.",
    icon: "🗂️",
    cta: "Connect repo",
    form: (onSave) => <RepoForm onSave={onSave} />,
  },
  {
    id: "jira",
    title: "Connect Jira",
    subtitle: "Let Kronode read and act on your tickets.",
    icon: "📋",
    cta: "Connect Jira",
    form: (onSave) => <JiraForm onSave={onSave} />,
  },
  {
    id: "slack",
    title: "Connect Slack",
    subtitle: "Kronode will post standups and updates here.",
    icon: "💬",
    cta: "Connect Slack",
    form: (onSave) => <SlackForm onSave={onSave} />,
  },
  {
    id: "capabilities",
    title: "Set capabilities",
    subtitle: "Control what Kronode is allowed to do.",
    icon: "⚙️",
    cta: "Set capabilities",
    form: (onSave) => <CapabilitiesForm onSave={onSave} />,
  },
  {
    id: "guardrails",
    title: "Set guardrails",
    subtitle: "Define the limits of your agent's autonomy.",
    icon: "🛡️",
    cta: "Set guardrails",
    form: (onSave) => <GuardrailsForm onSave={onSave} />,
  },
  {
    id: "context",
    title: "Project context",
    subtitle: "Give Kronode extra context about your stack.",
    icon: "📝",
    cta: "Add context",
    form: (onSave) => <ContextForm onSave={onSave} />,
  },
  {
    id: "agent",
    title: "Name your agent",
    subtitle: "Give your AI teammate a name and a face.",
    icon: "🤖",
    cta: "Name agent",
    form: (onSave) => <AgentForm onSave={onSave} />,
  },
];

// ─── Main component ────────────────────────────────────────────────────────────

export default function OnboardingDashboard() {
  const router = useRouter();
  const { currentStep, setStep } = useOnboardingStore();
  const [openModal, setOpenModal] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());

  const totalStages = STAGES.length;
  const completedCount = completedStages.size;
  const allDone = completedCount === totalStages;

  function handleSave(stageId: string) {
    setCompletedStages((prev) => new Set([...prev, stageId]));
    setOpenModal(null);
  }

  async function handleComplete() {
    setCompleting(true);
    try {
      await completeOnboarding();
      router.push("/dashboard");
    } catch {
      setCompleting(false);
    }
  }

  return (
    <div
      className="min-h-screen"
      style={{
        background: "linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #0f0f1a 100%)",
      }}
    >
      {/* Top bar with sign out */}
      <div
        className="flex items-center justify-between px-6 py-4"
        style={{ borderBottom: "1px solid rgba(99,102,241,0.12)" }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-sm"
            style={{ background: "rgba(99,102,241,0.2)" }}
          >
            ⚡
          </div>
          <span className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
            Kronode
          </span>
        </div>
        <LogoutButton variant="dark" />
      </div>

      <div className="max-w-2xl mx-auto px-4 py-10 space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold" style={{ color: "#e2e8f0" }}>
            Set up your AI teammate
          </h1>
          <p className="text-sm" style={{ color: "#64748b" }}>
            Complete the steps below to get Kronode ready to work.
          </p>
          <div className="flex items-center justify-center gap-2 pt-1">
            <div
              className="text-xs px-3 py-1 rounded-full"
              style={{
                background: "rgba(99,102,241,0.12)",
                color: allDone ? "#34d399" : "#94a3b8",
                border: `1px solid ${allDone ? "rgba(52,211,153,0.3)" : "rgba(99,102,241,0.2)"}`,
              }}
            >
              {completedCount} / {totalStages} complete
            </div>
          </div>
        </div>

        {/* Stage cards */}
        <div className="space-y-3">
          {STAGES.map((stage) => {
            const done = completedStages.has(stage.id);
            return (
              <div
                key={stage.id}
                className="flex items-center gap-4 rounded-2xl p-4 transition-all"
                style={{
                  background: done
                    ? "rgba(52,211,153,0.05)"
                    : "rgba(255,255,255,0.03)",
                  border: `1px solid ${
                    done ? "rgba(52,211,153,0.2)" : "rgba(99,102,241,0.15)"
                  }`,
                }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
                  style={{
                    background: done
                      ? "rgba(52,211,153,0.15)"
                      : "rgba(99,102,241,0.1)",
                  }}
                >
                  {done ? "✅" : stage.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div
                    className="text-sm font-semibold"
                    style={{ color: done ? "#34d399" : "#e2e8f0" }}
                  >
                    {stage.title}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "#475569" }}>
                    {stage.subtitle}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setOpenModal(stage.id)}
                  className="text-xs px-3 py-1.5 rounded-lg flex-shrink-0 transition-all"
                  style={{
                    background: done
                      ? "rgba(52,211,153,0.1)"
                      : "rgba(99,102,241,0.15)",
                    color: done ? "#34d399" : "#a78bfa",
                    border: `1px solid ${
                      done ? "rgba(52,211,153,0.3)" : "rgba(99,102,241,0.3)"
                    }`,
                  }}
                >
                  {done ? "Edit" : stage.cta}
                </button>
              </div>
            );
          })}
        </div>

        {/* Complete button */}
        <button
          type="button"
          onClick={handleComplete}
          disabled={!allDone || completing}
          className="w-full py-3.5 rounded-2xl font-semibold text-white text-sm transition-all"
          style={{
            background:
              allDone && !completing
                ? "linear-gradient(135deg, #6366f1, #a78bfa)"
                : "rgba(99,102,241,0.15)",
            cursor: allDone && !completing ? "pointer" : "not-allowed",
            opacity: completing ? 0.7 : 1,
          }}
        >
          {completing ? "Setting up your agent…" : "Launch Kronode →"}
        </button>
      </div>

      {/* Modals */}
      {STAGES.map((stage) => (
        <Modal
          key={stage.id}
          isOpen={openModal === stage.id}
          onClose={() => setOpenModal(null)}
          title={stage.title}
        >
          {stage.form(() => handleSave(stage.id))}
        </Modal>
      ))}
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUser, useAuth } from "@clerk/nextjs";
import { useOnboardingStore } from "@/lib/store";
import type { OnboardingState } from "@/lib/types";
import {
  saveAgent,
  saveAgentProfile,
  saveRepo,
  saveGithubToken,
  saveCapabilities,
  saveGuardrails,
  saveContext,
  saveAccount,
  saveJira,
  saveSlack,
  testSlack,
  testGithubToken,
  testJira,
  completeOnboarding,
  getOnboardingStatus,
  getOnboardingConfig,
} from "@/lib/api";
import StageBar from "./StageBar";
import SetupCard from "./SetupCard";
import AgentUnderstanding from "./AgentUnderstanding";
import Modal from "@/components/ui/Modal";

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

// ─── Agent profile data ────────────────────────────────────────────────────────

export const PROFILE_OPTIONS = [
  { key: "web",            name: "Web Engineer",             icon: "🌐", chips: ["React", "Next.js", "TypeScript", "Tailwind"] },
  { key: "backend",        name: "Backend Engineer",          icon: "⚙️",  chips: ["Python", "FastAPI", "PostgreSQL", "Redis"] },
  { key: "fullstack",      name: "Full-Stack Engineer",       icon: "🔀", chips: ["Next.js", "FastAPI", "TypeScript"] },
  { key: "devops",         name: "DevOps Engineer",           icon: "🏗️", chips: ["Docker", "Kubernetes", "Terraform", "GH Actions"] },
  { key: "mobile_ios",     name: "Mobile Engineer (iOS)",     icon: "📱", chips: ["Swift", "SwiftUI", "Combine"] },
  { key: "mobile_android", name: "Mobile Engineer (Android)", icon: "🤖", chips: ["Kotlin", "Jetpack Compose"] },
  { key: "data",           name: "Data Engineer",             icon: "📊", chips: ["Python", "dbt", "Airflow", "Snowflake"] },
];

function AgentProfileForm({ onSave }: { onSave: () => void }) {
  const { agentProfile, setAgentProfile } = useOnboardingStore();
  const [selected, setSelected] = useState(agentProfile?.profile_key || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSave() {
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      await saveAgentProfile({ profile_key: selected });
      const found = PROFILE_OPTIONS.find((p) => p.key === selected)!;
      setAgentProfile({ profile_key: found.key, profile_name: found.name });
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm" style={{ color: "#64748b" }}>
        Your agent will be a world-class specialist in this domain. The profile shapes its
        judgement, conventions, and which files it touches.
      </p>
      <div className="space-y-2">
        {PROFILE_OPTIONS.map((p) => {
          const isSelected = selected === p.key;
          return (
            <button
              key={p.key}
              type="button"
              onClick={() => setSelected(p.key)}
              className="w-full text-left rounded-xl px-4 py-3 transition-all"
              style={{
                background: isSelected ? "rgba(99,102,241,0.1)" : "rgba(255,255,255,0.03)",
                border: `1px solid ${isSelected ? "rgba(99,102,241,0.6)" : "rgba(255,255,255,0.08)"}`,
              }}
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">{p.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium" style={{ color: isSelected ? "#a5b4fc" : "#e2e8f0" }}>
                    {p.name}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {p.chips.map((chip) => (
                      <span
                        key={chip}
                        className="text-xs rounded px-1.5 py-0.5"
                        style={{
                          background: "rgba(99,102,241,0.12)",
                          color: "#94a3b8",
                        }}
                      >
                        {chip}
                      </span>
                    ))}
                  </div>
                </div>
                {isSelected && (
                  <span className="text-sm" style={{ color: "#6366f1" }}>✓</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!selected} label="Set profile" />
    </div>
  );
}

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

function RepoForm({ onSave, onFail }: { onSave: () => void; onFail?: () => void }) {
  const { repo, setRepo } = useOnboardingStore();
  const [provider, setProvider] = useState<"github" | "gitlab">(
    (repo?.provider as "github" | "gitlab") || "github"
  );
  const [repoUrl, setRepoUrl] = useState(repo?.repo_url || "");
  const [pat, setPat] = useState("");
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState("");
  const repoName = repoUrl.split("/").slice(-1)[0]?.replace(".git", "") || "";
  const valid = repoUrl.trim().startsWith("http") && pat.trim().length > 0;

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testGithubToken({ token: pat.trim(), repo_url: repoUrl.trim() });
      if (res.data.ok) {
        setTestResult({ ok: true, message: `Connected as ${res.data.login} · ${res.data.repo}` });
      } else {
        setTestResult({ ok: false, message: res.data.error || "Connection failed" });
      }
    } catch {
      setTestResult({ ok: false, message: "Could not reach server" });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      const check = await testGithubToken({ token: pat.trim(), repo_url: repoUrl.trim() });
      if (!check.data.ok) {
        setError(check.data.error || "Could not connect to GitHub — please check your token and repo URL");
        onFail?.();
        return;
      }
      await saveRepo({ provider, repo_url: repoUrl, repo_name: repoName });
      await saveGithubToken({ token: pat.trim() });
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
      <div className="flex gap-2">
        {(["github", "gitlab"] as const).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setProvider(p)}
            className="flex-1 py-2 rounded-lg text-sm font-medium capitalize transition-all"
            style={
              provider === p
                ? { background: "linear-gradient(135deg, #6366f1, #a78bfa)", color: "#fff", border: "none" }
                : { background: "rgba(255,255,255,0.04)", color: "#94a3b8", border: "1px solid rgba(99,102,241,0.2)" }
            }
          >
            {p}
          </button>
        ))}
      </div>
      <div>
        <FieldLabel>Repository URL</FieldLabel>
        <input
          style={inputCls}
          placeholder={`https://${provider}.com/your-org/your-repo`}
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      {repoName && (
        <div
          className="flex items-center gap-2 text-sm rounded-lg px-3 py-2"
          style={{ background: "rgba(52,211,153,0.07)", border: "1px solid rgba(52,211,153,0.2)", color: "#34d399" }}
        >
          <span>✓</span>
          <span>Detected: <strong>{repoName}</strong></span>
        </div>
      )}
      <div>
        <FieldLabel>Personal Access Token</FieldLabel>
        <input
          style={inputCls}
          type="password"
          placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
          value={pat}
          onChange={(e) => setPat(e.target.value)}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
        <p className="text-xs mt-1.5" style={{ color: "#475569" }}>
          Needs <code style={{ color: "#6366f1" }}>repo</code> scope.{" "}
          <a
            href="https://github.com/settings/tokens/new?scopes=repo&description=Kronode"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#6366f1", textDecoration: "underline" }}
          >
            Generate one →
          </a>
        </p>
      </div>
      <div
        className="text-xs px-4 py-3 rounded-lg"
        style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)", color: "#64748b" }}
      >
        Your agent only creates branches — it will never push to main or merge pull requests.
      </div>
      {valid && (
        <button
          type="button"
          onClick={handleTest}
          disabled={testing}
          className="w-full py-2 rounded-lg text-sm font-medium transition-all"
          style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc" }}
        >
          {testing ? "Checking…" : "Test connection"}
        </button>
      )}
      {testResult && (
        <div
          className="flex items-start gap-2 text-sm rounded-lg px-3 py-2.5"
          style={{
            background: testResult.ok ? "rgba(52,211,153,0.07)" : "rgba(239,68,68,0.07)",
            border: `1px solid ${testResult.ok ? "rgba(52,211,153,0.25)" : "rgba(239,68,68,0.25)"}`,
            color: testResult.ok ? "#34d399" : "#f87171",
          }}
        >
          <span>{testResult.ok ? "✓" : "✗"}</span>
          <span>{testResult.message}</span>
        </div>
      )}
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

const DEFAULT_CAPS = {
  building: {
    "Implement UI screens": true,
    "Build API connections": true,
    "Write unit tests": true,
    "Database schema changes": false,
    "Infrastructure changes": false,
  },
  planning: {
    "Create Epics from documents": true,
    "Create Jira tickets": true,
    "Estimate story points": true,
    "Reprioritise existing backlog": false,
  },
  review: {
    "Create Pull Requests": true,
    "Review PRs and leave comments": true,
    "Approve and merge PRs": false,
  },
  communication: {
    "Post Slack progress updates": true,
    "Ask clarifying questions via Slack": true,
    "Read meeting transcripts": true,
    "Join live meetings": false,
  },
};

const LOCKED_OFF = new Set(["Approve and merge PRs"]);

function CapabilitiesForm({ onSave }: { onSave: () => void }) {
  const { capabilities, setCapabilities } = useOnboardingStore();
  const [caps, setCaps] = useState<typeof DEFAULT_CAPS>(
    (capabilities as typeof DEFAULT_CAPS) || DEFAULT_CAPS
  );
  const [loading, setLoading] = useState(false);

  function toggle(category: string, item: string) {
    if (LOCKED_OFF.has(item)) return;
    setCaps((prev) => ({
      ...prev,
      [category]: {
        ...prev[category as keyof typeof prev],
        [item]: !prev[category as keyof typeof prev][item as keyof (typeof prev)[keyof typeof prev]],
      },
    }));
  }

  const [error, setError] = useState("");

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
    <div className="space-y-5">
      <p className="text-sm" style={{ color: "#64748b" }}>
        You can change these at any time from the dashboard.
      </p>
      {Object.entries(caps).map(([category, items]) => (
        <div key={category}>
          <h4
            className="text-xs font-semibold uppercase tracking-wider mb-2"
            style={{ color: "#475569" }}
          >
            {category}
          </h4>
          <div className="space-y-1">
            {Object.entries(items).map(([item, enabled]) => {
              const locked = LOCKED_OFF.has(item);
              return (
                <label
                  key={item}
                  className="flex items-center gap-3 p-2.5 rounded-lg"
                  style={{
                    cursor: locked ? "not-allowed" : "pointer",
                    opacity: locked ? 0.45 : 1,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => toggle(category, item)}
                    disabled={locked}
                    className="w-4 h-4 rounded"
                    style={{ accentColor: "#6366f1" }}
                  />
                  <span className="text-sm flex-1" style={{ color: "#94a3b8" }}>{item}</span>
                  {locked && (
                    <span className="text-xs" style={{ color: "#334155" }}>Human-only</span>
                  )}
                </label>
              );
            })}
          </div>
        </div>
      ))}
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={false} />
    </div>
  );
}

const RISK_LEVELS = [
  { value: "conservative", label: "Conservative", desc: "Ask before anything non-trivial" },
  { value: "balanced", label: "Balanced", desc: "Proceed on clear tasks, ask on ambiguous ones" },
  { value: "aggressive", label: "Aggressive", desc: "Minimise questions, maximise autonomy" },
];

function GuardrailsForm({ onSave }: { onSave: () => void }) {
  const { guardrails, setGuardrails } = useOnboardingStore();
  const [pathInput, setPathInput] = useState("");
  const [paths, setPaths] = useState<string[]>(
    guardrails?.restricted_paths || ["/payments", "/auth"]
  );
  const [maxFiles, setMaxFiles] = useState(guardrails?.max_files_per_task || 10);
  const [riskLevel, setRiskLevel] = useState(guardrails?.risk_level || "balanced");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function addPath() {
    const p = pathInput.trim();
    if (p && !paths.includes(p)) {
      setPaths([...paths, p]);
      setPathInput("");
    }
  }

  async function handleSave() {
    setLoading(true);
    setError("");
    const data = { restricted_paths: paths, max_files_per_task: maxFiles, risk_level: riskLevel };
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
    <div className="space-y-5">
      {/* Restricted paths */}
      <div>
        <FieldLabel>Restricted folders and files</FieldLabel>
        <div className="flex gap-2">
          <input
            style={{ ...inputCls, width: "auto", flex: 1 }}
            placeholder="/payments or /auth/tokens"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onFocus={focusBorder}
            onBlur={blurBorder}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addPath())}
          />
          <button
            type="button"
            onClick={addPath}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc" }}
          >
            Add
          </button>
        </div>
        {paths.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {paths.map((p) => (
              <span
                key={p}
                className="flex items-center gap-1 text-xs px-2 py-1 rounded-full"
                style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.25)", color: "#f87171" }}
              >
                {p}
                <button
                  type="button"
                  onClick={() => setPaths(paths.filter((x) => x !== p))}
                  className="font-bold hover:opacity-70 ml-0.5"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Max files */}
      <div>
        <FieldLabel>Maximum files changed per task</FieldLabel>
        <input
          type="number"
          min={1}
          max={50}
          value={maxFiles}
          onChange={(e) => setMaxFiles(parseInt(e.target.value) || 10)}
          style={{ ...inputCls, width: "6rem" }}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>

      {/* Risk level */}
      <div>
        <FieldLabel>Risk level</FieldLabel>
        <div className="space-y-2">
          {RISK_LEVELS.map((r) => (
            <label
              key={r.value}
              className="flex items-start gap-3 p-3 rounded-lg cursor-pointer"
              style={{
                border: `1px solid ${riskLevel === r.value ? "rgba(99,102,241,0.5)" : "rgba(99,102,241,0.15)"}`,
                background: riskLevel === r.value ? "rgba(99,102,241,0.06)" : "transparent",
              }}
            >
              <input
                type="radio"
                name="risk"
                value={r.value}
                checked={riskLevel === r.value}
                onChange={() => setRiskLevel(r.value)}
                className="mt-0.5"
                style={{ accentColor: "#6366f1" }}
              />
              <div>
                <div className="text-sm font-medium" style={{ color: "#e2e8f0" }}>{r.label}</div>
                <div className="text-xs" style={{ color: "#64748b" }}>{r.desc}</div>
              </div>
            </label>
          ))}
        </div>
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={false} />
    </div>
  );
}

function ContextForm({ onSave }: { onSave: () => void }) {
  const { agent, projectContext, codingStandards, setProjectContext, setCodingStandards } = useOnboardingStore();
  const [text, setText] = useState(projectContext || "");
  const [standards, setStandards] = useState(codingStandards || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const agentName = agent?.agent_name || "Your agent";
  const valid = text.trim().length >= 20;

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      await saveContext({ project_context: text, coding_standards: standards });
      setProjectContext(text);
      setCodingStandards(standards);
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: "#64748b" }}>
        Plain English — no technical knowledge required. This is injected into every task so{" "}
        {agentName} builds for your specific product.
      </p>
      <textarea
        className="w-full rounded-xl px-4 py-3 text-sm resize-y outline-none"
        style={{
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(99,102,241,0.2)",
          color: "#e2e8f0",
          minHeight: "150px",
        }}
        placeholder={`What does your product do?\nWhat tech stack are you using? (rough is fine — "I think it's React")\nAnything the agent should never do?`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,0.6)")}
        onBlur={(e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,0.2)")}
      />
      {text.length > 0 && text.length < 20 && (
        <p className="text-xs" style={{ color: "#475569" }}>
          Add a bit more context — at least a sentence or two.
        </p>
      )}
      <div>
        <label className="text-sm font-medium block mb-1.5" style={{ color: "#94a3b8" }}>
          Team coding standards <span style={{ color: "#475569", fontWeight: 400 }}>(optional)</span>
        </label>
        <textarea
          className="w-full rounded-xl px-4 py-3 text-sm resize-y outline-none"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(99,102,241,0.2)",
            color: "#e2e8f0",
            minHeight: "100px",
          }}
          placeholder={`e.g. Always use named exports\nPrefer async/await over .then()\nTests go in __tests__/ next to the file being tested`}
          value={standards}
          onChange={(e) => setStandards(e.target.value)}
          onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,0.6)")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,0.2)")}
        />
        <p className="text-xs mt-1" style={{ color: "#475569" }}>
          Injected into every agent call between profile and task instructions.
        </p>
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

const ROLES = ["PM", "Founder", "Stakeholder", "Engineer", "Other"];

function ProfileForm({ onSave }: { onSave: () => void }) {
  const { account, setAccount } = useOnboardingStore();
  const { user } = useUser();
  const clerkName = user?.fullName || user?.firstName || "";
  const [form, setForm] = useState({
    name: account?.name || clerkName,
    company_name: account?.company_name || "",
    role: account?.role || "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const valid = form.name.trim() && form.company_name.trim() && form.role;

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      await saveAccount(form);
      setAccount(form);
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
          style={{ ...inputCls, color: "#64748b", cursor: "default" }}
          value={form.name}
          readOnly
        />
        <p className="text-xs mt-1" style={{ color: "#334155" }}>From your sign-in account</p>
      </div>
      <div>
        <FieldLabel>Company name</FieldLabel>
        <input
          style={inputCls}
          placeholder="Acme Inc."
          value={form.company_name}
          onChange={(e) => setForm({ ...form, company_name: e.target.value })}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Your role</FieldLabel>
        <div className="flex flex-wrap gap-2">
          {ROLES.map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => setForm({ ...form, role })}
              className="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
              style={
                form.role === role
                  ? { background: "linear-gradient(135deg, #6366f1, #a78bfa)", color: "#fff", border: "1px solid transparent" }
                  : { background: "rgba(255,255,255,0.04)", color: "#94a3b8", border: "1px solid rgba(99,102,241,0.2)" }
              }
            >
              {role}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

function JiraForm({ onSave, onFail }: { onSave: () => void; onFail?: () => void }) {
  const { jira, setJira } = useOnboardingStore();
  const [form, setForm] = useState({
    workspace_url: jira?.workspace_url || "",
    project_key: jira?.project_key || "",
    email: jira?.email || "",
    api_token: jira?.api_token || "",
  });
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState("");
  const valid = form.workspace_url.trim() && form.project_key.trim() && form.email.trim() && form.api_token.trim();

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testJira({ workspace_url: form.workspace_url.trim(), project_key: form.project_key.trim(), email: form.email.trim(), api_token: form.api_token.trim() });
      if (res.data.ok) {
        setTestResult({ ok: true, message: `Connected as ${res.data.user} · project: ${res.data.project}` });
      } else {
        setTestResult({ ok: false, message: res.data.error || "Connection failed" });
      }
    } catch {
      setTestResult({ ok: false, message: "Could not reach server" });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    try {
      const check = await testJira({ workspace_url: form.workspace_url.trim(), project_key: form.project_key.trim(), email: form.email.trim(), api_token: form.api_token.trim() });
      if (!check.data.ok) {
        setError(check.data.error || "Could not connect to Jira — please check your credentials");
        onFail?.();
        return;
      }
      await saveJira(form);
      setJira(form);
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: "#64748b" }}>
        Your agent will read tickets, update statuses, and link pull requests.
      </p>
      <div>
        <FieldLabel>Jira workspace URL</FieldLabel>
        <input
          style={inputCls}
          placeholder="https://your-team.atlassian.net"
          value={form.workspace_url}
          onChange={(e) => setForm({ ...form, workspace_url: e.target.value })}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Project key</FieldLabel>
        <input
          style={inputCls}
          placeholder="e.g. KR or ACME"
          value={form.project_key}
          onChange={(e) => setForm({ ...form, project_key: e.target.value.toUpperCase() })}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
        <p className="text-xs mt-1.5" style={{ color: "#475569" }}>
          The short code shown before ticket numbers (e.g. KR-42)
        </p>
      </div>
      <div>
        <FieldLabel>Atlassian account email</FieldLabel>
        <input
          style={inputCls}
          type="email"
          placeholder="you@company.com"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>API token</FieldLabel>
        <input
          style={inputCls}
          type="password"
          placeholder="Atlassian API token"
          value={form.api_token}
          onChange={(e) => setForm({ ...form, api_token: e.target.value })}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
        <p className="text-xs mt-1.5" style={{ color: "#475569" }}>
          Generate at{" "}
          <a
            href="https://id.atlassian.com/manage-profile/security/api-tokens"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#a5b4fc" }}
          >
            id.atlassian.com → API tokens
          </a>
        </p>
      </div>
      {valid && (
        <button
          type="button"
          onClick={handleTest}
          disabled={testing}
          className="w-full py-2 rounded-lg text-sm font-medium transition-all"
          style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc" }}
        >
          {testing ? "Checking…" : "Test connection"}
        </button>
      )}
      {testResult && (
        <div
          className="flex items-start gap-2 text-sm rounded-lg px-3 py-2.5"
          style={{
            background: testResult.ok ? "rgba(52,211,153,0.07)" : "rgba(239,68,68,0.07)",
            border: `1px solid ${testResult.ok ? "rgba(52,211,153,0.25)" : "rgba(239,68,68,0.25)"}`,
            color: testResult.ok ? "#34d399" : "#f87171",
          }}
        >
          <span>{testResult.ok ? "✓" : "✗"}</span>
          <span>{testResult.message}</span>
        </div>
      )}
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

function SlackForm({ onSave, onFail }: { onSave: () => void; onFail?: () => void }) {
  const { agent, slack, setSlack } = useOnboardingStore();
  const [form, setForm] = useState({
    channel_id: slack?.channel_id || "",
    channel_name: slack?.channel_name || "",
    bot_token: slack?.bot_token || "",
  });
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState("");
  const agentName = agent?.agent_name || "Your agent";
  const valid = form.channel_name.trim() && form.bot_token.trim();

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testSlack({ bot_token: form.bot_token.trim(), channel_name: form.channel_name.trim() });
      if (res.data.ok) {
        setTestResult({ ok: true, message: `Connected to ${form.channel_name} · workspace: ${res.data.workspace}` });
      } else {
        setTestResult({ ok: false, message: res.data.error || "Connection failed" });
      }
    } catch {
      setTestResult({ ok: false, message: "Could not reach server" });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    if (!valid) return;
    setLoading(true);
    setError("");
    const payload = {
      channel_id: form.channel_id || form.channel_name,
      channel_name: form.channel_name,
      bot_token: form.bot_token,
    };
    try {
      const check = await testSlack({ bot_token: form.bot_token.trim(), channel_name: form.channel_name.trim() });
      if (!check.data.ok) {
        setError(check.data.error || "Could not connect to Slack — please check your token and channel");
        onFail?.();
        return;
      }
      await saveSlack(payload);
      setSlack(payload);
      onSave();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: "#64748b" }}>
        {agentName} will post progress updates here so your team stays informed.
      </p>

      {/* Setup steps */}
      <div
        className="rounded-xl p-4 space-y-3"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
      >
        <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "#475569" }}>
          How to get a bot token
        </p>
        {[
          {
            n: 1,
            text: (
              <>
                Go to{" "}
                <a href="https://api.slack.com/apps" target="_blank" rel="noreferrer" style={{ color: "#a5b4fc" }}>
                  api.slack.com/apps
                </a>
                {" "}→ <strong style={{ color: "#e2e8f0" }}>Create New App</strong> → <strong style={{ color: "#e2e8f0" }}>From scratch</strong>
              </>
            ),
          },
          {
            n: 2,
            text: (
              <>
                Open <strong style={{ color: "#e2e8f0" }}>OAuth &amp; Permissions</strong>, scroll to{" "}
                <strong style={{ color: "#e2e8f0" }}>Bot Token Scopes</strong>, and add{" "}
                <span style={{ color: "#a5b4fc" }}>chat:write</span>
              </>
            ),
          },
          {
            n: 3,
            text: (
              <>
                Click <strong style={{ color: "#e2e8f0" }}>Install to Workspace</strong> and copy the{" "}
                <span style={{ color: "#a5b4fc" }}>xoxb-</span> token
              </>
            ),
          },
          {
            n: 4,
            text: (
              <>
                In Slack, invite the bot to your channel:{" "}
                <span
                  className="rounded px-1.5 py-0.5 font-mono text-xs"
                  style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc" }}
                >
                  /invite @YourAppName
                </span>
              </>
            ),
          },
        ].map(({ n, text }) => (
          <div key={n} className="flex items-start gap-3">
            <div
              className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5"
              style={{ background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }}
            >
              {n}
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "#94a3b8" }}>{text}</p>
          </div>
        ))}
      </div>

      <div>
        <FieldLabel>Slack channel name</FieldLabel>
        <input
          style={inputCls}
          placeholder="#dev-updates"
          value={form.channel_name}
          onChange={(e) => setForm({ ...form, channel_name: e.target.value })}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      <div>
        <FieldLabel>Bot token</FieldLabel>
        <input
          style={inputCls}
          type="password"
          placeholder="xoxb-..."
          value={form.bot_token}
          onChange={(e) => setForm({ ...form, bot_token: e.target.value })}
          onFocus={focusBorder}
          onBlur={blurBorder}
        />
      </div>
      {form.channel_name && (
        <div
          className="rounded-xl p-4 space-y-2"
          style={{ background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)" }}
        >
          <p className="text-xs uppercase tracking-wide" style={{ color: "#475569" }}>
            Preview in {form.channel_name}
          </p>
          <div className="flex items-start gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: "linear-gradient(135deg, #6366f1, #a78bfa)" }}
            >
              <span className="text-white text-xs font-bold">K</span>
            </div>
            <div>
              <span className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>{agentName}</span>
              <p className="text-sm mt-0.5" style={{ color: "#94a3b8" }}>
                ✅ PR opened:{" "}
                <span style={{ color: "#a5b4fc" }}>Add forgot password screen #42</span>
                {" "}— ready for your review.
              </p>
            </div>
          </div>
        </div>
      )}
      {valid && (
        <button
          type="button"
          onClick={handleTest}
          disabled={testing}
          className="w-full py-2 rounded-lg text-sm font-medium transition-all"
          style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc" }}
        >
          {testing ? "Checking…" : "Test connection"}
        </button>
      )}
      {testResult && (
        <div
          className="flex items-start gap-2 text-sm rounded-lg px-3 py-2.5"
          style={{
            background: testResult.ok ? "rgba(52,211,153,0.07)" : "rgba(239,68,68,0.07)",
            border: `1px solid ${testResult.ok ? "rgba(52,211,153,0.25)" : "rgba(239,68,68,0.25)"}`,
            color: testResult.ok ? "#34d399" : "#f87171",
          }}
        >
          <span>{testResult.ok ? "✓" : "✗"}</span>
          <span>{testResult.message}</span>
        </div>
      )}
      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}
      <SaveBtn onClick={handleSave} loading={loading} disabled={!valid} />
    </div>
  );
}

// ─── Stage computation ────────────────────────────────────────────────────────

function computeStage(store: OnboardingState): number {
  if (!store.agentProfile) return 1;                                        // Hired
  if (!store.agent?.agent_name) return 2;                                   // Orientation
  if (!store.repo || !store.capabilities) return 3;                         // Training
  if (!store.projectContext || store.projectContext.length < 20) return 4;  // Shadowing
  if (!store.guardrails) return 5;                                          // First Task
  if (!store.jira && !store.slack) return 5;
  return 6;                                                                  // Autonomy
}

// ─── Main component ───────────────────────────────────────────────────────────

const MODAL_TITLES: Record<string, string> = {
  agent_profile: "Choose specialist role",
  agent: "Name your agent",
  repo: "Connect repository",
  capabilities: "Set capabilities",
  guardrails: "Set guardrails",
  context: "Project context",
  profile: "Your profile",
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
          // Hydrate the Zustand store from the backend so settings survive logout/new sessions
          const res = await getOnboardingConfig();
          const c = res.data;
          if (c.agent_profile) {
            const found = PROFILE_OPTIONS.find((p) => p.key === c.agent_profile);
            if (found) store.setAgentProfile({ profile_key: found.key, profile_name: found.name });
          }
          if (c.agent_name) store.setAgent({ agent_name: c.agent_name, agent_avatar: c.agent_avatar || "" });
          if (c.repo_url) store.setRepo({ provider: c.repo_provider || "github", repo_url: c.repo_url, repo_name: c.repo_name || "" });
          if (c.capabilities) store.setCapabilities(c.capabilities);
          if (c.guardrails) store.setGuardrails(c.guardrails);
          if (c.project_context) store.setProjectContext(c.project_context);
          if (c.coding_standards) store.setCodingStandards(c.coding_standards);
          if (c.user_name) store.setAccount({ name: c.user_name, company_name: c.company_name || "", role: c.user_role || "" });
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
  // Required cards done at stage 5 — Jira/Slack (stage 6) are optional, don't block launch
  const requiredDone = currentStage >= 5;

  async function handleLaunch() {
    setLaunching(true);
    try { await completeOnboarding(); } catch {}
    store.reset();
    router.push("/dashboard");
  }

  const cards = [
    {
      id: "agent_profile",
      icon: "👔",
      title: "Choose specialist role",
      description: store.agentProfile?.profile_name ?? "Select the engineering domain your agent works in",
      required: true,
      completed: !!store.agentProfile,
    },
    {
      id: "agent",
      icon: "🤖",
      title: "Name your agent",
      description: isSettings && store.agent?.agent_name
        ? `${store.agent.agent_avatar} ${store.agent.agent_name}`
        : "Give your AI developer a name and avatar",
      required: true,
      completed: !!store.agent?.agent_name,
    },
    {
      id: "repo",
      icon: "🔗",
      title: "Connect GitHub",
      description: isSettings && store.repo?.repo_name
        ? store.repo.repo_name
        : "Point to the repo your agent will work in",
      required: true,
      completed: !!store.repo,
    },
    {
      id: "capabilities",
      icon: "⚡",
      title: "Set capabilities",
      description: "Choose what your agent is allowed to do",
      required: true,
      completed: !!store.capabilities,
    },
    {
      id: "guardrails",
      icon: "🛡️",
      title: "Set guardrails",
      description: isSettings && store.guardrails
        ? `${store.guardrails.risk_level} · max ${store.guardrails.max_files_per_task} files`
        : "Define limits and off-limits paths",
      required: true,
      completed: !!store.guardrails,
    },
    {
      id: "context",
      icon: "📝",
      title: "Project context",
      description: isSettings && store.projectContext.length >= 20
        ? store.projectContext.slice(0, 60) + (store.projectContext.length > 60 ? "…" : "")
        : "Describe your project in plain English",
      required: true,
      completed: store.projectContext.length >= 20,
    },
    {
      id: "profile",
      icon: "👤",
      title: "Your profile",
      description: isSettings && store.account?.name
        ? `${store.account.name} · ${store.account.company_name}`
        : "Name, company, and role",
      required: false,
      completed: !!store.account,
    },
    {
      id: "jira",
      icon: "🏷️",
      title: "Connect Jira",
      description: isSettings && store.jira?.project_key
        ? `${store.jira.project_key} · ${store.jira.workspace_url.replace("https://", "")}`
        : "Let your agent read and update tickets",
      required: false,
      completed: !!store.jira,
    },
    {
      id: "slack",
      icon: "💬",
      title: "Connect Slack",
      description: isSettings && store.slack?.channel_name
        ? store.slack.channel_name
        : "Get progress updates in your channel",
      required: false,
      completed: !!store.slack,
    },
  ];

  // Assign incrementing index to non-completed cards
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
            <a
              href="/dashboard"
              className="text-sm font-medium inline-flex items-center gap-1.5 mb-3"
              style={{ color: "#6366f1" }}
            >
              ← Back to dashboard
            </a>
            <h1 className="text-2xl font-bold" style={{ color: "#e2e8f0" }}>
              Settings
            </h1>
            <p className="text-sm mt-1" style={{ color: "#64748b" }}>
              Update your agent configuration and integrations at any time.
            </p>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium mb-1" style={{ color: "#6366f1" }}>
              {firstName ? `Welcome, ${firstName}!` : "Welcome!"}
            </p>
            <h1 className="text-2xl font-bold" style={{ color: "#e2e8f0" }}>
              Meet your new teammate
            </h1>
            <p className="text-sm mt-1" style={{ color: "#64748b" }}>
              Set up your AI developer in any order. Complete required sections to launch.
            </p>
          </div>
        )}

        {/* Stage bar — onboarding only */}
        {!isSettings && <StageBar currentStage={currentStage} />}

        {/* Grid + sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Cards */}
          <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {cardsWithIdx.map((card) => (
              <SetupCard
                key={card.id}
                icon={card.icon}
                title={card.title}
                description={card.description}
                status={
                  card.completed
                    ? "completed"
                    : failedCards.has(card.id)
                    ? "failed"
                    : card.required
                    ? "pending"
                    : "optional"
                }
                index={card.index}
                onClick={() => setOpenCard(card.id)}
              />
            ))}
          </div>

          {/* Sidebar */}
          <AgentUnderstanding
            agentName={store.agent?.agent_name || null}
            agentAvatar={store.agent?.agent_avatar || null}
            agentProfile={store.agentProfile?.profile_name || null}
            repoName={store.repo?.repo_name || null}
            capabilities={store.capabilities}
            guardrails={store.guardrails}
            projectContext={store.projectContext}
          />
        </div>

        {/* Launch CTA — onboarding only */}
        {!isSettings && requiredDone && (
          <button
            onClick={handleLaunch}
            disabled={launching}
            className="w-full py-4 rounded-xl font-semibold text-white text-sm transition-all"
            style={{
              background: "linear-gradient(135deg, #6366f1, #a78bfa)",
              boxShadow: "0 0 30px rgba(99,102,241,0.35)",
              opacity: launching ? 0.7 : 1,
              cursor: launching ? "not-allowed" : "pointer",
            }}
          >
            {launching ? "Launching…" : "Launch kronode →"}
          </button>
        )}

        {/* Progress hint — onboarding only */}
        {!isSettings && !requiredDone && (
          <p className="text-xs text-center" style={{ color: "#334155" }}>
            {cards.filter((c) => c.required && !c.completed).length} required{" "}
            {cards.filter((c) => c.required && !c.completed).length === 1 ? "section" : "sections"} remaining
          </p>
        )}
      </div>

      {/* Modal */}
      {openCard && (
        <Modal
          open
          onClose={() => setOpenCard(null)}
          title={MODAL_TITLES[openCard] || ""}
        >
          {openCard === "agent_profile" && <AgentProfileForm onSave={() => setOpenCard(null)} />}
          {openCard === "agent" && <AgentForm onSave={() => setOpenCard(null)} />}
          {openCard === "repo" && <RepoForm onSave={() => markSaved("repo")} onFail={() => markFailed("repo")} />}
          {openCard === "capabilities" && <CapabilitiesForm onSave={() => setOpenCard(null)} />}
          {openCard === "guardrails" && <GuardrailsForm onSave={() => setOpenCard(null)} />}
          {openCard === "context" && <ContextForm onSave={() => setOpenCard(null)} />}
          {openCard === "profile" && <ProfileForm onSave={() => setOpenCard(null)} />}
          {openCard === "jira" && <JiraForm onSave={() => markSaved("jira")} onFail={() => markFailed("jira")} />}
          {openCard === "slack" && <SlackForm onSave={() => markSaved("slack")} onFail={() => markFailed("slack")} />}
        </Modal>
      )}
    </>
  );
}

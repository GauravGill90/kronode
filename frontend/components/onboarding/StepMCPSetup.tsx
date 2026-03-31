"use client";

import { useState, useEffect } from "react";
import { generateApiKey, listApiKeys } from "@/lib/api";

const AGENT_CONFIGS: Record<string, {
  name: string;
  file: string;
  rootKey: string;
  note?: string;
}> = {
  "claude-code": {
    name: "Claude Code",
    file: ".mcp.json",
    rootKey: "mcpServers",
    note: "Or run: claude mcp add kronode -- python -m app.mcp.main --token TOKEN",
  },
  cursor: {
    name: "Cursor",
    file: ".cursor/mcp.json",
    rootKey: "mcpServers",
  },
  windsurf: {
    name: "Windsurf",
    file: "~/.codeium/windsurf/mcp_config.json",
    rootKey: "mcpServers",
  },
  copilot: {
    name: "GitHub Copilot (VS Code)",
    file: ".vscode/mcp.json",
    rootKey: "servers",
    note: "Root key is 'servers' not 'mcpServers'",
  },
  cline: {
    name: "Cline",
    file: "cline_mcp_settings.json",
    rootKey: "mcpServers",
  },
  continue: {
    name: "Continue",
    file: ".continue/mcpServers/kronode.json",
    rootKey: "mcpServers",
  },
  "amazon-q": {
    name: "Amazon Q",
    file: "~/.aws/amazonq/mcp.json",
    rootKey: "mcpServers",
  },
  jetbrains: {
    name: "JetBrains AI",
    file: "mcp.json",
    rootKey: "mcpServers",
  },
  zed: {
    name: "Zed",
    file: "settings.json",
    rootKey: "context_servers",
    note: "Root key is 'context_servers' not 'mcpServers'",
  },
  tabnine: {
    name: "Tabnine",
    file: ".tabnine/mcp_servers.json",
    rootKey: "mcpServers",
  },
  codex: {
    name: "OpenAI Codex",
    file: "~/.codex/config.toml",
    rootKey: "mcpServers",
    note: "Or run: codex mcp add kronode -- python -m app.mcp.main --token TOKEN",
  },
};

function generateConfig(agent: string, token: string, remote: boolean): string {
  const info = AGENT_CONFIGS[agent];
  if (!info) return "";

  const TOOL_APPROVALS = `
[mcp_servers.kronode.tools.kronode_workflow]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_context]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_doc]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_file_companions]
approval_mode = "approve"

[mcp_servers.kronode.tools.get_reviewer_guidance]
approval_mode = "approve"

[mcp_servers.kronode.tools.check_completeness]
approval_mode = "approve"`;

  // Codex uses TOML
  if (agent === "codex") {
    if (remote) {
      return `[mcp_servers.kronode]
url = "https://api.kronode.dev/mcp/sse"

[mcp_servers.kronode.headers]
Authorization = "Bearer ${token}"
${TOOL_APPROVALS}`;
    }
    return `[mcp_servers.kronode]
command = "python"
args = ["-m", "app.mcp.main", "--token", "${token}"]
${TOOL_APPROVALS}`;
  }

  const serverConfig = remote
    ? { url: "https://api.kronode.dev/mcp/sse", headers: { Authorization: `Bearer ${token}` } }
    : { command: "python", args: ["-m", "app.mcp.main", "--token", token], env: {} };

  const config = { [info.rootKey]: { kronode: serverConfig } };
  return JSON.stringify(config, null, 2);
}

interface Props {
  onDone?: () => void;
}

export default function StepMCPSetup({ onDone }: Props) {
  const [apiKey, setApiKey] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("claude-code");
  const [useRemote, setUseRemote] = useState(false);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);
  const [existingKeys, setExistingKeys] = useState<any[]>([]);

  useEffect(() => {
    loadKeys();
  }, []);

  async function loadKeys() {
    try {
      const resp = await listApiKeys();
      setExistingKeys(resp.data || []);
    } catch {}
  }

  async function handleGenerateKey() {
    setLoading(true);
    try {
      const resp = await generateApiKey({ name: "mcp-setup" });
      setApiKey(resp.data.key);
    } catch (e: any) {
      alert("Failed to generate API key: " + (e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    const config = generateConfig(selectedAgent, apiKey, useRemote);
    navigator.clipboard.writeText(config);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const agentInfo = AGENT_CONFIGS[selectedAgent];
  const config = apiKey ? generateConfig(selectedAgent, apiKey, useRemote) : "";

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">Connect Your AI Tool</h3>
        <p className="text-sm text-text-secondary">
          Generate an API key and add Kronode to your AI coding tool.
        </p>
      </div>

      {/* Step 1: Generate API Key */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-text-primary">1. Generate API Key</label>
        {apiKey ? (
          <div className="bg-surface-raised rounded-lg p-3 border border-surface-border">
            <code className="text-status-success text-sm break-all">{apiKey}</code>
            <p className="text-xs text-text-muted mt-1">Save this key — it won't be shown again.</p>
          </div>
        ) : (
          <div>
            {existingKeys.length > 0 && (
              <p className="text-xs text-text-muted mb-2">
                You have {existingKeys.length} existing key(s). Generate a new one for this setup.
              </p>
            )}
            <button
              onClick={handleGenerateKey}
              disabled={loading}
              className="px-4 py-2 bg-brand hover:bg-brand-500 text-white rounded-lg text-sm disabled:opacity-50"
            >
              {loading ? "Generating..." : "Generate API Key"}
            </button>
          </div>
        )}
      </div>

      {/* Step 2: Select AI Tool */}
      {apiKey && (
        <div className="space-y-3">
          <label className="block text-sm font-medium text-text-primary">2. Select Your AI Tool</label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(AGENT_CONFIGS).map(([key, info]) => (
              <button
                key={key}
                onClick={() => setSelectedAgent(key)}
                className={`px-3 py-2 rounded-lg text-sm text-left transition ${
                  selectedAgent === key
                    ? "bg-brand text-white"
                    : "bg-surface-overlay text-text-primary hover:bg-surface-border"
                }`}
              >
                {info.name}
              </button>
            ))}
          </div>

          {/* Transport toggle */}
          <div className="flex items-center gap-3 mt-2">
            <label className="text-sm text-text-secondary">Transport:</label>
            <button
              onClick={() => setUseRemote(false)}
              className={`px-3 py-1 rounded text-xs ${!useRemote ? "bg-brand text-white" : "bg-surface-overlay text-text-secondary"}`}
            >
              Local (stdio)
            </button>
            <button
              onClick={() => setUseRemote(true)}
              className={`px-3 py-1 rounded text-xs ${useRemote ? "bg-brand text-white" : "bg-surface-overlay text-text-secondary"}`}
            >
              Remote (HTTP)
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Config */}
      {config && (
        <div className="space-y-3">
          <label className="block text-sm font-medium text-text-primary">
            3. Add to <code className="text-brand">{agentInfo.file}</code>
          </label>
          {agentInfo.note && (
            <p className="text-xs text-text-muted">{agentInfo.note}</p>
          )}
          <div className="relative">
            <pre className="bg-surface-raised rounded-lg p-4 border border-surface-border text-sm text-text-primary overflow-x-auto max-h-64">
              {config}
            </pre>
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 px-3 py-1 bg-zinc-700 hover:bg-surface-border-light text-white rounded text-xs"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>
      )}

      {/* Done */}
      {apiKey && (
        <div className="pt-4">
          <button
            onClick={onDone}
            className="w-full py-3 bg-brand hover:bg-brand-500 text-white rounded-lg font-medium"
          >
            Done — Start Using Kronode
          </button>
        </div>
      )}
    </div>
  );
}

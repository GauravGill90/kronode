"use client";

import { useState } from "react";
import StepMCPSetup from "@/components/onboarding/StepMCPSetup";

interface MCPTool {
  name: string;
  description: string;
}

interface Props {
  tools: MCPTool[];
}

export default function MCPTools({ tools }: Props) {
  const [showSetup, setShowSetup] = useState(false);

  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">MCP Tools</h3>
        <button
          onClick={() => setShowSetup(!showSetup)}
          className="text-xs px-3 py-1 rounded-lg bg-brand text-text-inverse font-medium hover:bg-brand-500 transition"
        >
          {showSetup ? "Hide Setup" : "Setup Instructions"}
        </button>
      </div>

      {showSetup && (
        <div className="mb-4 p-4 rounded-lg border border-surface-border bg-surface-overlay">
          <StepMCPSetup onDone={() => setShowSetup(false)} />
        </div>
      )}

      <div className="space-y-2">
        {tools.map((tool) => (
          <div key={tool.name} className="flex items-start gap-3 py-2">
            <code className="text-xs font-mono text-brand bg-brand/10 px-2 py-0.5 rounded shrink-0">
              {tool.name}
            </code>
            <p className="text-xs text-text-muted leading-relaxed">{tool.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

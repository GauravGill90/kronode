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
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">MCP Tools</h3>
        <button
          onClick={() => setShowSetup(!showSetup)}
          className="text-xs px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white"
        >
          {showSetup ? "Hide Setup" : "Setup Instructions"}
        </button>
      </div>

      {showSetup && (
        <div className="mb-4 p-4 rounded-lg border border-zinc-700 bg-zinc-800/50">
          <StepMCPSetup onDone={() => setShowSetup(false)} />
        </div>
      )}

      <div className="space-y-2">
        {tools.map((tool) => (
          <div key={tool.name} className="flex items-start gap-3 py-2">
            <code className="text-xs font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded shrink-0">
              {tool.name}
            </code>
            <p className="text-xs text-zinc-500 leading-relaxed">{tool.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

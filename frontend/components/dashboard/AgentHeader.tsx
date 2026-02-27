import type { AgentConfig } from "@/lib/types";

export default function AgentHeader({ agent }: { agent: AgentConfig }) {
  return (
    <div className="flex items-center gap-4 bg-white rounded-2xl p-5 border border-gray-200">
      <div className="w-14 h-14 bg-brand-500 rounded-2xl flex items-center justify-center text-3xl">
        {agent.agent_avatar}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-900">{agent.agent_name}</h2>
          <span className="w-2 h-2 rounded-full bg-green-400"></span>
          <span className="text-xs text-green-600">Ready</span>
        </div>
        <p className="text-sm text-gray-500">Your autonomous developer</p>
      </div>
    </div>
  );
}

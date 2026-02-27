"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { saveAgent } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

const SUGGESTIONS = ["Forge", "Relay", "Scout", "Hatch", "Stride"];
const AVATARS = ["🤖", "🛠️", "⚡", "🚀", "🔮", "🧠"];

export default function Step8AgentName() {
  const router = useRouter();
  const { setAgent, setStep } = useOnboardingStore();
  const [agentName, setAgentName] = useState("");
  const [avatar, setAvatar] = useState(AVATARS[0]);
  const [loading, setLoading] = useState(false);

  const valid = agentName.trim().length >= 2;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setLoading(true);
    try {
      await saveAgent({ agent_name: agentName, agent_avatar: avatar });
      setAgent({ agent_name: agentName, agent_avatar: avatar });
      setStep(9);
      router.push("/onboarding/9");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Name your agent</h1>
        <p className="text-sm text-gray-500 mt-1">
          This is the developer joining your team. Give them a name.
        </p>
      </div>

      {/* Avatar picker */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">Avatar</label>
        <div className="flex gap-3">
          {AVATARS.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setAvatar(a)}
              className={`w-12 h-12 text-2xl rounded-xl border-2 transition-all ${
                avatar === a ? "border-brand-500 bg-brand-50 scale-110" : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Name input */}
      <div className="space-y-3">
        <Input
          label="Agent name"
          placeholder="e.g. Forge"
          value={agentName}
          onChange={(e) => setAgentName(e.target.value)}
          required
        />
        <div className="flex gap-2 flex-wrap">
          <span className="text-xs text-gray-400">Suggestions:</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setAgentName(s)}
              className="text-xs text-brand-600 hover:text-brand-800 underline"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Preview */}
      {agentName && (
        <div className="flex items-center gap-3 bg-gray-50 rounded-xl p-4 border border-gray-200">
          <div className="w-12 h-12 bg-brand-500 rounded-xl flex items-center justify-center text-2xl">
            {avatar}
          </div>
          <div>
            <div className="font-semibold text-gray-900">{agentName}</div>
            <div className="text-xs text-gray-500">Your autonomous developer</div>
          </div>
          <div className="ml-auto w-2 h-2 rounded-full bg-green-400"></div>
        </div>
      )}

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/7")}>
          Back
        </Button>
        <Button type="submit" size="lg" className="flex-1" loading={loading} disabled={!valid}>
          Continue
        </Button>
      </div>
    </form>
  );
}

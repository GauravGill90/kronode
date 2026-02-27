"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { saveContext } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

const PLACEHOLDER = `What does your product do?
What tech stack are you using? (rough is fine — "I think it's React")
Anything the agent should never do?`;

export default function Step9Context() {
  const router = useRouter();
  const { agent, setProjectContext, setStep } = useOnboardingStore();
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);

  const agentName = agent?.agent_name || "Your agent";
  const valid = context.trim().length >= 20;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setLoading(true);
    try {
      await saveContext({ project_context: context });
      setProjectContext(context);
      setStep(10);
      router.push("/onboarding/10");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Tell {agentName} about your project</h1>
        <p className="text-sm text-gray-500 mt-1">
          Plain English — no technical knowledge required. This is injected into every task so {agentName} builds for your specific product.
        </p>
      </div>

      <textarea
        className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 min-h-[180px] resize-y focus:outline-none focus:ring-2 focus:ring-brand-500"
        placeholder={PLACEHOLDER}
        value={context}
        onChange={(e) => setContext(e.target.value)}
      />

      {context.length > 0 && context.length < 20 && (
        <p className="text-xs text-gray-400">Add a bit more context — at least a sentence or two.</p>
      )}

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/8")}>
          Back
        </Button>
        <Button type="submit" size="lg" className="flex-1" loading={loading} disabled={!valid}>
          Continue
        </Button>
      </div>
    </form>
  );
}

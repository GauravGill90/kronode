"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useOnboardingStore } from "@/lib/store";

export default function Step10Shadow() {
  const router = useRouter();
  const { agent, setStep } = useOnboardingStore();
  const agentName = agent?.agent_name || "Your agent";

  function proceed() {
    setStep(11);
    router.push("/onboarding/11");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Shadow teammate mode</h1>
        <p className="text-sm text-gray-500 mt-1">Coming soon</p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-amber-600 text-lg">🔭</span>
          <span className="font-semibold text-amber-800 text-sm">Learning from your team</span>
        </div>
        <p className="text-sm text-amber-700">
          In a future version, {agentName} will spend a sprint in read-only mode — watching your PRs,
          tickets, and Slack threads to understand how your team works before taking any autonomous action.
        </p>
        <p className="text-xs text-amber-600">This feature is being designed. Skip for now to continue setup.</p>
      </div>

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/9")}>
          Back
        </Button>
        <Button type="button" size="lg" className="flex-1" onClick={proceed}>
          Skip and continue
        </Button>
      </div>
    </div>
  );
}

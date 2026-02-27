"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { completeOnboarding } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

const STEPS = [
  { label: "Repository connected and scanned", delay: 800 },
  { label: "Jira project loaded", delay: 1600 },
  { label: "Slack channel confirmed", delay: 2200 },
  { label: "Capabilities and guardrails saved", delay: 2800 },
  { label: "Project context loaded", delay: 3400 },
  { label: "Agent is ready", delay: 4000 },
];

export default function Step11ReadingSetup() {
  const router = useRouter();
  const { agent } = useOnboardingStore();
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [done, setDone] = useState(false);

  const agentName = agent?.agent_name || "Your agent";
  const agentAvatar = agent?.agent_avatar || "🤖";

  useEffect(() => {
    STEPS.forEach((step, i) => {
      setTimeout(() => {
        setCompletedSteps((prev) => [...prev, i]);
        if (i === STEPS.length - 1) {
          setDone(true);
          completeOnboarding().catch(() => {});
        }
      }, step.delay);
    });
  }, []);

  return (
    <div className="space-y-8 text-center">
      {/* Agent avatar with pulse */}
      <div className="flex flex-col items-center gap-3">
        <div className={`w-20 h-20 bg-brand-500 rounded-3xl flex items-center justify-center text-4xl transition-all duration-500 ${done ? "scale-110" : "animate-pulse"}`}>
          {agentAvatar}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {done ? `${agentName} is ready` : `${agentName} is getting up to speed`}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {done ? "Everything is connected and working." : "Reading your setup…"}
          </p>
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-3 text-left">
        {STEPS.map((step, i) => {
          const complete = completedSteps.includes(i);
          const active = completedSteps.length === i;
          return (
            <div key={i} className={`flex items-center gap-3 transition-all duration-300 ${complete ? "opacity-100" : active ? "opacity-60" : "opacity-20"}`}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${complete ? "bg-green-500" : "bg-gray-200"}`}>
                {complete && <span className="text-white text-xs">✓</span>}
              </div>
              <span className={`text-sm ${complete ? "text-gray-900" : "text-gray-500"}`}>{step.label}</span>
            </div>
          );
        })}
      </div>

      {done && (
        <button
          onClick={() => router.push("/dashboard")}
          className="w-full bg-brand-500 hover:bg-brand-600 text-white font-medium py-3 px-6 rounded-xl transition-colors text-sm animate-in fade-in"
        >
          Go to your dashboard
        </button>
      )}
    </div>
  );
}

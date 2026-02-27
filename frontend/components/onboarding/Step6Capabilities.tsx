"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { saveCapabilities } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

const DEFAULT_CAPABILITIES = {
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

export default function Step6Capabilities() {
  const router = useRouter();
  const { setCapabilities, setStep } = useOnboardingStore();
  const [caps, setCaps] = useState(DEFAULT_CAPABILITIES);
  const [loading, setLoading] = useState(false);

  function toggle(category: string, item: string) {
    if (LOCKED_OFF.has(item)) return;
    setCaps((prev) => ({
      ...prev,
      [category]: { ...prev[category as keyof typeof prev], [item]: !prev[category as keyof typeof prev][item] },
    }));
  }

  async function handleSubmit() {
    setLoading(true);
    try {
      await saveCapabilities(caps);
      setCapabilities(caps);
      setStep(7);
      router.push("/onboarding/7");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">What can your agent do?</h1>
        <p className="text-sm text-gray-500 mt-1">
          You can change these at any time from the dashboard.
        </p>
      </div>

      <div className="space-y-5">
        {Object.entries(caps).map(([category, items]) => (
          <div key={category}>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              {category}
            </h3>
            <div className="space-y-1">
              {Object.entries(items).map(([item, enabled]) => {
                const locked = LOCKED_OFF.has(item);
                return (
                  <label
                    key={item}
                    className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors ${locked ? "opacity-50 cursor-not-allowed" : "hover:bg-gray-50"}`}
                  >
                    <input
                      type="checkbox"
                      checked={enabled}
                      onChange={() => toggle(category, item)}
                      disabled={locked}
                      className="w-4 h-4 text-brand-500 rounded border-gray-300"
                    />
                    <span className="text-sm text-gray-700">{item}</span>
                    {locked && <span className="text-xs text-gray-400 ml-auto">Human-only</span>}
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/5")}>
          Back
        </Button>
        <Button type="button" size="lg" className="flex-1" loading={loading} onClick={handleSubmit}>
          Continue
        </Button>
      </div>
    </div>
  );
}

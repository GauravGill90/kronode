"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { saveSlack } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

export default function Step4Slack() {
  const router = useRouter();
  const { agent, setSlack, setStep } = useOnboardingStore();
  const [form, setForm] = useState({ channel_id: "", channel_name: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const agentName = agent?.agent_name || "Your agent";
  const valid = form.channel_name.trim();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setLoading(true);
    const payload = { channel_id: form.channel_id || form.channel_name, channel_name: form.channel_name };
    try {
      await saveSlack(payload);
      setSlack(payload);
      setStep(5);
      router.push("/onboarding/5");
    } catch {
      setError("Couldn't save your Slack settings. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Connect Slack</h1>
        <p className="text-sm text-gray-500 mt-1">
          {agentName} will post progress updates here so your team stays informed without checking dashboards.
        </p>
      </div>

      <Input
        label="Slack channel name"
        placeholder="#dev-updates"
        value={form.channel_name}
        onChange={(e) => setForm({ ...form, channel_name: e.target.value })}
        hint="The channel where your agent will post updates"
      />

      {/* Preview message */}
      {form.channel_name && (
        <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 space-y-2">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Preview in {form.channel_name}</p>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center flex-shrink-0">
              <span className="text-white text-xs font-bold">K</span>
            </div>
            <div>
              <span className="text-sm font-semibold text-gray-900">{agentName}</span>
              <p className="text-sm text-gray-700 mt-0.5">
                ✅ PR opened: <span className="text-brand-600 underline">Add forgot password screen #42</span> — ready for your review.
              </p>
            </div>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/3")}>
          Back
        </Button>
        <Button type="submit" size="lg" className="flex-1" loading={loading} disabled={!valid}>
          Continue
        </Button>
      </div>
      <button type="button" className="w-full text-sm text-gray-400 hover:text-gray-600 text-center" onClick={() => { setStep(5); router.push("/onboarding/5"); }}>
        Skip for now
      </button>
    </form>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { saveJira } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

export default function Step3Jira() {
  const router = useRouter();
  const { setJira, setStep } = useOnboardingStore();
  const [form, setForm] = useState({ workspace_url: "", project_key: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const valid = form.workspace_url.trim() && form.project_key.trim();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setLoading(true);
    try {
      await saveJira(form);
      setJira(form);
      setStep(4);
      router.push("/onboarding/4");
    } catch {
      setError("Couldn't save your Jira settings. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Connect Jira</h1>
        <p className="text-sm text-gray-500 mt-1">
          Your agent will read tickets, update statuses, and link pull requests.
        </p>
      </div>

      <div className="space-y-4">
        <Input
          label="Jira workspace URL"
          placeholder="https://your-team.atlassian.net"
          value={form.workspace_url}
          onChange={(e) => setForm({ ...form, workspace_url: e.target.value })}
        />
        <Input
          label="Project key"
          placeholder="e.g. KR or ACME"
          value={form.project_key}
          onChange={(e) => setForm({ ...form, project_key: e.target.value.toUpperCase() })}
          hint="The short code shown before ticket numbers (e.g. KR-42)"
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/2")}>
          Back
        </Button>
        <Button type="submit" size="lg" className="flex-1" loading={loading} disabled={!valid}>
          Continue
        </Button>
      </div>
      <button type="button" className="w-full text-sm text-gray-400 hover:text-gray-600 text-center" onClick={() => { setStep(4); router.push("/onboarding/4"); }}>
        Skip for now
      </button>
    </form>
  );
}

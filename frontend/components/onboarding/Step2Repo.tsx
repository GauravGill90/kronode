"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { saveRepo } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

export default function Step2Repo() {
  const router = useRouter();
  const { setRepo, setStep } = useOnboardingStore();
  const [provider, setProvider] = useState<"github" | "gitlab">("github");
  const [repoUrl, setRepoUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const repoName = repoUrl.split("/").slice(-1)[0]?.replace(".git", "") || "";
  const valid = repoUrl.trim().startsWith("http");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setLoading(true);
    try {
      await saveRepo({ provider, repo_url: repoUrl, repo_name: repoName });
      setRepo({ provider, repo_url: repoUrl, repo_name: repoName });
      setStep(3);
      router.push("/onboarding/3");
    } catch {
      setError("Couldn't save your repository. Check the URL and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Connect your repository</h1>
        <p className="text-sm text-gray-500 mt-1">
          Your agent works in branches only — it will never touch main.
        </p>
      </div>

      <div className="space-y-4">
        {/* Provider toggle */}
        <div className="flex gap-2">
          {(["github", "gitlab"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setProvider(p)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors capitalize ${
                provider === p
                  ? "bg-brand-500 text-white border-brand-500"
                  : "bg-white text-gray-700 border-gray-300 hover:border-brand-400"
              }`}
            >
              {p}
            </button>
          ))}
        </div>

        <Input
          label="Repository URL"
          placeholder={`https://${provider}.com/your-org/your-repo`}
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          hint="Paste the full URL of the repository you want to connect"
        />

        {repoName && (
          <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2 border border-green-200">
            <span className="font-medium">✓</span>
            <span>Repository: <strong>{repoName}</strong></span>
          </div>
        )}
      </div>

      <div className="bg-blue-50 rounded-lg px-4 py-3 text-sm text-blue-700 border border-blue-200">
        Your agent only creates branches. It can never push to main or merge pull requests.
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/1")}>
          Back
        </Button>
        <Button type="submit" size="lg" className="flex-1" loading={loading} disabled={!valid}>
          Continue
        </Button>
      </div>
    </form>
  );
}

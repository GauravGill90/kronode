"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { useOnboardingStore } from "@/lib/store";

export default function Step5Docs() {
  const router = useRouter();
  const { setStep } = useOnboardingStore();

  function skip() {
    setStep(6);
    router.push("/onboarding/6");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Connect your docs</h1>
        <p className="text-sm text-gray-500 mt-1">
          Optional — lets your agent read PRDs, specs, and design docs to build more accurately.
        </p>
      </div>

      <div className="space-y-3">
        <button
          type="button"
          className="w-full flex items-center gap-4 p-4 rounded-xl border border-gray-200 hover:border-brand-400 bg-white transition-colors text-left"
          onClick={skip}
        >
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-lg">C</div>
          <div>
            <div className="font-medium text-gray-900 text-sm">Confluence</div>
            <div className="text-xs text-gray-500">Connect a Confluence space</div>
          </div>
        </button>
        <button
          type="button"
          className="w-full flex items-center gap-4 p-4 rounded-xl border border-gray-200 hover:border-brand-400 bg-white transition-colors text-left"
          onClick={skip}
        >
          <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center text-lg">G</div>
          <div>
            <div className="font-medium text-gray-900 text-sm">Google Drive</div>
            <div className="text-xs text-gray-500">Connect a Google Drive folder</div>
          </div>
        </button>
      </div>

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/4")}>
          Back
        </Button>
        <Button type="button" variant="ghost" size="lg" className="flex-1" onClick={skip}>
          Skip — add later
        </Button>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { saveGuardrails } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

const RISK_LEVELS = [
  { value: "conservative", label: "Conservative", desc: "Ask before anything non-trivial" },
  { value: "balanced", label: "Balanced", desc: "Proceed on clear tasks, ask on ambiguous ones" },
  { value: "aggressive", label: "Aggressive", desc: "Minimise questions, maximise autonomy" },
];

export default function Step7Guardrails() {
  const router = useRouter();
  const { setGuardrails, setStep } = useOnboardingStore();
  const [restrictedInput, setRestrictedInput] = useState("");
  const [paths, setPaths] = useState<string[]>(["/payments", "/auth"]);
  const [maxFiles, setMaxFiles] = useState(10);
  const [riskLevel, setRiskLevel] = useState("balanced");
  const [loading, setLoading] = useState(false);

  function addPath() {
    const p = restrictedInput.trim();
    if (p && !paths.includes(p)) {
      setPaths([...paths, p]);
      setRestrictedInput("");
    }
  }

  async function handleSubmit() {
    setLoading(true);
    const data = { restricted_paths: paths, max_files_per_task: maxFiles, risk_level: riskLevel };
    try {
      await saveGuardrails(data);
      setGuardrails(data);
      setStep(8);
      router.push("/onboarding/8");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Set guardrails</h1>
        <p className="text-sm text-gray-500 mt-1">
          Define what your agent is never allowed to touch.
        </p>
      </div>

      {/* Restricted paths */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">Restricted folders and files</label>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="/payments or /auth/tokens"
            value={restrictedInput}
            onChange={(e) => setRestrictedInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addPath())}
          />
          <Button type="button" variant="secondary" size="sm" onClick={addPath}>Add</Button>
        </div>
        {paths.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {paths.map((p) => (
              <span key={p} className="flex items-center gap-1 bg-red-50 text-red-700 text-xs px-2 py-1 rounded-full border border-red-200">
                {p}
                <button type="button" onClick={() => setPaths(paths.filter((x) => x !== p))} className="hover:text-red-900 font-bold">×</button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Max files */}
      <div className="space-y-1.5">
        <label className="block text-sm font-medium text-gray-700">Maximum files changed per task</label>
        <input
          type="number"
          min={1}
          max={50}
          value={maxFiles}
          onChange={(e) => setMaxFiles(parseInt(e.target.value) || 10)}
          className="w-24 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>

      {/* Risk level */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">Risk level</label>
        <div className="space-y-2">
          {RISK_LEVELS.map((r) => (
            <label key={r.value} className="flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors hover:bg-gray-50"
              style={{ borderColor: riskLevel === r.value ? "#4f6ef7" : "#e5e7eb" }}>
              <input type="radio" name="risk" value={r.value} checked={riskLevel === r.value}
                onChange={() => setRiskLevel(r.value)} className="mt-0.5 text-brand-500" />
              <div>
                <div className="text-sm font-medium text-gray-900">{r.label}</div>
                <div className="text-xs text-gray-500">{r.desc}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="flex gap-3">
        <Button type="button" variant="secondary" size="lg" className="flex-1" onClick={() => router.push("/onboarding/6")}>
          Back
        </Button>
        <Button type="button" size="lg" className="flex-1" loading={loading} onClick={handleSubmit}>
          Continue
        </Button>
      </div>
    </div>
  );
}

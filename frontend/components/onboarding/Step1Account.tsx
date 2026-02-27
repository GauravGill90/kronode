"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveAccount } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

const ROLES = ["PM", "Founder", "Stakeholder", "Engineer", "Other"];

const inputStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(99,102,241,0.2)",
  borderRadius: "10px",
  color: "#e2e8f0",
  padding: "10px 14px",
  fontSize: "14px",
  width: "100%",
  outline: "none",
};

export default function Step1Account() {
  const router = useRouter();
  const { setAccount, setStep } = useOnboardingStore();
  const [form, setForm] = useState({ name: "", company_name: "", role: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const valid = form.name.trim() && form.company_name.trim() && form.role;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setLoading(true);
    try {
      await saveAccount(form);
      setAccount(form);
      setStep(2);
      router.push("/onboarding/2");
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-7">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "#e2e8f0" }}>Tell us about yourself</h1>
        <p className="text-sm mt-1" style={{ color: "#64748b" }}>Just a few fields — takes under a minute.</p>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium block" style={{ color: "#94a3b8" }}>Your name</label>
          <input
            style={inputStyle}
            placeholder="Alex Johnson"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            onFocus={(e) => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
            onBlur={(e) => (e.target.style.borderColor = "rgba(99,102,241,0.2)")}
            required
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium block" style={{ color: "#94a3b8" }}>Company name</label>
          <input
            style={inputStyle}
            placeholder="Acme Inc."
            value={form.company_name}
            onChange={(e) => setForm({ ...form, company_name: e.target.value })}
            onFocus={(e) => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
            onBlur={(e) => (e.target.style.borderColor = "rgba(99,102,241,0.2)")}
            required
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium block" style={{ color: "#94a3b8" }}>Your role</label>
          <div className="flex flex-wrap gap-2">
            {ROLES.map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => setForm({ ...form, role })}
                className="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
                style={form.role === role ? {
                  background: "linear-gradient(135deg, #6366f1, #a78bfa)",
                  color: "#fff",
                  border: "1px solid transparent",
                } : {
                  background: "rgba(255,255,255,0.04)",
                  color: "#94a3b8",
                  border: "1px solid rgba(99,102,241,0.2)",
                }}
              >
                {role}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-sm" style={{ color: "#f87171" }}>{error}</p>}

      <button
        type="submit"
        disabled={!valid || loading}
        className="w-full py-3.5 rounded-xl font-semibold text-white text-sm transition-all"
        style={{
          background: valid ? "linear-gradient(135deg, #6366f1, #a78bfa)" : "rgba(99,102,241,0.2)",
          cursor: valid ? "pointer" : "not-allowed",
          opacity: loading ? 0.7 : 1,
        }}
      >
        {loading ? "Saving…" : "Continue"}
      </button>
    </form>
  );
}

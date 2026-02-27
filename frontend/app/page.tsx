"use client";

import { SignInButton, SignUpButton, useUser } from "@clerk/nextjs";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function WelcomePage() {
  const { isSignedIn, isLoaded } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      router.push("/onboarding");
    }
  }, [isLoaded, isSignedIn, router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden"
      style={{ background: "#080810" }}>

      {/* Ambient glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(ellipse, rgba(99,102,241,0.15) 0%, transparent 70%)" }} />
      <div className="absolute bottom-0 left-1/4 w-[400px] h-[300px] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(ellipse, rgba(167,139,250,0.08) 0%, transparent 70%)" }} />
      <div className="absolute bottom-0 right-1/4 w-[400px] h-[300px] rounded-full pointer-events-none"
        style={{ background: "radial-gradient(ellipse, rgba(56,189,248,0.08) 0%, transparent 70%)" }} />

      {/* Grid overlay */}
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(99,102,241,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.04) 1px, transparent 1px)",
          backgroundSize: "40px 40px"
        }} />

      <div className="relative z-10 max-w-md w-full text-center space-y-10">

        {/* Logo */}
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #6366f1, #a78bfa)",
              boxShadow: "0 0 40px rgba(99,102,241,0.4)"
            }}>
            <span className="text-white font-bold text-2xl">K</span>
          </div>
          <div>
            <h1 className="text-4xl font-bold tracking-tight"
              style={{
                background: "linear-gradient(135deg, #e2e8f0 0%, #a5b4fc 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent"
              }}>
              kronode
            </h1>
            <p className="text-sm mt-1 tracking-widest uppercase font-medium" style={{ color: "#6366f1" }}>
              autonomous AI developer
            </p>
          </div>
        </div>

        {/* Headline */}
        <div className="space-y-3">
          <h2 className="text-2xl font-semibold leading-snug" style={{ color: "#e2e8f0" }}>
            Describe what to build.{" "}
            <span style={{
              background: "linear-gradient(90deg, #a78bfa, #38bdf8)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent"
            }}>
              Your agent ships the PR.
            </span>
          </h2>
          <p className="text-sm leading-relaxed max-w-sm mx-auto" style={{ color: "#94a3b8" }}>
            Connect GitHub, Jira, and Slack. Write a task in plain English.
            Kronode plans, codes, tests, and opens a pull request — you approve and merge.
          </p>
        </div>

        {/* Trust signals */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { icon: "🔀", title: "Branches only", desc: "Never touches main" },
            { icon: "✅", title: "You approve", desc: "Every PR reviewed by you" },
            { icon: "🛡️", title: "Guardrails", desc: "You set the limits" },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="rounded-xl p-3 text-center"
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(99,102,241,0.2)"
              }}>
              <div className="text-lg mb-1">{icon}</div>
              <div className="text-xs font-semibold" style={{ color: "#e2e8f0" }}>{title}</div>
              <div className="text-xs mt-0.5" style={{ color: "#64748b" }}>{desc}</div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="space-y-3">
          <SignUpButton mode="modal" afterSignUpUrl="/onboarding" asChild>
            <button
              className="w-full py-3.5 rounded-xl font-semibold text-white text-sm transition-all hover:opacity-90 cursor-pointer"
              style={{
                background: "linear-gradient(135deg, #6366f1, #a78bfa)",
                boxShadow: "0 0 30px rgba(99,102,241,0.3)"
              }}>
              Get started free
            </button>
          </SignUpButton>

          <SignInButton mode="modal" afterSignInUrl="/onboarding" asChild>
            <button
              className="w-full py-3.5 rounded-xl font-medium text-sm transition-all cursor-pointer"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(99,102,241,0.25)",
                color: "#a5b4fc"
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,0.6)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,0.25)")}>
              Sign in
            </button>
          </SignInButton>

          <p className="text-xs" style={{ color: "#475569" }}>
            No credit card required · Free to start
          </p>
        </div>

      </div>
    </div>
  );
}

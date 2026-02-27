"use client";

import { SignInButton, SignUpButton, useUser } from "@clerk/nextjs";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { colors, gradients } from "@/tokens/colors";

export default function WelcomePage() {
  const { isSignedIn, isLoaded } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      router.push("/onboarding");
    }
  }, [isLoaded, isSignedIn, router]);

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden"
      style={{ background: colors.bg.base }}
    >
      {/* Ambient glow */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] rounded-full pointer-events-none"
        style={{ background: gradients.glowTop }}
      />
      <div
        className="absolute bottom-0 left-1/4 w-[400px] h-[300px] rounded-full pointer-events-none"
        style={{ background: gradients.glowBottomLeft }}
      />
      <div
        className="absolute bottom-0 right-1/4 w-[400px] h-[300px] rounded-full pointer-events-none"
        style={{ background: gradients.glowBottomRight }}
      />

      {/* Grid overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: gradients.gridOverlay,
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative z-10 max-w-md w-full text-center space-y-10">
        {/* Logo */}
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{
              background: gradients.brandLogo,
              boxShadow: `0 0 40px ${colors.glow.primary}`,
            }}
          >
            <span className="text-white font-bold text-2xl">K</span>
          </div>
          <div>
            <h1
              className="text-4xl font-bold tracking-tight"
              style={{
                background: gradients.brandText,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              kronode
            </h1>
            <p
              className="text-sm mt-1 tracking-widest uppercase font-medium"
              style={{ color: colors.brand.primary }}
            >
              autonomous AI developer
            </p>
          </div>
        </div>

        {/* Headline */}
        <div className="space-y-3">
          <h2
            className="text-2xl font-semibold leading-snug"
            style={{ color: colors.text.primary }}
          >
            Describe what to build.{" "}
            <span
              style={{
                background: gradients.brandAccent,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Your agent ships the PR.
            </span>
          </h2>
          <p
            className="text-sm leading-relaxed max-w-sm mx-auto"
            style={{ color: colors.text.secondary }}
          >
            Connect GitHub, Jira, and Slack. Write a task in plain English.
            Kronode plans, codes, tests, and opens a pull request — you approve
            and merge.
          </p>
        </div>

        {/* Trust signals */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { icon: "🔀", title: "Branches only", desc: "Never touches main" },
            { icon: "✅", title: "You approve", desc: "Every PR reviewed by you" },
            { icon: "🛡️", title: "Guardrails", desc: "You set the limits" },
          ].map(({ icon, title, desc }) => (
            <div
              key={title}
              className="rounded-xl p-3 text-center"
              style={{
                background: colors.bg.surface,
                border: `1px solid ${colors.border.default}`,
              }}
            >
              <div className="text-lg mb-1">{icon}</div>
              <div
                className="text-xs font-semibold mb-0.5"
                style={{ color: colors.text.primary }}
              >
                {title}
              </div>
              <div className="text-xs" style={{ color: colors.text.secondary }}>
                {desc}
              </div>
            </div>
          ))}
        </div>

        {/* CTA buttons */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <SignUpButton mode="modal">
            <button
              className="px-6 py-3 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: gradients.brandLogo,
                color: colors.text.white,
                boxShadow: `0 0 20px ${colors.glow.primarySoft}`,
              }}
            >
              Get started free
            </button>
          </SignUpButton>
          <SignInButton mode="modal">
            <button
              className="px-6 py-3 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: colors.bg.surface,
                color: colors.text.primary,
                border: `1px solid ${colors.border.default}`,
              }}
            >
              Sign in
            </button>
          </SignInButton>
        </div>

        {/* Footer note */}
        <p className="text-xs" style={{ color: colors.text.muted }}>
          No credit card required · Free during beta
        </p>
      </div>
    </div>
  );
}

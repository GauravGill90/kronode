"use client";

import { SignInButton, SignUpButton, useUser } from "@clerk/nextjs";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { colors, gradients } from "@/tokens/colors";
import { Brain, Plug, Shield } from "lucide-react";
import KronodeLogo from "@/components/ui/KronodeLogo";

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
          <div style={{ filter: `drop-shadow(0 0 30px ${colors.glow.primary})` }}>
            <KronodeLogo size={64} />
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
              organizational memory
            </p>
          </div>
        </div>

        {/* Headline */}
        <div className="space-y-3">
          <h2
            className="text-2xl font-semibold leading-snug"
            style={{ color: colors.text.primary }}
          >
            Your team&apos;s conventions.{" "}
            <span
              style={{
                background: gradients.brandAccent,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              In every AI tool.
            </span>
          </h2>
          <p
            className="text-sm leading-relaxed max-w-sm mx-auto"
            style={{ color: colors.text.secondary }}
          >
            Kronode learns your team&apos;s coding conventions, reviewer preferences, and documentation — then serves them to Claude Code, Cursor, Copilot, and 10+ other AI tools via MCP.
          </p>
        </div>

        {/* Trust signals */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { icon: <Brain className="w-5 h-5" />, title: "Learns from PRs", desc: "Extracts conventions automatically" },
            { icon: <Plug className="w-5 h-5" />, title: "Works everywhere", desc: "Any MCP-compatible AI tool" },
            { icon: <Shield className="w-5 h-5" />, title: "Your data, yours", desc: "Local embeddings, no code stored" },
          ].map(({ icon, title, desc }) => (
            <div
              key={title}
              className="rounded-xl p-4 text-center"
              style={{
                background: colors.bg.raised,
                border: `1px solid ${colors.border.default}`,
              }}
            >
              <div className="flex justify-center mb-2" style={{ color: colors.brand.primary }}>{icon}</div>
              <div className="text-xs font-semibold mb-0.5" style={{ color: colors.text.primary }}>{title}</div>
              <div className="text-xs" style={{ color: colors.text.secondary }}>{desc}</div>
            </div>
          ))}
        </div>

        {/* CTA buttons */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <SignUpButton mode="modal">
            <button
              className="px-6 py-3 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: colors.brand.primary,
                color: colors.bg.base,
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
                background: colors.bg.raised,
                color: colors.text.primary,
                border: `1px solid ${colors.border.default}`,
              }}
            >
              Sign in
            </button>
          </SignInButton>
        </div>

        <p className="text-xs" style={{ color: colors.text.muted }}>
          No credit card required · Free during beta
        </p>
      </div>
    </div>
  );
}

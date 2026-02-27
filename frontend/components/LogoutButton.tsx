"use client";

import { useClerk } from "@clerk/nextjs";

interface LogoutButtonProps {
  variant?: "light" | "dark";
}

export default function LogoutButton({ variant = "dark" }: LogoutButtonProps) {
  const { signOut } = useClerk();

  const isLight = variant === "light";

  return (
    <button
      onClick={() => signOut({ redirectUrl: "/" })}
      className="text-xs px-3 py-1.5 rounded-lg transition-colors"
      style={{
        color: isLight ? "#64748b" : "#94a3b8",
        border: `1px solid ${isLight ? "rgba(99,102,241,0.15)" : "rgba(148,163,184,0.2)"}`,
        background: "transparent",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = isLight ? "#1e293b" : "#e2e8f0";
        e.currentTarget.style.borderColor = isLight
          ? "rgba(99,102,241,0.4)"
          : "rgba(99,102,241,0.5)";
        e.currentTarget.style.background = isLight
          ? "rgba(99,102,241,0.06)"
          : "rgba(99,102,241,0.12)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = isLight ? "#64748b" : "#94a3b8";
        e.currentTarget.style.borderColor = isLight
          ? "rgba(99,102,241,0.15)"
          : "rgba(148,163,184,0.2)";
        e.currentTarget.style.background = "transparent";
      }}
    >
      Sign out
    </button>
  );
}

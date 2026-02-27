"use client";

import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

interface TopBarProps {
  /** Show a back link to the dashboard */
  backHref?: string;
  backLabel?: string;
  /** Visual theme: 'light' (white bg) or 'dark' (dark/transparent bg) */
  theme?: "light" | "dark";
}

export default function TopBar({
  backHref,
  backLabel = "← Dashboard",
  theme = "light",
}: TopBarProps) {
  const isLight = theme === "light";

  return (
    <div
      className="flex items-center justify-between px-4 py-3"
      style={{
        borderBottom: `1px solid ${isLight ? "#e5e7eb" : "rgba(99,102,241,0.12)"}`,
        background: isLight ? "#ffffff" : "transparent",
      }}
    >
      <div className="flex items-center gap-2">
        {backHref ? (
          <Link
            href={backHref}
            className="text-sm font-medium transition-colors"
            style={{ color: isLight ? "#6b7280" : "#64748b" }}
          >
            {backLabel}
          </Link>
        ) : (
          <span
            className="text-sm font-semibold tracking-tight"
            style={{ color: isLight ? "#111827" : "#e2e8f0" }}
          >
            Kronode
          </span>
        )}
      </div>
      <LogoutButton variant={isLight ? "light" : "dark"} />
    </div>
  );
}

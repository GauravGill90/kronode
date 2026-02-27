"use client";

import { useClerk } from "@clerk/nextjs";

export default function LogoutButton() {
  const { signOut } = useClerk();

  return (
    <button
      onClick={() => signOut({ redirectUrl: "/" })}
      className="text-xs px-3 py-1.5 rounded-lg transition-colors"
      style={{
        color: "#64748b",
        border: "1px solid rgba(99,102,241,0.15)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = "#e2e8f0";
        e.currentTarget.style.borderColor = "rgba(99,102,241,0.4)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = "#64748b";
        e.currentTarget.style.borderColor = "rgba(99,102,241,0.15)";
      }}
    >
      Sign out
    </button>
  );
}

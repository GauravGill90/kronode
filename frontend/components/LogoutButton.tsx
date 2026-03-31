"use client";

import { useClerk } from "@clerk/nextjs";

export default function LogoutButton() {
  const { signOut } = useClerk();

  return (
    <button
      onClick={() => signOut({ redirectUrl: "/" })}
      className="text-xs px-3 py-1.5 rounded-lg text-text-muted border border-surface-border hover:text-text-primary hover:border-brand/40 transition-colors"
    >
      Sign out
    </button>
  );
}

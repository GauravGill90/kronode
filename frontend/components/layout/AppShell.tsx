"use client";

import LogoutButton from "@/components/LogoutButton";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen" style={{ background: "#080810" }}>
      {/* Nav bar */}
      <header
        className="px-6 py-4 sticky top-0 z-10"
        style={{
          borderBottom: "1px solid rgba(99,102,241,0.1)",
          background: "rgba(8,8,16,0.85)",
          backdropFilter: "blur(12px)",
        }}
      >
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <a href="/dashboard" className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #6366f1, #a78bfa)" }}
            >
              <span className="text-white font-bold text-sm">K</span>
            </div>
            <span className="font-semibold text-sm" style={{ color: "#e2e8f0" }}>kronode</span>
          </a>
          <LogoutButton />
        </div>
      </header>

      {/* Page content */}
      <main>{children}</main>
    </div>
  );
}

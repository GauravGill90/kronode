"use client";

import LogoutButton from "@/components/LogoutButton";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-surface">
      {/* Nav bar */}
      <header className="px-6 py-4 sticky top-0 z-10 border-b border-surface-border bg-surface/85 backdrop-blur-xl">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <a href="/dashboard" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-brand">
              <span className="text-text-inverse font-bold text-sm">K</span>
            </div>
            <span className="font-semibold text-sm text-text-primary">kronode</span>
          </a>
          <LogoutButton />
        </div>
      </header>

      {/* Page content */}
      <main>{children}</main>
    </div>
  );
}

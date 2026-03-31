import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import LogoutButton from "@/components/LogoutButton";

export default async function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId } = await auth();
  if (!userId) redirect("/");

  return (
    <div className="min-h-screen bg-surface">
      <header className="px-6 py-4 border-b border-surface-border">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <svg width="28" height="28" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="64" height="64" rx="14" fill="#d4a853"/>
              <path d="M32 16 C24 16 18 22 18 30 C18 38 24 44 32 48 C40 44 46 38 46 30 C46 22 40 16 32 16Z" stroke="#1c1917" strokeWidth="2.5" fill="none"/>
              <line x1="32" y1="22" x2="32" y2="42" stroke="#1c1917" strokeWidth="2"/>
              <line x1="24" y1="28" x2="40" y2="28" stroke="#1c1917" strokeWidth="2"/>
              <line x1="24" y1="36" x2="40" y2="36" stroke="#1c1917" strokeWidth="2"/>
              <circle cx="32" cy="28" r="2.5" fill="#1c1917"/>
              <circle cx="32" cy="36" r="2.5" fill="#1c1917"/>
              <circle cx="24" cy="28" r="2" fill="#1c1917"/>
              <circle cx="40" cy="28" r="2" fill="#1c1917"/>
              <circle cx="24" cy="36" r="2" fill="#1c1917"/>
              <circle cx="40" cy="36" r="2" fill="#1c1917"/>
            </svg>
            <span className="font-semibold text-sm text-text-primary">kronode</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="/dashboard" className="text-sm font-medium text-text-muted hover:text-text-secondary transition">
              ← Dashboard
            </a>
            <LogoutButton />
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
    </div>
  );
}

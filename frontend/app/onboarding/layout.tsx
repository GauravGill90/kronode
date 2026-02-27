import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import LogoutButton from "@/components/LogoutButton";

export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId } = await auth();
  if (!userId) redirect("/");

  return (
    <div className="min-h-screen" style={{ background: "#080810" }}>
      {/* Top bar */}
      <header
        className="px-6 py-4"
        style={{ borderBottom: "1px solid rgba(99,102,241,0.12)" }}
      >
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #6366f1, #a78bfa)" }}
            >
              <span className="text-white font-bold text-sm">K</span>
            </div>
            <span className="font-semibold text-sm" style={{ color: "#e2e8f0" }}>
              kronode
            </span>
          </div>
          <LogoutButton />
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
    </div>
  );
}

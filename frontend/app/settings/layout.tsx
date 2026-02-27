import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import LogoutButton from "@/components/LogoutButton";
import { colors, gradients } from "@/tokens/colors";

export default async function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId } = await auth();
  if (!userId) redirect("/");

  return (
    <div className="min-h-screen" style={{ background: colors.bg.base }}>
      {/* Top bar */}
      <header
        className="px-6 py-4"
        style={{ borderBottom: `1px solid ${colors.border.subtle}` }}
      >
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: gradients.brandLogo }}
            >
              <span className="text-white font-bold text-sm">K</span>
            </div>
            <span
              className="font-semibold text-sm"
              style={{ color: colors.text.primary }}
            >
              kronode
            </span>
          </div>
          <div className="flex items-center gap-4">
            <a
              href="/dashboard"
              className="text-sm font-medium"
              style={{ color: colors.text.muted }}
            >
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

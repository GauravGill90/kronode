import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import OnboardingDashboard from "@/components/onboarding/OnboardingDashboard";

export default async function OnboardingPage() {
  const { userId } = await auth();
  if (!userId) redirect("/");

  return <OnboardingDashboard />;
}

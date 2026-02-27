import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import DashboardClient from "@/components/dashboard/DashboardClient";

export default async function DashboardPage() {
  const { userId } = await auth();
  if (!userId) redirect("/");
  return <DashboardClient />;
}

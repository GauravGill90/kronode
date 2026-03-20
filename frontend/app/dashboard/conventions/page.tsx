import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import ConventionsClient from "@/components/conventions/ConventionsClient";

export default async function ConventionsPage() {
  const { userId } = await auth();
  if (!userId) redirect("/");
  return <ConventionsClient />;
}

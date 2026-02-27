import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import TaskDetailClient from "@/components/task/TaskDetailClient";

export default async function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { userId } = await auth();
  if (!userId) redirect("/");
  const { id } = await params;
  return <TaskDetailClient taskId={id} />;
}

import { clsx } from "clsx";

type BadgeVariant = "default" | "success" | "warning" | "error" | "info" | "queued" | "running";

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
        {
          "bg-gray-100 text-gray-700": variant === "default",
          "bg-green-100 text-green-700": variant === "success",
          "bg-yellow-100 text-yellow-700": variant === "warning",
          "bg-red-100 text-red-700": variant === "error",
          "bg-blue-100 text-blue-700": variant === "info",
          "bg-gray-100 text-gray-500": variant === "queued",
          "bg-brand-100 text-brand-700 animate-pulse": variant === "running",
        },
        className
      )}
    >
      {children}
    </span>
  );
}

export function statusToBadge(status: string): BadgeVariant {
  switch (status) {
    case "done": return "success";
    case "failed": return "error";
    case "paused": return "warning";
    case "running": return "running";
    case "queued": return "queued";
    default: return "default";
  }
}

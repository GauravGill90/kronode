"use client";

interface ActivityItem {
  action: string;
  resource: string | null;
  details: Record<string, unknown> | null;
  timestamp: string;
}

interface Props {
  activity: ActivityItem[];
}

function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;

  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

function actionIcon(action: string): string {
  switch (action) {
    case "mcp_tool_call": return ">";
    case "api_request": return "*";
    case "webhook_received": return "~";
    case "convention_extracted": return "+";
    case "admin_action": return "#";
    default: return "-";
  }
}

function actionLabel(action: string): string {
  switch (action) {
    case "mcp_tool_call": return "MCP call";
    case "api_request": return "API request";
    case "webhook_received": return "Webhook";
    case "convention_extracted": return "Convention";
    case "admin_action": return "Admin";
    default: return action.replace(/_/g, " ");
  }
}

export default function RecentActivity({ activity }: Props) {
  if (activity.length === 0) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
        <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-3">Recent Activity</h3>
        <p className="text-xs text-zinc-600 text-center py-4">
          No activity yet. Activity will appear here as MCP tools are called, webhooks are received, and conventions are extracted.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-3">Recent Activity</h3>
      <div className="space-y-1.5">
        {activity.map((item, i) => (
          <div key={i} className="flex items-center gap-3 py-1.5 text-xs">
            <span className="text-zinc-600 font-mono w-4 text-center">{actionIcon(item.action)}</span>
            <span className="text-indigo-400 font-medium w-20 shrink-0">{actionLabel(item.action)}</span>
            {item.resource && (
              <code className="text-zinc-400 font-mono">{item.resource}</code>
            )}
            {item.details && (
              <span className="text-zinc-600 truncate">
                {typeof item.details === "object"
                  ? Object.values(item.details).filter(v => typeof v === "string").join(" — ").slice(0, 80)
                  : ""}
              </span>
            )}
            <span className="text-zinc-700 ml-auto shrink-0">{timeAgo(item.timestamp)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

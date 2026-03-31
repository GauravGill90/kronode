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
  const diff = Date.now() - new Date(timestamp).getTime();
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    mcp_tool_call: "MCP call",
    api_request: "API request",
    webhook_received: "Webhook",
    convention_extracted: "Convention",
    admin_action: "Admin",
  };
  return map[action] || action.replace(/_/g, " ");
}

export default function RecentActivity({ activity }: Props) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Recent Activity</h3>
      {activity.length === 0 ? (
        <p className="text-xs text-text-muted text-center py-4">
          No activity yet. Activity appears here as MCP tools are called and conventions are extracted.
        </p>
      ) : (
        <div className="space-y-1.5">
          {activity.map((item, i) => (
            <div key={i} className="flex items-center gap-3 py-1.5 text-xs">
              <span className="text-brand font-medium w-20 shrink-0">{actionLabel(item.action)}</span>
              {item.resource && <code className="text-text-secondary font-mono">{item.resource}</code>}
              <span className="text-text-muted ml-auto shrink-0">{timeAgo(item.timestamp)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

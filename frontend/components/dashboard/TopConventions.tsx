"use client";

interface Convention {
  id: number;
  rule: string;
  category: string;
  confidence: number;
  enforced_by: string[] | null;
}

interface Props {
  conventions: Convention[];
  total: number;
}

function categoryBadge(cat: string): string {
  const colors: Record<string, string> = {
    style: "text-purple-400 bg-purple-500/10",
    architecture: "text-blue-400 bg-blue-500/10",
    testing: "text-status-success bg-status-success/10",
    error_handling: "text-status-error bg-status-error/10",
    naming: "text-brand bg-brand/10",
    logging: "text-cyan-400 bg-cyan-500/10",
  };
  return colors[cat] || "text-text-muted bg-surface-overlay";
}

export default function TopConventions({ conventions, total }: Props) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Top Conventions</h3>
        <a href="/dashboard/conventions" className="text-xs text-brand hover:text-brand-300 transition">
          Browse all {total} →
        </a>
      </div>

      {conventions.length === 0 ? (
        <p className="text-xs text-text-muted text-center py-4">
          No conventions extracted yet. Connect a repo and run ingestion.
        </p>
      ) : (
        <div className="space-y-2">
          {conventions.map((c) => (
            <div key={c.id} className="flex items-start gap-3 py-2 border-b border-surface-border/50 last:border-0">
              <div className="w-1 h-8 rounded-full mt-0.5 shrink-0 overflow-hidden bg-surface-overlay">
                <div
                  className="w-full rounded-full bg-brand"
                  style={{ height: `${c.confidence * 100}%` }}
                />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text-primary leading-snug">{c.rule}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${categoryBadge(c.category)}`}>
                    {c.category}
                  </span>
                  <span className="text-[10px] text-text-muted">
                    {Math.round(c.confidence * 100)}%
                  </span>
                  {c.enforced_by && c.enforced_by.length > 0 && (
                    <span className="text-[10px] text-text-muted">
                      by {c.enforced_by.slice(0, 2).join(", ")}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

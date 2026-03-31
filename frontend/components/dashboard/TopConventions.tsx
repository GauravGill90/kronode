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

function confidenceColor(c: number): string {
  if (c >= 0.8) return "bg-emerald-500";
  if (c >= 0.5) return "bg-amber-500";
  return "bg-zinc-600";
}

function categoryBadge(cat: string): string {
  const colors: Record<string, string> = {
    style: "text-purple-400 bg-purple-500/10",
    architecture: "text-blue-400 bg-blue-500/10",
    testing: "text-green-400 bg-green-500/10",
    error_handling: "text-red-400 bg-red-500/10",
    naming: "text-amber-400 bg-amber-500/10",
    logging: "text-cyan-400 bg-cyan-500/10",
  };
  return colors[cat] || "text-zinc-400 bg-zinc-500/10";
}

export default function TopConventions({ conventions, total }: Props) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
          Top Conventions
        </h3>
        <a
          href="/dashboard/conventions"
          className="text-xs text-indigo-400 hover:text-indigo-300"
        >
          Browse all {total} →
        </a>
      </div>

      {conventions.length === 0 ? (
        <p className="text-xs text-zinc-600 text-center py-4">
          No conventions extracted yet. Connect a repo and run ingestion.
        </p>
      ) : (
        <div className="space-y-2">
          {conventions.map((c) => (
            <div key={c.id} className="flex items-start gap-3 py-2 border-b border-zinc-800/50 last:border-0">
              {/* Confidence bar */}
              <div className="w-1 h-8 rounded-full mt-0.5 shrink-0 overflow-hidden bg-zinc-800">
                <div
                  className={`w-full rounded-full ${confidenceColor(c.confidence)}`}
                  style={{ height: `${c.confidence * 100}%` }}
                />
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm text-zinc-300 leading-snug">{c.rule}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${categoryBadge(c.category)}`}>
                    {c.category}
                  </span>
                  <span className="text-[10px] text-zinc-600">
                    {Math.round(c.confidence * 100)}% confidence
                  </span>
                  {c.enforced_by && c.enforced_by.length > 0 && (
                    <span className="text-[10px] text-zinc-600">
                      enforced by {c.enforced_by.slice(0, 2).join(", ")}
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

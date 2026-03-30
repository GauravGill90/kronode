import type { PRStats } from "@/lib/types";

export default function PRStatsCard({ stats }: { stats: PRStats }) {
  if (stats.total_prs === 0 && stats.failed === 0) return null;

  const total = stats.total_prs + stats.failed;
  const rate = stats.acceptance_rate;

  return (
    <div
      className="rounded-xl p-5"
      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>
          PR Performance
        </h3>
        {rate !== null && (
          <span
            className="text-lg font-bold"
            style={{ color: rate >= 0.8 ? "#34d399" : rate >= 0.5 ? "#fbbf24" : "#f87171" }}
          >
            {Math.round(rate * 100)}%
            <span className="text-xs font-normal ml-1" style={{ color: "#64748b" }}>
              acceptance
            </span>
          </span>
        )}
      </div>

      {/* Stat pills */}
      <div className="flex gap-3 flex-wrap">
        <Stat label="Merged" value={stats.merged} color="#34d399" />
        <Stat label="In Review" value={stats.in_review} color="#fbbf24" />
        <Stat label="Rejected" value={stats.rejected} color="#f87171" />
        <Stat label="Failed" value={stats.failed} color="#64748b" />
      </div>

      {/* Cost & efficiency */}
      {(stats.avg_cost_usd !== null || stats.avg_turns !== null) && (
        <div className="flex gap-4 mt-3 pt-3" style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}>
          {stats.avg_cost_usd !== null && (
            <span className="text-xs" style={{ color: "#64748b" }}>
              Avg cost: <span style={{ color: "#a5b4fc" }}>${stats.avg_cost_usd.toFixed(2)}</span>
            </span>
          )}
          {stats.avg_turns !== null && (
            <span className="text-xs" style={{ color: "#64748b" }}>
              Avg turns: <span style={{ color: "#a5b4fc" }}>{stats.avg_turns}</span>
            </span>
          )}
          <span className="text-xs" style={{ color: "#64748b" }}>
            Total PRs: <span style={{ color: "#a5b4fc" }}>{total}</span>
          </span>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  if (value === 0) return null;
  return (
    <div
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full font-medium"
      style={{ background: `${color}10`, color, border: `1px solid ${color}30` }}
    >
      <span className="font-bold">{value}</span>
      {label}
    </div>
  );
}

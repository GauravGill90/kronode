"use client";

interface StatCardProps {
  label: string;
  value: number | string;
  sublabel?: string;
}

export default function StatCard({ label, value, sublabel }: StatCardProps) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-4 shadow-sm shadow-black/20">
      <p className="text-[10px] text-text-muted uppercase tracking-wider font-medium">{label}</p>
      <p className="text-2xl font-bold mt-1 text-brand">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {sublabel && <p className="text-xs text-text-muted mt-0.5">{sublabel}</p>}
    </div>
  );
}

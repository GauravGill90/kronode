"use client";

interface StatCardProps {
  label: string;
  value: number | string;
  sublabel?: string;
  color?: string; // tailwind color class for the accent
}

export default function StatCard({ label, value, sublabel, color = "indigo" }: StatCardProps) {
  const colorMap: Record<string, string> = {
    indigo: "border-indigo-500/20 bg-indigo-500/5",
    green: "border-emerald-500/20 bg-emerald-500/5",
    blue: "border-blue-500/20 bg-blue-500/5",
    amber: "border-amber-500/20 bg-amber-500/5",
    red: "border-red-500/20 bg-red-500/5",
    purple: "border-purple-500/20 bg-purple-500/5",
  };

  const valueColorMap: Record<string, string> = {
    indigo: "text-indigo-300",
    green: "text-emerald-300",
    blue: "text-blue-300",
    amber: "text-amber-300",
    red: "text-red-300",
    purple: "text-purple-300",
  };

  return (
    <div className={`rounded-xl border p-4 ${colorMap[color] || colorMap.indigo}`}>
      <p className="text-xs text-zinc-500 uppercase tracking-wider font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${valueColorMap[color] || valueColorMap.indigo}`}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {sublabel && <p className="text-xs text-zinc-500 mt-0.5">{sublabel}</p>}
    </div>
  );
}

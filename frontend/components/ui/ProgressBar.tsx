import { clsx } from "clsx";

interface ProgressBarProps {
  current: number;
  total: number;
  className?: string;
  showLabel?: boolean;
}

export function ProgressBar({ current, total, className, showLabel = true }: ProgressBarProps) {
  const pct = Math.round((current / total) * 100);
  return (
    <div className={clsx("space-y-1", className)}>
      {showLabel && (
        <div className="flex justify-between text-xs text-gray-500">
          <span>Step {current} of {total}</span>
          <span>{pct}%</span>
        </div>
      )}
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div
          className="bg-brand-500 h-1.5 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

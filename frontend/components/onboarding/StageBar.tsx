const STAGES = ["Hired", "Orientation", "Training", "Shadowing", "First Task", "Autonomy"];

interface StageBarProps {
  /** The highest stage that has been reached (1–6). */
  currentStage: number;
}

export default function StageBar({ currentStage }: StageBarProps) {
  return (
    <div className="flex items-start overflow-x-auto pb-1">
      {STAGES.map((stage, i) => {
        const stageNum = i + 1;
        const completed = stageNum <= currentStage;
        const active = stageNum === currentStage;

        return (
          <div key={stage} className="flex items-center">
            {/* Stage node */}
            <div className="flex flex-col items-center gap-1.5">
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300"
                style={
                  completed
                    ? {
                        background: "linear-gradient(135deg, #6366f1, #a78bfa)",
                        color: "#fff",
                        boxShadow: active
                          ? "0 0 14px rgba(99,102,241,0.55)"
                          : "none",
                      }
                    : {
                        background: "rgba(99,102,241,0.08)",
                        border: "1px solid rgba(99,102,241,0.15)",
                        color: "#334155",
                      }
                }
              >
                {completed ? "✓" : stageNum}
              </div>
              <span
                className="text-xs whitespace-nowrap"
                style={{ color: completed ? "#a5b4fc" : "#334155" }}
              >
                {stage}
              </span>
            </div>

            {/* Connector line */}
            {i < STAGES.length - 1 && (
              <div
                className="h-px w-10 flex-shrink-0 -mt-5 mx-1 transition-all duration-500"
                style={{
                  background:
                    stageNum < currentStage
                      ? "linear-gradient(90deg, #6366f1, #a78bfa)"
                      : "rgba(99,102,241,0.12)",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

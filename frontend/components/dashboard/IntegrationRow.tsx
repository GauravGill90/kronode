import type { IntegrationStatus } from "@/lib/types";

const INTEGRATIONS = [
  { key: "github", label: "GitHub" },
  { key: "jira", label: "Jira" },
  { key: "slack", label: "Slack" },
  { key: "docs", label: "Docs" },
] as const;

export default function IntegrationRow({ integrations }: { integrations: IntegrationStatus }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {INTEGRATIONS.map(({ key, label }) => {
        const connected = integrations[key];
        return (
          <span
            key={key}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border font-medium ${
              connected
                ? "bg-green-50 text-green-700 border-green-200"
                : "bg-gray-50 text-gray-400 border-gray-200"
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-500" : "bg-gray-300"}`}></span>
            {label}
          </span>
        );
      })}
    </div>
  );
}

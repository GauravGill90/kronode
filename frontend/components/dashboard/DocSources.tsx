"use client";

import { refreshAllIngestion } from "@/lib/api";
import { useState } from "react";

interface DocSource {
  source_type: string;
  source_count: number;
  chunk_count: number;
  last_updated: string | null;
}

interface Props {
  sources: DocSource[];
  totalChunks: number;
}

function sourceLabel(type: string): string {
  const labels: Record<string, string> = {
    git: "Git Markdown", bitbucket: "Bitbucket Markdown", confluence: "Confluence",
    notion: "Notion", gdrive: "Google Drive", gitlab: "GitLab Markdown",
  };
  return labels[type] || type;
}

export default function DocSources({ sources, totalChunks }: Props) {
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    try { await refreshAllIngestion(); } catch {}
    setTimeout(() => setRefreshing(false), 3000);
  }

  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Documentation Sources</h3>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-xs px-3 py-1 rounded-lg bg-surface-overlay hover:bg-surface-border-light text-text-secondary disabled:opacity-50 transition"
        >
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {sources.length === 0 ? (
        <p className="text-xs text-text-muted text-center py-4">
          No documentation ingested yet. Connect Confluence, Notion, or Google Drive.
        </p>
      ) : (
        <div className="space-y-2">
          {sources.map((src) => (
            <div key={src.source_type} className="flex items-center gap-3 py-2">
              <div className="w-7 h-7 rounded-lg bg-surface-overlay flex items-center justify-center text-xs font-bold text-text-secondary">
                {src.source_type[0].toUpperCase()}
              </div>
              <div className="flex-1">
                <p className="text-sm text-text-primary">{sourceLabel(src.source_type)}</p>
                <p className="text-xs text-text-muted">
                  {src.source_count} {src.source_count === 1 ? "page" : "pages"} / {src.chunk_count} chunks
                </p>
              </div>
            </div>
          ))}
          <div className="pt-2 border-t border-surface-border">
            <p className="text-xs text-text-muted">
              Total: {totalChunks} chunks across {sources.length} {sources.length === 1 ? "source" : "sources"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

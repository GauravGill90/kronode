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
    git: "Git Markdown",
    bitbucket: "Bitbucket Markdown",
    confluence: "Confluence",
    notion: "Notion",
    gdrive: "Google Drive",
    gitlab: "GitLab Markdown",
  };
  return labels[type] || type;
}

function sourceIcon(type: string): string {
  const icons: Record<string, string> = {
    git: "G",
    bitbucket: "B",
    confluence: "C",
    notion: "N",
    gdrive: "D",
    gitlab: "L",
  };
  return icons[type] || "?";
}

export default function DocSources({ sources, totalChunks }: Props) {
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshAllIngestion();
    } catch {}
    setTimeout(() => setRefreshing(false), 3000);
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
          Documentation Sources
        </h3>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-xs px-3 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 disabled:opacity-50"
        >
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {sources.length === 0 ? (
        <p className="text-xs text-zinc-600 text-center py-4">
          No documentation ingested yet. Connect Confluence, Notion, or Google Drive in settings.
        </p>
      ) : (
        <div className="space-y-2">
          {sources.map((src) => (
            <div key={src.source_type} className="flex items-center gap-3 py-2">
              <div className="w-7 h-7 rounded-lg bg-zinc-800 flex items-center justify-center text-xs font-bold text-zinc-400">
                {sourceIcon(src.source_type)}
              </div>
              <div className="flex-1">
                <p className="text-sm text-zinc-300">{sourceLabel(src.source_type)}</p>
                <p className="text-xs text-zinc-600">
                  {src.source_count} {src.source_count === 1 ? "page" : "pages"} / {src.chunk_count} chunks
                </p>
              </div>
            </div>
          ))}
          <div className="pt-2 border-t border-zinc-800">
            <p className="text-xs text-zinc-600">
              Total: {totalChunks} chunks across {sources.length} {sources.length === 1 ? "source" : "sources"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

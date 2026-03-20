"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import AppShell from "@/components/layout/AppShell";
import {
  getConventions,
  updateConvention,
  suppressConvention,
  triggerExtraction,
  triggerBaseExtraction,
  type Convention,
} from "@/lib/api";

const CATEGORIES = ["all", "architecture", "style", "naming", "error_handling", "testing", "logging"];
const LAYERS = ["all", "customer", "base"];

export default function ConventionsClient() {
  const { getToken } = useAuth();
  const [conventions, setConventions] = useState<Convention[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("all");
  const [layer, setLayer] = useState("all");
  const [page, setPage] = useState(1);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editRule, setEditRule] = useState("");
  const [extracting, setExtracting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const t = await getToken();
      if (t) (window as Window & { __clerkToken?: string }).__clerkToken = t;

      const params: Record<string, string | number> = { page };
      if (category !== "all") params.category = category;
      if (layer !== "all") params.layer = layer;

      const res = await getConventions(params);
      setConventions(res.data.conventions);
      setTotal(res.data.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, layer, page]);

  async function handleSuppress(id: number) {
    try {
      await suppressConvention(id);
      setConventions((prev) => prev.filter((c) => c.id !== id));
      setTotal((t) => t - 1);
    } catch {
      // ignore
    }
  }

  async function handleSaveEdit(id: number) {
    if (!editRule.trim()) return;
    try {
      await updateConvention(id, { rule: editRule.trim() });
      setConventions((prev) =>
        prev.map((c) => (c.id === id ? { ...c, rule: editRule.trim() } : c))
      );
      setEditingId(null);
    } catch {
      // ignore
    }
  }

  async function handleExtract() {
    setExtracting(true);
    try {
      await triggerExtraction();
    } catch {
      // ignore
    } finally {
      setExtracting(false);
    }
  }

  async function handleBaseExtract() {
    setExtracting(true);
    try {
      await triggerBaseExtraction();
    } catch {
      // ignore
    } finally {
      setExtracting(false);
    }
  }

  const confColor = (c: number) => {
    if (c >= 0.7) return "#34d399";
    if (c >= 0.4) return "#fbbf24";
    return "#f87171";
  };

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <a href="/dashboard" className="text-sm font-medium mb-2 inline-block" style={{ color: "#6366f1" }}>
              ← Back to dashboard
            </a>
            <h1 className="text-2xl font-bold" style={{ color: "#e2e8f0" }}>
              Conventions
            </h1>
            <p className="text-sm mt-1" style={{ color: "#64748b" }}>
              {total} conventions learned from your codebase. Edit or suppress any rule.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleExtract}
              disabled={extracting}
              className="px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc" }}
            >
              {extracting ? "Running…" : "Re-extract"}
            </button>
            <button
              onClick={handleBaseExtract}
              disabled={extracting}
              className="px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.3)", color: "#34d399" }}
            >
              {extracting ? "Running…" : "Extract base (Cal.com)"}
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-4 mb-6">
          <div className="flex gap-1">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => { setCategory(c); setPage(1); }}
                className="px-2.5 py-1 rounded-md text-xs font-medium capitalize"
                style={
                  category === c
                    ? { background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }
                    : { color: "#64748b" }
                }
              >
                {c.replace("_", " ")}
              </button>
            ))}
          </div>
          <div className="flex gap-1 ml-auto">
            {LAYERS.map((l) => (
              <button
                key={l}
                onClick={() => { setLayer(l); setPage(1); }}
                className="px-2.5 py-1 rounded-md text-xs font-medium capitalize"
                style={
                  layer === l
                    ? { background: "rgba(99,102,241,0.2)", color: "#a5b4fc" }
                    : { color: "#64748b" }
                }
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        {/* Convention list */}
        {loading ? (
          <p className="text-sm text-center py-12" style={{ color: "#475569" }}>Loading…</p>
        ) : conventions.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-sm" style={{ color: "#475569" }}>No conventions yet.</p>
            <p className="text-xs mt-1" style={{ color: "#334155" }}>
              Connect a repo and run extraction, or wait for PR reviews to accumulate them.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {conventions.map((c) => (
              <div
                key={c.id}
                className="rounded-xl p-4"
                style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    {editingId === c.id ? (
                      <div className="flex gap-2">
                        <input
                          className="flex-1 rounded-lg px-3 py-1.5 text-sm"
                          style={{
                            background: "rgba(255,255,255,0.04)",
                            border: "1px solid rgba(99,102,241,0.3)",
                            color: "#e2e8f0",
                            outline: "none",
                          }}
                          value={editRule}
                          onChange={(e) => setEditRule(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleSaveEdit(c.id)}
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveEdit(c.id)}
                          className="px-2 py-1 rounded text-xs"
                          style={{ color: "#34d399" }}
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="px-2 py-1 rounded text-xs"
                          style={{ color: "#64748b" }}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <p className="text-sm" style={{ color: "#e2e8f0" }}>{c.rule}</p>
                    )}

                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      <span
                        className="text-xs px-2 py-0.5 rounded-full capitalize"
                        style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc" }}
                      >
                        {c.category.replace("_", " ")}
                      </span>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full"
                        style={{
                          background: c.layer === "base" ? "rgba(52,211,153,0.1)" : "rgba(251,191,36,0.1)",
                          color: c.layer === "base" ? "#34d399" : "#fbbf24",
                        }}
                      >
                        {c.layer}
                      </span>
                      <span className="text-xs" style={{ color: "#475569" }}>
                        freq: {c.frequency}
                      </span>
                      <span className="text-xs" style={{ color: confColor(c.confidence) }}>
                        conf: {c.confidence.toFixed(2)}
                      </span>
                      {c.enforced_by && c.enforced_by.length > 0 && (
                        <span className="text-xs" style={{ color: "#64748b" }}>
                          enforced by: {c.enforced_by.join(", ")}
                        </span>
                      )}
                      {c.source_prs && c.source_prs.length > 0 && (
                        <a
                          href={c.source_prs[0]}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs"
                          style={{ color: "#6366f1" }}
                        >
                          source PR
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-1 flex-shrink-0">
                    <button
                      onClick={() => { setEditingId(c.id); setEditRule(c.rule); }}
                      className="p-1.5 rounded-md text-xs"
                      style={{ color: "#64748b" }}
                      title="Edit"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleSuppress(c.id)}
                      className="p-1.5 rounded-md text-xs"
                      style={{ color: "#f87171" }}
                      title="Suppress — never inject again"
                    >
                      Suppress
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {total > 50 && (
          <div className="flex justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 rounded-lg text-xs"
              style={{ color: page === 1 ? "#334155" : "#a5b4fc" }}
            >
              ← Prev
            </button>
            <span className="text-xs py-1.5" style={{ color: "#64748b" }}>
              Page {page} of {Math.ceil(total / 50)}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= Math.ceil(total / 50)}
              className="px-3 py-1.5 rounded-lg text-xs"
              style={{ color: page >= Math.ceil(total / 50) ? "#334155" : "#a5b4fc" }}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}

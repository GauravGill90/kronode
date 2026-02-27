"use client";

import { useState, useEffect } from "react";
import { getJiraTickets } from "@/lib/api";
import type { JiraTicket } from "@/lib/api";

const PRIORITY_COLOR: Record<string, string> = {
  Highest: "#f87171",
  High: "#fb923c",
  Medium: "#fbbf24",
  Low: "#34d399",
  Lowest: "#94a3b8",
};

const STATUS_COLOR: Record<string, string> = {
  "blue-grey": "#64748b",
  blue: "#60a5fa",
  yellow: "#fbbf24",
  green: "#34d399",
};

interface Props {
  onSelect: (ticket: JiraTicket) => void;
}

export default function JiraTickets({ onSelect }: Props) {
  const [tickets, setTickets] = useState<JiraTicket[]>([]);
  const [configured, setConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    getJiraTickets()
      .then((res) => {
        setTickets(res.data.tickets);
        setConfigured(res.data.configured);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (!configured || loading) return null;
  if (tickets.length === 0) return null;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(99,102,241,0.12)" }}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3"
        style={{ borderBottom: expanded ? "1px solid rgba(99,102,241,0.1)" : "none" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium" style={{ color: "#94a3b8" }}>
            Jira backlog
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded-full"
            style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc" }}
          >
            {tickets.length}
          </span>
        </div>
        <span className="text-xs" style={{ color: "#475569" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {/* Ticket list */}
      {expanded && (
        <ul className="divide-y" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
          {tickets.map((ticket) => {
            const statusColor = STATUS_COLOR[ticket.status_category] || "#64748b";
            const priorityColor = PRIORITY_COLOR[ticket.priority || ""] || "#64748b";

            return (
              <li key={ticket.id}>
                <button
                  type="button"
                  onClick={() => onSelect(ticket)}
                  className="w-full text-left px-5 py-3 transition-colors group"
                  style={{ background: "transparent" }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "rgba(99,102,241,0.06)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className="text-xs font-mono font-semibold flex-shrink-0"
                          style={{ color: "#6366f1" }}
                        >
                          {ticket.id}
                        </span>
                        <span
                          className="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
                          style={{ background: `${statusColor}18`, color: statusColor, border: `1px solid ${statusColor}30` }}
                        >
                          {ticket.status}
                        </span>
                        {ticket.priority && (
                          <span className="text-xs flex-shrink-0" style={{ color: priorityColor }}>
                            ● {ticket.priority}
                          </span>
                        )}
                      </div>
                      <p
                        className="text-sm mt-1 truncate"
                        style={{ color: "#e2e8f0" }}
                      >
                        {ticket.summary}
                      </p>
                      {ticket.assignee && (
                        <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
                          {ticket.assignee}
                        </p>
                      )}
                    </div>
                    <span
                      className="text-xs flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity mt-1"
                      style={{ color: "#a5b4fc" }}
                    >
                      Assign →
                    </span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { colors, gradients } from "@/tokens/colors";
import { getOnboardingConfig } from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";
import ConfluenceForm from "@/components/onboarding/ConfluenceForm";

// ── card types ────────────────────────────────────────────────────────────────

interface OnboardingCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  connected: boolean;
  optional?: boolean;
  action: () => void;
}

export default function OnboardingDashboard() {
  const store = useOnboardingStore();
  const [showConfluenceForm, setShowConfluenceForm] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  // Hydrate store from API on mount
  useEffect(() => {
    getOnboardingConfig()
      .then((config) => {
        store.hydrateFromApi(config);
        setHydrated(true);
      })
      .catch(() => {
        // Proceed without hydration — not fatal
        setHydrated(true);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cards: OnboardingCard[] = [
    {
      id: "github",
      title: "Connect GitHub",
      description: "Kronode needs access to your repositories to read code and open pull requests.",
      icon: "🐙",
      connected: !!store.repoUrl,
      action: () => {},
    },
    {
      id: "jira",
      title: "Connect Jira",
      description: "Kronode reads your Jira board to pick up tickets and update their status.",
      icon: "📋",
      connected: !!store.jiraProjectKey,
      action: () => {},
    },
    {
      id: "slack",
      title: "Connect Slack",
      description: "Kronode communicates in Slack — standups, plan previews, and questions.",
      icon: "💬",
      connected: !!store.slackChannelId,
      action: () => {},
    },
    {
      id: "confluence",
      title: "Connect Confluence",
      description:
        "Kronode learns from your ADRs, conventions, and domain glossaries in Confluence.",
      icon: "📚",
      connected: !!store.confluenceBaseUrl,
      optional: true,
      action: () => setShowConfluenceForm(true),
    },
  ];

  if (!hydrated) {
    return (
      <div className="flex items-center justify-center py-20">
        <span style={{ color: colors.text.muted }} className="text-sm">
          Loading…
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <div>
        <h1
          className="text-2xl font-bold"
          style={{
            background: gradients.brandText,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          Set up Kronode
        </h1>
        <p className="text-sm mt-1" style={{ color: colors.text.secondary }}>
          Connect your tools so Kronode can start learning your codebase and
          workflows.
        </p>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {cards.map((card) => (
          <button
            key={card.id}
            onClick={card.action}
            className="text-left rounded-2xl p-5 transition-colors"
            style={{
              background: card.connected
                ? colors.status.successBg
                : colors.bg.surface,
              border: `1px solid ${
                card.connected
                  ? colors.status.successBorder
                  : colors.border.default
              }`,
            }}
          >
            <div className="flex items-start gap-3">
              <span className="text-2xl">{card.icon}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3
                    className="font-semibold text-sm"
                    style={{ color: colors.text.primary }}
                  >
                    {card.title}
                  </h3>
                  {card.optional && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        background: colors.status.infoBg,
                        color: colors.status.info,
                        border: `1px solid ${colors.status.infoBorder}`,
                      }}
                    >
                      optional
                    </span>
                  )}
                  {card.connected && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        background: colors.status.successBg,
                        color: colors.status.success,
                        border: `1px solid ${colors.status.successBorder}`,
                      }}
                    >
                      ✓ Connected
                    </span>
                  )}
                </div>
                <p
                  className="text-xs mt-1 leading-relaxed"
                  style={{ color: colors.text.secondary }}
                >
                  {card.description}
                </p>
                {card.id === "confluence" && store.confluenceBaseUrl && (
                  <p
                    className="text-xs mt-1"
                    style={{ color: colors.text.muted }}
                  >
                    {store.confluenceSpaceKeys.join(", ")}{" "}
                    {store.confluenceIncludeLabels.length > 0 &&
                      `· labels: ${store.confluenceIncludeLabels.join(", ")}`}
                  </p>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Confluence form modal */}
      {showConfluenceForm && (
        <ConfluenceForm
          onClose={() => setShowConfluenceForm(false)}
          onSaved={() => setShowConfluenceForm(false)}
        />
      )}
    </div>
  );
}

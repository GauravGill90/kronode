"use client";

import { useState, KeyboardEvent } from "react";
import { colors, gradients } from "@/tokens/colors";
import {
  saveConfluenceConfig,
  testConfluenceConnection,
  ConfluenceTestResult,
} from "@/lib/api";
import { useOnboardingStore } from "@/lib/store";

interface Props {
  onClose: () => void;
  onSaved: () => void;
}

export default function ConfluenceForm({ onClose, onSaved }: Props) {
  const { confluenceBaseUrl, confluenceSpaceKeys, confluenceIncludeLabels, setConfluenceConfig } =
    useOnboardingStore();

  const [baseUrl, setBaseUrl] = useState(confluenceBaseUrl ?? "");
  const [spaceKeys, setSpaceKeys] = useState<string[]>(confluenceSpaceKeys ?? []);
  const [spaceInput, setSpaceInput] = useState("");
  const [labels, setLabels] = useState<string[]>(confluenceIncludeLabels ?? []);
  const [labelInput, setLabelInput] = useState("");

  const [testResult, setTestResult] = useState<ConfluenceTestResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<{
    baseUrl?: string;
    spaceKeys?: string;
  }>({});

  // ── tag helpers ────────────────────────────────────────────────────────────

  function addSpaceKey(raw: string) {
    const key = raw.trim().toUpperCase();
    if (key && !spaceKeys.includes(key)) {
      setSpaceKeys((prev) => [...prev, key]);
    }
    setSpaceInput("");
  }

  function removeSpaceKey(key: string) {
    setSpaceKeys((prev) => prev.filter((k) => k !== key));
  }

  function addLabel(raw: string) {
    const lbl = raw.trim().toLowerCase();
    if (lbl && !labels.includes(lbl)) {
      setLabels((prev) => [...prev, lbl]);
    }
    setLabelInput("");
  }

  function removeLabel(lbl: string) {
    setLabels((prev) => prev.filter((l) => l !== lbl));
  }

  function handleSpaceKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === "," || e.key === " ") {
      e.preventDefault();
      addSpaceKey(spaceInput);
    }
  }

  function handleLabelKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addLabel(labelInput);
    }
  }

  // ── validation ─────────────────────────────────────────────────────────────

  function validate(): boolean {
    const errors: { baseUrl?: string; spaceKeys?: string } = {};
    if (!baseUrl.trim()) {
      errors.baseUrl = "Confluence base URL is required.";
    }
    if (spaceKeys.length === 0) {
      errors.spaceKeys = "At least one space key is required.";
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }

  // ── test connection ────────────────────────────────────────────────────────

  async function handleTest() {
    if (!validate()) return;
    setTesting(true);
    setTestResult(null);
    setTestError(null);
    try {
      const result = await testConfluenceConnection({
        base_url: baseUrl.trim(),
        space_keys: spaceKeys,
        include_labels: labels,
      });
      setTestResult(result);
    } catch (err: unknown) {
      setTestError(
        err instanceof Error ? err.message : "Connection test failed."
      );
    } finally {
      setTesting(false);
    }
  }

  // ── save ──────────────────────────────────────────────────────────────────

  async function handleSave() {
    if (!validate()) return;
    setSaving(true);
    setSaveError(null);
    try {
      await saveConfluenceConfig({
        base_url: baseUrl.trim(),
        space_keys: spaceKeys,
        include_labels: labels,
      });
      setConfluenceConfig(baseUrl.trim(), spaceKeys, labels);
      onSaved();
    } catch (err: unknown) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to save configuration."
      );
    } finally {
      setSaving(false);
    }
  }

  // ── render ────────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: colors.bg.overlay }}
    >
      <div
        className="w-full max-w-lg rounded-2xl p-6 space-y-5"
        style={{
          background: "#0f0f1a",
          border: `1px solid ${colors.border.default}`,
          boxShadow: `0 0 60px ${colors.glow.primaryFaint}`,
        }}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2
              className="text-lg font-semibold"
              style={{ color: colors.text.primary }}
            >
              Connect Confluence
            </h2>
            <p className="text-xs mt-1" style={{ color: colors.text.muted }}>
              Let Kronode learn from your team&apos;s documentation.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-xl leading-none"
            style={{ color: colors.text.muted }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Base URL */}
        <div className="space-y-1">
          <label
            className="text-xs font-medium"
            style={{ color: colors.text.secondary }}
          >
            Confluence base URL <span style={{ color: colors.status.error }}>*</span>
          </label>
          <input
            type="url"
            placeholder="https://acme.atlassian.net/wiki"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={{
              background: colors.bg.surface,
              border: `1px solid ${
                validationErrors.baseUrl
                  ? colors.status.errorBorder
                  : colors.border.subtle
              }`,
              color: colors.text.primary,
            }}
          />
          {validationErrors.baseUrl && (
            <p className="text-xs" style={{ color: colors.status.error }}>
              {validationErrors.baseUrl}
            </p>
          )}
        </div>

        {/* Space keys */}
        <div className="space-y-1">
          <label
            className="text-xs font-medium"
            style={{ color: colors.text.secondary }}
          >
            Spaces to learn from <span style={{ color: colors.status.error }}>*</span>
          </label>
          <div
            className="flex flex-wrap gap-1.5 rounded-lg px-3 py-2 min-h-[40px]"
            style={{
              background: colors.bg.surface,
              border: `1px solid ${
                validationErrors.spaceKeys
                  ? colors.status.errorBorder
                  : colors.border.subtle
              }`,
            }}
          >
            {spaceKeys.map((k) => (
              <span
                key={k}
                className="flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium"
                style={{
                  background: colors.glow.primarySoft,
                  color: colors.brand.primary,
                  border: `1px solid ${colors.border.default}`,
                }}
              >
                {k}
                <button
                  onClick={() => removeSpaceKey(k)}
                  className="leading-none"
                  style={{ color: colors.text.muted }}
                  aria-label={`Remove space ${k}`}
                >
                  ✕
                </button>
              </span>
            ))}
            <input
              type="text"
              placeholder={spaceKeys.length === 0 ? "ENG, ARCH, PRODUCT…" : "+ Add space"}
              value={spaceInput}
              onChange={(e) => setSpaceInput(e.target.value)}
              onKeyDown={handleSpaceKeyDown}
              onBlur={() => spaceInput && addSpaceKey(spaceInput)}
              className="flex-1 min-w-[100px] bg-transparent text-sm outline-none"
              style={{ color: colors.text.primary }}
            />
          </div>
          <p className="text-xs" style={{ color: colors.text.muted }}>
            Press Enter or Space to add a space key.
          </p>
          {validationErrors.spaceKeys && (
            <p className="text-xs" style={{ color: colors.status.error }}>
              {validationErrors.spaceKeys}
            </p>
          )}
        </div>

        {/* Label filter (optional) */}
        <div className="space-y-1">
          <label
            className="text-xs font-medium"
            style={{ color: colors.text.secondary }}
          >
            Only pages labelled{" "}
            <span style={{ color: colors.text.muted }}>(optional)</span>
          </label>
          <div
            className="flex flex-wrap gap-1.5 rounded-lg px-3 py-2 min-h-[40px]"
            style={{
              background: colors.bg.surface,
              border: `1px solid ${colors.border.subtle}`,
            }}
          >
            {labels.map((lbl) => (
              <span
                key={lbl}
                className="flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium"
                style={{
                  background: colors.status.infoBg,
                  color: colors.status.info,
                  border: `1px solid ${colors.status.infoBorder}`,
                }}
              >
                {lbl}
                <button
                  onClick={() => removeLabel(lbl)}
                  className="leading-none"
                  style={{ color: colors.text.muted }}
                  aria-label={`Remove label ${lbl}`}
                >
                  ✕
                </button>
              </span>
            ))}
            <input
              type="text"
              placeholder={
                labels.length === 0 ? "agent-context, adr…" : "+ Add label"
              }
              value={labelInput}
              onChange={(e) => setLabelInput(e.target.value)}
              onKeyDown={handleLabelKeyDown}
              onBlur={() => labelInput && addLabel(labelInput)}
              className="flex-1 min-w-[100px] bg-transparent text-sm outline-none"
              style={{ color: colors.text.primary }}
            />
          </div>
          <p className="text-xs" style={{ color: colors.text.muted }}>
            Leave empty to include all pages in the selected spaces.
          </p>
        </div>

        {/* Test result / error */}
        {testResult && (
          <div
            className="rounded-lg px-4 py-3 text-sm"
            style={{
              background: colors.status.successBg,
              border: `1px solid ${colors.status.successBorder}`,
              color: colors.status.success,
            }}
          >
            <span className="font-semibold">✓ Connected</span> —{" "}
            {testResult.spaces
              .map((s) => `${s.name} (${s.page_count} pages)`)
              .join(", ")}
          </div>
        )}
        {testError && (
          <div
            className="rounded-lg px-4 py-3 text-sm"
            style={{
              background: colors.status.errorBg,
              border: `1px solid ${colors.status.errorBorder}`,
              color: colors.status.error,
            }}
          >
            {testError}
          </div>
        )}
        {saveError && (
          <div
            className="rounded-lg px-4 py-3 text-sm"
            style={{
              background: colors.status.errorBg,
              border: `1px solid ${colors.status.errorBorder}`,
              color: colors.status.error,
            }}
          >
            {saveError}
          </div>
        )}

        {/* Helper message */}
        <div
          className="rounded-lg px-4 py-3 text-xs leading-relaxed"
          style={{
            background: colors.status.infoBg,
            border: `1px solid ${colors.status.infoBorder}`,
            color: colors.status.info,
          }}
        >
          ℹ Kronode will read these spaces daily to learn your team&apos;s
          conventions, decisions, and domain language. It{" "}
          <strong>never writes</strong> to Confluence.
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between gap-3 pt-1">
          <button
            onClick={handleTest}
            disabled={testing}
            className="rounded-lg px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-50"
            style={{
              background: colors.bg.surfaceHover,
              border: `1px solid ${colors.border.default}`,
              color: colors.text.secondary,
            }}
          >
            {testing ? "Testing…" : "Test Connection"}
          </button>

          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-medium"
              style={{
                background: "transparent",
                color: colors.text.muted,
              }}
            >
              Skip
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg px-4 py-2 text-sm font-semibold transition-opacity disabled:opacity-50"
              style={{
                background: gradients.brandLogo,
                color: colors.text.white,
              }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

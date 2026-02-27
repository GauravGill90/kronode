/**
 * Kronode Design System — Color Tokens
 *
 * All color values used across the application must be imported from here.
 * Never use raw hex or rgba values directly in components.
 */

export const colors = {
  // ─── Brand ───────────────────────────────────────────────────────────────
  brand: {
    primary: "#6366f1",       // indigo-500  — primary accent
    secondary: "#a78bfa",     // violet-400  — secondary accent
    sky: "#38bdf8",           // sky-400     — tertiary accent
  },

  // ─── Background ──────────────────────────────────────────────────────────
  bg: {
    base: "#080810",          // deepest background
    surface: "rgba(255,255,255,0.03)",   // card / tile surface
    surfaceHover: "rgba(255,255,255,0.05)",
    overlay: "rgba(0,0,0,0.4)",
  },

  // ─── Border ──────────────────────────────────────────────────────────────
  border: {
    subtle: "rgba(99,102,241,0.12)",
    default: "rgba(99,102,241,0.2)",
    strong: "rgba(99,102,241,0.4)",
    muted: "rgba(255,255,255,0.08)",
  },

  // ─── Text ────────────────────────────────────────────────────────────────
  text: {
    primary: "#e2e8f0",       // slate-200
    secondary: "#94a3b8",     // slate-400
    muted: "#64748b",         // slate-500
    accent: "#6366f1",        // same as brand.primary
    white: "#ffffff",
  },

  // ─── Status ──────────────────────────────────────────────────────────────
  status: {
    success: "#22c55e",       // green-500
    successBg: "rgba(34,197,94,0.15)",
    successBorder: "rgba(34,197,94,0.3)",

    warning: "#f59e0b",       // amber-500
    warningBg: "rgba(245,158,11,0.15)",
    warningBorder: "rgba(245,158,11,0.3)",

    error: "#ef4444",         // red-500
    errorBg: "rgba(239,68,68,0.15)",
    errorBorder: "rgba(239,68,68,0.3)",

    info: "#38bdf8",          // sky-400
    infoBg: "rgba(56,189,248,0.15)",
    infoBorder: "rgba(56,189,248,0.3)",
  },

  // ─── Glow / Ambient ──────────────────────────────────────────────────────
  glow: {
    primary: "rgba(99,102,241,0.4)",
    primarySoft: "rgba(99,102,241,0.15)",
    primaryFaint: "rgba(99,102,241,0.08)",
    primaryGrid: "rgba(99,102,241,0.04)",
    secondary: "rgba(167,139,250,0.08)",
    sky: "rgba(56,189,248,0.08)",
  },
} as const;

// ─── Gradient helpers ────────────────────────────────────────────────────────
export const gradients = {
  brandLogo: `linear-gradient(135deg, ${colors.brand.primary}, ${colors.brand.secondary})`,
  brandText: `linear-gradient(135deg, ${colors.text.primary} 0%, #a5b4fc 100%)`,
  brandAccent: `linear-gradient(90deg, ${colors.brand.secondary}, ${colors.brand.sky})`,
  glowTop: `radial-gradient(ellipse, ${colors.glow.primarySoft} 0%, transparent 70%)`,
  glowBottomLeft: `radial-gradient(ellipse, ${colors.glow.secondary} 0%, transparent 70%)`,
  glowBottomRight: `radial-gradient(ellipse, ${colors.glow.sky} 0%, transparent 70%)`,
  gridOverlay: `linear-gradient(${colors.glow.primaryGrid} 1px, transparent 1px), linear-gradient(90deg, ${colors.glow.primaryGrid} 1px, transparent 1px)`,
} as const;

export type ColorToken = typeof colors;
export type GradientToken = typeof gradients;

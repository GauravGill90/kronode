/**
 * Kronode Design System — Color Tokens (Warm Gold Theme)
 */

export const colors = {
  brand: {
    primary: "#d4a853",
    secondary: "#e4c37d",
    tertiary: "#b07f2e",
  },

  bg: {
    base: "#1c1917",
    surface: "rgba(255,255,255,0.02)",
    surfaceHover: "rgba(255,255,255,0.04)",
    overlay: "rgba(0,0,0,0.4)",
    raised: "#231f1d",
  },

  border: {
    subtle: "rgba(212,168,83,0.1)",
    default: "rgba(212,168,83,0.2)",
    strong: "rgba(212,168,83,0.4)",
    muted: "rgba(255,255,255,0.06)",
  },

  text: {
    primary: "#e7e0d8",
    secondary: "#a39e96",
    muted: "#6b6560",
    accent: "#d4a853",
    white: "#ffffff",
  },

  status: {
    success: "#4ade80",
    successBg: "rgba(74,222,128,0.1)",
    successBorder: "rgba(74,222,128,0.25)",
    warning: "#fbbf24",
    warningBg: "rgba(251,191,36,0.1)",
    warningBorder: "rgba(251,191,36,0.25)",
    error: "#f87171",
    errorBg: "rgba(248,113,113,0.1)",
    errorBorder: "rgba(248,113,113,0.25)",
    info: "#60a5fa",
    infoBg: "rgba(96,165,250,0.1)",
    infoBorder: "rgba(96,165,250,0.25)",
  },

  glow: {
    primary: "rgba(212,168,83,0.3)",
    primarySoft: "rgba(212,168,83,0.12)",
    primaryFaint: "rgba(212,168,83,0.06)",
    primaryGrid: "rgba(212,168,83,0.03)",
    secondary: "rgba(228,195,125,0.06)",
    warm: "rgba(176,127,46,0.06)",
  },
} as const;

export const gradients = {
  brandLogo: colors.brand.primary,
  brandText: `linear-gradient(135deg, ${colors.text.primary} 0%, ${colors.brand.secondary} 100%)`,
  brandAccent: `linear-gradient(90deg, ${colors.brand.primary}, ${colors.brand.secondary})`,
  glowTop: `radial-gradient(ellipse, ${colors.glow.primarySoft} 0%, transparent 70%)`,
  glowBottomLeft: `radial-gradient(ellipse, ${colors.glow.secondary} 0%, transparent 70%)`,
  glowBottomRight: `radial-gradient(ellipse, ${colors.glow.warm} 0%, transparent 70%)`,
  gridOverlay: `linear-gradient(${colors.glow.primaryGrid} 1px, transparent 1px), linear-gradient(90deg, ${colors.glow.primaryGrid} 1px, transparent 1px)`,
} as const;

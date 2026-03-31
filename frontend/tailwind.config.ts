import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Warm dark base
        surface: {
          DEFAULT: "#1c1917",
          raised: "#231f1d",
          overlay: "#2a2623",
          border: "#2e2a27",
          "border-light": "#3a3530",
        },
        // Warm gold brand
        brand: {
          50: "#fdf8ef",
          100: "#f9efd9",
          200: "#f0dbb0",
          300: "#e4c37d",
          400: "#d4a853",
          DEFAULT: "#d4a853",
          500: "#c99a3e",
          600: "#b07f2e",
          700: "#8f6425",
          800: "#6b4c1f",
          900: "#4a351b",
        },
        // Text colors
        text: {
          primary: "#e7e0d8",
          secondary: "#a39e96",
          muted: "#6b6560",
          inverse: "#1c1917",
        },
        // Status colors
        status: {
          success: "#4ade80",
          warning: "#fbbf24",
          error: "#f87171",
          info: "#60a5fa",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

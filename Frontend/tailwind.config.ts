import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design System - Bioluminescent / Frozen Light
        "surface-container-lowest": "#0c0e12",
        secondary: "#94a3b8", // Muted slate
        "tertiary-fixed-dim": "#7dd3fc", // Ice blue
        "on-secondary-fixed-variant": "#475569",
        "on-surface-variant": "#94a3b8",
        "error-container": "#450a0a",
        primary: "#e2e8f0",
        "secondary-fixed": "#cbd5e1",
        tertiary: "#7dd3fc", // Glacier ice blue
        "surface-tint": "#7dd3fc",
        "surface-container-low": "#191c1f",
        "primary-container": "#1e293b",
        "on-primary": "#0f172a",
        "on-background": "#f8fafc",
        surface: "#111417",
        "inverse-on-surface": "#0f172a",
        outline: "#475569",
        "on-secondary-container": "#e2e8f0",
        "on-tertiary-fixed": "#082f49",
        "tertiary-container": "#0c4a6e",
        "on-secondary": "#1e293b",
        "primary-fixed-dim": "#cbd5e1",
        "surface-container-high": "#23282e",
        "on-error": "#fef2f2",
        "on-primary-fixed-variant": "#334155",
        "on-primary-container": "#94a3b8",
        "primary-fixed": "#f1f5f9",
        "on-tertiary-container": "#bae6fd",
        "surface-variant": "#1e293b",
        "surface-dim": "#111417",
        "on-tertiary": "#082f49",
        "on-primary-fixed": "#0f172a",
        "secondary-container": "#334155",
        "surface-bright": "#37393d",
        "inverse-primary": "#64748b",
        "secondary-fixed-dim": "#94a3b8",
        "on-surface": "#f8fafc",
        "on-secondary-fixed": "#0f172a",
        "inverse-surface": "#f8fafc",
        "on-error-container": "#fca5a5",
        "surface-container": "#1d2126",
        "tertiary-fixed": "#bae6fd",
        "outline-variant": "#334155",
        background: "#0c0e12",
        "on-tertiary-fixed-variant": "#075985",
        error: "#f87171",
        "surface-container-highest": "#2d3239",
        // Kept for backward compatibility
        risk: "#FF7A59",
        "brand-teal": "#3FE0B0",
        "brand-lavender": "#c8c2e4",
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem",
      },
      spacing: {
        gutter: "24px",
        "margin-mobile": "16px",
        "margin-desktop": "40px",
        unit: "8px",
        "stack-md": "16px",
        "stack-lg": "32px",
        "stack-sm": "8px",
        base: "4px",
      },
      maxWidth: {
        container: "1440px",
      },
      fontFamily: {
        sora: ["var(--font-sora)", "sans-serif"],
        literata: ["var(--font-literata)", "serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
        // New fonts
        "label-sm": ["JetBrains Mono", "monospace"],
        "body-md": ["Space Grotesk", "sans-serif"],
        "headline-lg": ["Space Grotesk", "sans-serif"],
        "data-mono": ["JetBrains Mono", "monospace"],
        "headline-xl": ["Space Grotesk", "sans-serif"],
      },
      fontSize: {
        "display-lg": ["48px", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
        "headline-lg": ["32px", { lineHeight: "1.2", fontWeight: "600" }],
        "headline-md": ["24px", { lineHeight: "1.3", fontWeight: "600" }],
        "score-display": ["20px", { lineHeight: "1.0", fontWeight: "700" }],
        "body-lg": ["18px", { lineHeight: "1.6", fontWeight: "400" }],
        "body-md": ["16px", { lineHeight: "1.6", fontWeight: "400" }],
        "label-mono": ["14px", { lineHeight: "1.0", letterSpacing: "0.05em", fontWeight: "500" }],
        // New font sizes
        "label-sm": ["12px", { lineHeight: "1.2", fontWeight: "500" }],
        "data-mono": ["14px", { lineHeight: "1.5", letterSpacing: "0.05em", fontWeight: "300" }],
        "headline-xl": ["48px", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
      },
      animation: {
        "liquid-sweep": "liquid-sweep 3s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "pulse-soft": "pulse-soft 4s ease-in-out infinite",
      },
      keyframes: {
        "liquid-sweep": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-20px)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "0.4", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.1)" },
        },
      },
      boxShadow: {
        glow: "0 0 20px rgba(63, 224, 176, 0.3)",
        "glow-lg": "0 0 40px rgba(63, 224, 176, 0.5)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;

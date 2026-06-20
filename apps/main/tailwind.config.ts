import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary:        "var(--color-brand-primary)",
          "primary-hover":"var(--color-brand-primary-hover)",
          accent:         "var(--color-brand-accent)",
        },
        surface: {
          bg:          "var(--color-surface-bg)",
          card:        "var(--color-surface-card)",
          overlay:     "var(--color-surface-overlay)",
          destructive: "var(--color-surface-destructive)",
        },
        content: {
          primary:     "var(--color-text-primary)",
          secondary:   "var(--color-text-secondary)",
          muted:       "var(--color-text-muted)",
          inverse:     "var(--color-text-inverse)",
          destructive: "var(--color-text-destructive)",
        },
        border: {
          default: "var(--color-border-default)",
          focus:   "var(--color-border-focus)",
        },
        status: {
          scheduled:          "var(--color-status-scheduled)",
          "in-progress":      "var(--color-status-in-progress)",
          completed:          "var(--color-status-completed)",
          cancelled:          "var(--color-status-cancelled)",
          "scheduled-bg":     "var(--color-status-scheduled-bg)",
          "in-progress-bg":   "var(--color-status-in-progress-bg)",
          "completed-bg":     "var(--color-status-completed-bg)",
          "cancelled-bg":     "var(--color-status-cancelled-bg)",
        },
      },
      fontSize: {
        h1:        ["1.875rem", { lineHeight: "1.2", fontWeight: "700" }],
        h2:        ["1.5rem",   { lineHeight: "1.3", fontWeight: "700" }],
        h3:        ["1.25rem",  { lineHeight: "1.3", fontWeight: "600" }],
        body:      ["1rem",     { lineHeight: "1.5", fontWeight: "400" }],
        "body-sm": ["0.875rem", { lineHeight: "1.5", fontWeight: "400" }],
        caption:   ["0.75rem",  { lineHeight: "1.4", fontWeight: "400" }],
        label:     ["0.875rem", { lineHeight: "1",   fontWeight: "500" }],
      },
    },
  },
  plugins: [],
};

export default config;

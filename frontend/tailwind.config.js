export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: { extend: { colors: {
    "surface-ground": "var(--surface-ground)",
    "surface-card": "var(--surface-card)",
    "surface-border": "var(--surface-border)",
    "surface-hover": "var(--surface-hover)",
    "color": "var(--text-color)",
    "color-secondary": "var(--text-color-secondary)",
    "primary": "var(--primary-color)",
  } } },
  plugins: [],
};

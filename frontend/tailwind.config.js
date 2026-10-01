/** PRISM design tokens — near-monochrome + one accent (#5E6AD2).
 *  See docs/DESIGN-RULES.md: no gradients, no glassmorphism, no emoji icons. */
const config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#08090A",
        surface: "#101214",
        elevated: "#1A1D21",
        accent: "#5E6AD2",
        "accent-dim": "#3D4496",
        ink: "#E8EAED",
        "ink-dim": "#9AA0A6",
        "ink-faint": "#5F6368",
        line: "rgba(255, 255, 255, 0.07)",
        ok: "#34A853",
        warn: "#FBBC04",
        danger: "#EA4335",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: ["11px", "16px"],
        sm: ["12px", "18px"],
        base: ["13px", "20px"],
        lg: ["14px", "22px"],
      },
    },
  },
  plugins: [],
};

module.exports = config;

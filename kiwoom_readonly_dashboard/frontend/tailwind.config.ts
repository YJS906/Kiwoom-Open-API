import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./types/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: "#090c10",
        panel: "#10161f",
        panelMuted: "#141d28",
        border: "#243143",
        text: "#e5edf8",
        muted: "#95a6bd",
        accent: "#3b82f6",
        success: "#22c55e",
        danger: "#ef4444",
        warning: "#f59e0b"
      },
      boxShadow: {
        soft: "0 20px 60px rgba(0, 0, 0, 0.35)"
      },
      fontFamily: {
        sans: ["Pretendard", "Segoe UI", "sans-serif"]
      }
    }
  },
  plugins: []
};

export default config;

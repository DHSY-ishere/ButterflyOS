import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#060814",
        card: "#0D111C",
        neon: "#7CC4FF", // azure accent
        crimson: "#FF5D8F", // rose / danger
        emerald: "#42F5C2", // mint / healed
        amber: "#FFC46B",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;

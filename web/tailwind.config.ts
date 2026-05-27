import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Source Serif 4"', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        ink: "#1a1a1a",
        paper: "#fbfaf6",
        rule: "#e4e0d6",
        accent: "#b4513a",
      },
    },
  },
  plugins: [],
} satisfies Config;

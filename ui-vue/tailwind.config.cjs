/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#2563eb",
        "primary-dark": "#1d4ed8",
        surface: "#ffffff",
        subtle: "#f8fafc",
        "surface-muted": "#f1f5f9",
      },
      fontFamily: {
        display: ["Segoe UI", "Microsoft YaHei", "PingFang SC", "Arial", "sans-serif"],
        body: ["Segoe UI", "Microsoft YaHei", "PingFang SC", "Arial", "sans-serif"],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        soft: "0 4px 20px -2px rgba(0, 0, 0, 0.05)",
        glow: "0 0 20px -5px rgba(37, 99, 235, 0.15)",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};

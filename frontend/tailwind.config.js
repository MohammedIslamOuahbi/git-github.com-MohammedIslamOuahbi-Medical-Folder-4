/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0fdfa", 100: "#ccfbf1", 200: "#99f6e4", 300: "#5eead4", 400: "#2dd4bf",
          500: "#14b8a6", 600: "#0d9488", 700: "#0f766e", 800: "#115e59", 900: "#134e4a",
        },
        mint: {
          50: "#eefafe",
          100: "#d9f5fc",
          200: "#b7ebf8",
          300: "#84dcf0",
          400: "#47c7e3",
          500: "#18afd1",
          600: "#0d93b5",
          700: "#0c7692",
          800: "#0d5e74",
          900: "#0d4d60",
        },
        navy: {
          50: "#f4f6fb",
          100: "#e8edf5",
          200: "#cfd9e8",
          300: "#a8b8d1",
          400: "#7d92b6",
          500: "#5f769d",
          600: "#495e82",
          700: "#394968",
          800: "#24324d",
          900: "#121c33",
        },
        sand: {
          50: "#fdfaf5",
          100: "#f8f1e7",
          200: "#f0e2cd",
          300: "#e5cfad",
          400: "#d4b483",
          500: "#c49d67",
          600: "#b18554",
          700: "#946b45",
          800: "#78553a",
          900: "#624631",
        },
        ink: {
          50: "#fbfbfd",
          100: "#f4f5f8",
          200: "#e8ebf1",
          300: "#d5dbe5",
          400: "#94a0b8",
          500: "#677389",
          600: "#4c566b",
          700: "#354055",
          800: "#21293c",
          900: "#141a28",
        },
        accent: {
          amber: "#cb9d54",
          sky: "#65accd",
          rose: "#d16d6a",
        },
      },
      fontFamily: {
        sans: ['"Manrope"', "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"Manrope"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"DM Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 16px 40px -30px rgba(15, 23, 42, 0.28)",
        float: "0 18px 36px -26px rgba(15, 23, 42, 0.28)",
        soft: "0 10px 24px -18px rgba(15, 23, 42, 0.20)",
      },
      backgroundImage: {
        "shell-glow": "#f8fafc",
      },
      borderRadius: {
        "4xl": "2rem",
      },
    },
  },
  plugins: [],
};

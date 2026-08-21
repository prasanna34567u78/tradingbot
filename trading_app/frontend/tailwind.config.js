/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: "#0d1117",
        cardBg: "#161b22",
        borderColor: "#30363d",
        accentGreen: "#00d395",
        accentRed: "#f85149",
        accentBlue: "#58a6ff",
        symbolGold: "#d29922",
        symbolBtc: "#f78166",
        symbolOil: "#58a6ff",
        symbolEur: "#00d395",
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['Fira Code', 'JetBrains Mono', 'monospace'],
      }
    },
  },
  plugins: [
    import('@tailwindcss/forms'),
  ],
}

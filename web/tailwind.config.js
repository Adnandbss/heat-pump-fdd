/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        night: "#0B0B12",
      },
      boxShadow: {
        glass: "0 24px 80px rgba(0,0,0,0.45)",
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: [
          "JetBrains Mono",
          "Cascadia Code",
          "SFMono-Regular",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        elf: {
          green: "#8CFFB2",
          greenDim: "#275B3A",
          panel: "#050806",
          panelSoft: "#08110C",
          line: "#1B2C20",
          danger: "#FF5C64",
          amber: "#F4C35B",
        },
      },
      boxShadow: {
        terminal: "0 0 32px rgba(82, 255, 152, 0.08)",
        glow: "0 0 22px rgba(140, 255, 178, 0.2)",
      },
    },
  },
  plugins: [],
};

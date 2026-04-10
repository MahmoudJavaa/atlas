import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        atlas: {
          50: "#f0f4ff",
          100: "#dde6ff",
          500: "#4f6ef7",
          600: "#3b55e6",
          700: "#2d43c9",
          900: "#1a2580",
        },
      },
    },
  },
  plugins: [],
};
export default config;

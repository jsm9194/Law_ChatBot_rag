/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "Noto Sans KR", "sans-serif"], // ✅ 기본 폰트 교체
      },
    },
  },
  plugins: [],
}

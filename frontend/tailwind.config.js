/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Wanted Sans Variable", "Pretendard", "Inter", "Noto Sans KR", "sans-serif"], // ✅ 기본 폰트
      },
      typography: {
        DEFAULT: {
          css: {
            p: {
              marginBottom: '1rem',   // 문단 간격
              lineHeight: '1.75',     // 줄간격
            },
            ul: {
              marginTop: '0.5rem',
              marginBottom: '0.5rem',
              paddingLeft: '1.5rem',
            },
            li: {
              marginBottom: '0.5rem', // 리스트 항목 간격
            },
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'), // ✅ 추가
  ],
}

// utils/formatAnswer.ts
export function formatAnswer(text: string): string {
  if (!text) return "";

  let formatted = text;

  // --- 구분선 앞뒤 줄바꿈
  formatted = formatted.replace(/-{3,}/g, "\n\n---\n\n");

  // 번호 매기기 항목: "1." 뒤에 줄바꿈 강제
  formatted = formatted.replace(/(\d+\.)\s*(?!\n)/g, "$1 ");

  // "출처" 뒤에 줄바꿈 추가
  formatted = formatted.replace(/출처/g, "출처\n");

  // 여러 줄이 붙은 경우 간격 확보
  formatted = formatted.replace(/\n{2,}/g, "\n\n");

  return formatted.trim();
}

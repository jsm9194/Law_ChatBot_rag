// src/utils/formatAnswer.ts
export function formatAnswer(raw: string): string {
  if (!raw) return "";

  // 1. markdown 코드블록(````markdown`) 제거
  let s = raw.replace(/^```(?:markdown)?\s*/i, "").replace(/```$/, "");

  // 2. #, ##, ### 제목이 붙어 있는 경우 띄어쓰기 보정
  s = s.replace(/(#+)([^\s#])/g, "$1 $2");

  // 3. ) - 리스트 구분 (문단 정리)
  s = s.replace(/\)\s*-\s*/g, ")\n- ");

  // 4. 연속 줄바꿈을 하나로 압축
  s = s.replace(/\n{3,}/g, "\n\n");

  // 5. 좌우 공백 제거
  return s.trim();
}

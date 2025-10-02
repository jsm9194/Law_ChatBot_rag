export function formatAnswer(raw: string): string {
  if (!raw) return "";

  let s = raw.trim();

  // 1. 첫 줄 제목
  if (!s.startsWith("##")) {
    const idx = s.indexOf("\n");
    if (idx !== -1) {
      const firstLine = s.slice(0, idx).trim();
      const rest = s.slice(idx).trim();
      s = `## ${firstLine}\n\n${rest}`;
    } else {
      s = `## ${s}`;
    }
  }

  // 2. 소제목 변환
  s = s.replace(/핵심 법령 조문 정리/g, "\n\n### 핵심 법령 조문 정리\n\n");
  s = s.replace(/준수 체크리스트/g, "\n\n### 준수 체크리스트\n\n");

  // 3. 구분선
  s = s.replace(/-{3,}/g, "\n\n---\n\n");

  // 5. 불릿 리스트
  s = s.replace(/•\s*/g, "- ");
  s = s.replace(/(?:^|\n)([-*+])\s+/g, "\n\n- ");

  // 6. 출처
  s = s.replace(/\[출처\]/g, "\n\n[출처]");

  // 7. 과도한 줄바꿈 정리
  s = s.replace(/\n{3,}/g, "\n\n");

  return s.trim();
}

export function formatAnswer(raw: string): string {
  if (!raw) return "";

  let s = raw.trim();

  s = s.replace(/(#+)([^\s#])/g, "$1 $2");
  s = s.replace(/\)\s*-\s*/g, ")\n- ");

  // #헤더
  s = s.replace(/^# (.*)$/gm, "# $1");
  s = s.replace(/^## (.*)$/gm, "## $1");
  s = s.replace(/^### (.*)$/gm, "### $1");
  

  return s.trim();
}

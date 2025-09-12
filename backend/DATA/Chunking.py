import os
import json
import re
import tiktoken  # pip install tiktoken

INPUT_DIR = "./ArticleCleanData"
OUTPUT_DIR = "./chunkedData"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------
# 유틸: 토큰 카운트
# -------------------------
enc = tiktoken.get_encoding("cl100k_base")  # OpenAI 모델 토크나이저

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

# -------------------------
# 텍스트 라벨링 (항/호/목)
# -------------------------
def label_text(text: str, level: str) -> str:
    text = text.strip()

    if level == "항":
        match = re.match(r"^(\d+)[\.\s]", text)
        if match:
            num = match.group(1)
            text = text[len(match.group(0)):].strip()
            return f"제{num}항 {text}"

    if level == "호":
        match = re.match(r"^(\d+)[\.\s]", text)
        if match:
            num = match.group(1)
            text = text[len(match.group(0)):].strip()
            return f"제{num}호 {text}"

    if level == "목":
        match = re.match(r"^([가-힣])[\.\s]", text)
        if match:
            char = match.group(1)
            text = text[len(match.group(0)):].strip()
            return f"{char}목 {text}"

    return text

# -------------------------
# 개정/신설/삭제 태그 추출
# -------------------------
def extract_amendments(text: str) -> list[dict]:
    pattern = r"<(개정|신설|삭제|타법개정)\s*([0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2}(?:,\s*[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2})*)>"
    matches = re.findall(pattern, text)

    results = []
    for amend_type, date_str in matches:
        dates = [d.strip() for d in date_str.split(",")]
        for d in dates:
            results.append({"type": amend_type, "date": d})
    return results

# -------------------------
# Recursive Chunking (항 → 호 → 목)
# -------------------------
def recursive_chunk(level_name: str, items, header: str, max_tokens: int = 800) -> list[str]:
    chunks = []
    for item in items:
        if not isinstance(item, dict):
            continue

        key = f"{level_name}내용"
        text = label_text(item.get(key, ""), level_name)
        block = f"{header}\n{text}".strip()

        # 하위 단계 감지
        next_level, next_name = None, None
        if level_name == "항":
            next_level, next_name = item.get("호", []), "호"
        elif level_name == "호":
            next_level, next_name = item.get("목", []), "목"

        if isinstance(next_level, dict):
            next_level = [next_level]

        if next_level:
            sub_lines = [block]
            for sub in next_level:
                if not isinstance(sub, dict):
                    continue
                sub_key = f"{next_name}내용"
                sub_text = label_text(sub.get(sub_key, ""), next_name)
                sub_lines.append(sub_text)
            full_block = "\n".join(sub_lines)

            if count_tokens(full_block) > max_tokens:
                sub_chunks = recursive_chunk(next_name, next_level, block, max_tokens)
                chunks.extend(sub_chunks)
            else:
                chunks.append(full_block)
        else:
            chunks.append(block)
    return chunks

# -------------------------
# 조문 단위 → Adaptive Chunking
# -------------------------
def build_article_chunks(article: dict, max_tokens: int = 800) -> list[str]:
    number = article.get("조문번호", "")
    title = article.get("조문제목", "")
    content = article.get("조문내용", "")

    header = f"제{number}조 {title}".strip() if number and title and title not in content else ""
    base_lines = [header, content.strip()] if content else [header]

    clauses = article.get("항", [])
    if isinstance(clauses, dict):
        clauses = [clauses]

    # 항/호/목이 전혀 없는 경우
    if not clauses:
        return ["\n".join(base_lines).strip()]

    # 조문 전체 조립
    clause_lines = base_lines[:]
    for clause in clauses:
        if not isinstance(clause, dict):
            continue

        if clause.get("항내용"):  # 항내용 있으면 추가
            clause_lines.append(label_text(clause["항내용"], "항"))

        # 호가 있으면 추가
        items = clause.get("호", [])
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if isinstance(item, dict) and item.get("호내용"):
                clause_lines.append("  " + label_text(item["호내용"], "호"))

            # 목이 있으면 추가
            subs = item.get("목", [])
            if isinstance(subs, dict):
                subs = [subs]
            for sub in subs:
                if isinstance(sub, dict) and sub.get("목내용"):
                    clause_lines.append("    " + label_text(sub["목내용"], "목"))

    full_text = "\n".join(clause_lines).strip()

    # 전체가 짧으면 그대로 반환
    if count_tokens(full_text) <= max_tokens:
        return [full_text]

    # 길면 항 단위 이하로 내려가기
    if clauses:
        return recursive_chunk("항", clauses, header, max_tokens)

    return [full_text]

# -------------------------
# JSON 변환
# -------------------------
def add_chunks(data: dict, law_name: str) -> dict:
    if "법령" not in data or "조문" not in data["법령"]:
        return data

    for article in data["법령"]["조문"].get("조문단위", []):
        if article.get("조문여부") != "조문":
            continue

        # 여기서 파일명 기반으로 법령 이름 주입
        article["law_name"] = law_name

        chunks = build_article_chunks(article)
        article["embedding_chunks"] = chunks

        amendments = extract_amendments(" ".join(chunks))
        if amendments:
            article["amendments"] = amendments
            article["all_change_dates"] = [a["date"] for a in amendments]

    return data

# -------------------------
# main
# -------------------------
def main():
    for fname in os.listdir(INPUT_DIR):
        if not fname.endswith("_clean.json"):
            continue

        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)

        # 파일명에서 "_clean.json" 제거 → law_name
        law_name = fname.replace("_clean.json", "")

        chunked = add_chunks(data, law_name)

        out_name = fname.replace("_clean.json", "_chunked.json")
        with open(os.path.join(OUTPUT_DIR, out_name), "w", encoding="utf-8") as f:
            json.dump(chunked, f, ensure_ascii=False, indent=2)

        print(f"✅ {fname} → {out_name} 저장 완료 (law_name={law_name})")

if __name__ == "__main__":
    main()

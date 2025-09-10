# pdf_ingest.py
import pdfplumber
import re
import os
import json

# --------------------------
# 텍스트 전처리
# --------------------------
def clean_text(text: str) -> str:
    text = re.sub(r"법제처\s+.*국가법령정보센터", "", text)  # 머리글/꼬리글 제거
    text = re.sub(r"\n\s*(산업안전보건기준에 관한 규칙|산업안전보건법 시행규칙|재난 및 안전관리 기본법 시행령|재난 및 안전관리 기본법|중대재해 처벌 등에 관한 법률 시행령|중대재해 처벌 등에 관한 법률)\s*\n", "\n", text)  # 문서명 제거
    text = re.sub(r"\s+\d+\s+", " ", text)  # 페이지 번호 제거
    text = re.sub(r"\n{2,}", "\n", text)  # 연속 개행 정리
    return text.strip()

def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\n*([①-⑳])", r"\n\1", text)  # 항
    text = re.sub(r"\n*(\d+\.\s)", r"\n\1", text)  # 호
    text = re.sub(r"\n*([가-하]\.\s)", r"\n\1", text)  # 목
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    # 잘린 단어 보정
    text = re.sub(r"(\w)\s+다\b", r"\1다", text)
    text = re.sub(r"하 여야", "하여야", text)
    text = re.sub(r"되 지", "되지", text)
    text = re.sub(r"않 는", "않는", text)
    text = re.sub(r"않 도록", "않도록", text)
    return text.strip()

# --------------------------
# <...>, [...] 주석 추출
# --------------------------
def extract_annotations(text: str):
    annotations = []
    annotations += re.findall(r"<([^>]+)>", text)
    text = re.sub(r"<[^>]+>", "", text)
    annotations += re.findall(r"\[([^\]]+)\]", text)
    text = re.sub(r"\[[^\]]+\]", "", text)
    return [a.strip() for a in annotations], text.strip()

# --------------------------
# 법령명 추출
# --------------------------
def extract_law_name(text: str):
    m = re.search(r"^(.*?규칙|.*?법)", text)
    return m.group(1).strip() if m else None

# --------------------------
# 항/호/목 분리
# --------------------------
CIRCLED_NUM_MAP = {
    "①": "1","②": "2","③": "3","④": "4","⑤": "5",
    "⑥": "6","⑦": "7","⑧": "8","⑨": "9","⑩": "10",
    "⑪": "11","⑫": "12","⑬": "13","⑭": "14","⑮": "15",
    "⑯": "16","⑰": "17","⑱": "18","⑲": "19","⑳": "20"
}

def split_subitems(item_text: str):
    valid_subletters = set("가나다라마바사아자차카타파하")
    parts = re.split(r"(?:^|\s)([가-하])\.\s", item_text)
    subitems, current = [], None
    for part in parts:
        if re.match(r"^[가-하]$", part) and part in valid_subletters:
            if current:
                current["text"] = normalize_whitespace(current["text"])
                subitems.append(current)
            current = {"subitem_number": part, "text": ""}
        else:
            if current:
                current["text"] += part.strip() + " "
    if current:
        current["text"] = normalize_whitespace(current["text"])
        subitems.append(current)
    return subitems if subitems else None

def split_items(paragraph_text: str):
    annotations, clean_text = extract_annotations(paragraph_text)
    pattern = r"(?:^|\s)([1-9][0-9]?)\.\s"
    if not re.search(pattern, clean_text):
        return None, clean_text.strip(), annotations
    parts = re.split(pattern, clean_text)
    items, current = [], None
    intro_text = ""
    for idx, part in enumerate(parts):
        if re.match(r"^[1-9][0-9]?$", part):
            if current:
                current["text"] = normalize_whitespace(current["text"])
                subitems = split_subitems(current["text"])
                if subitems:
                    intro_match = re.split(r"\s[가-하]\.\s", current["text"], maxsplit=1)
                    if intro_match:
                        current["text"] = intro_match[0].strip()
                    current["subitems"] = subitems
                items.append(current)
            current = {"item_number": part, "text": ""}
        else:
            if idx == 0:
                intro_text = normalize_whitespace(part)
            else:
                if current:
                    current["text"] += part.strip() + " "
    if current:
        current["text"] = normalize_whitespace(current["text"])
        subitems = split_subitems(current["text"])
        if subitems:
            intro_match = re.split(r"\s[가-하]\.\s", current["text"], maxsplit=1)
            if intro_match:
                current["text"] = intro_match[0].strip()
            current["subitems"] = subitems
        items.append(current)
    return (items if items else None, intro_text.strip(), annotations)

def split_paragraphs(article_text: str):
    parts = re.split(r"(?:\n)?([①-⑳])", article_text)
    paragraphs, current = [], None
    for part in parts:
        if not part.strip():
            continue
        if re.match(r"[①-⑳]", part):
            if current:
                current["text"] = normalize_whitespace(current["text"])
                items, intro_text, annotations = split_items(current["text"])
                if items:
                    current["items"] = items
                    current["text"] = intro_text
                    if annotations:
                        current["annotations"] = annotations
                paragraphs.append(current)
            num = CIRCLED_NUM_MAP.get(part, part)
            current = {"paragraph_number": num, "text": ""}
        else:
            if current:
                current["text"] += part.strip() + " "
            else:
                current = {"paragraph_number": "본문", "text": part.strip() + " "}
    if current:
        current["text"] = normalize_whitespace(current["text"])
        items, intro_text, annotations = split_items(current["text"])
        if items:
            current["items"] = items
            current["text"] = intro_text
            if annotations:
                current["annotations"] = annotations
        paragraphs.append(current)
    return paragraphs

# --------------------------
# bbox 계산
# --------------------------
def get_bbox_for_text(words, target_text):
    if not words:
        return None
    # 단순히 페이지 전체 bbox로 잡기 (조문 시작 단어 기준 → 확장 가능)
    x0 = min(w["x0"] for w in words)
    top = min(w["top"] for w in words)
    x1 = max(w["x1"] for w in words)
    bottom = max(w["bottom"] for w in words)
    return [x0, top, x1, bottom]

# --------------------------
# 조문 단위 분리
# --------------------------
def chunk_by_articles(full_text: str, law_name: str, page_map: dict, bbox_map: dict):
    pattern = r"(?=제\s*\d+조(?:의\d+)?\s*\(.+?\))"
    raw_articles = re.split(pattern, full_text)
    chunks = []
    current_chapter, current_section, current_subsection = None, None, None
    for art in raw_articles:
        art = art.strip()
        if not art:
            continue
        chap = re.search(r"(제\s*\d+편\s*.+)", art)
        sec = re.search(r"(제\s*\d+장\s*.+)", art)
        subsec = re.search(r"(제\s*\d+관\s*.+)", art)
        if chap:
            current_chapter = chap.group(1).strip()
            art = re.sub(r"제\s*\d+편\s*.+", "", art)
        if sec:
            current_section = sec.group(1).strip()
            art = re.sub(r"제\s*\d+장\s*.+", "", art)
        if subsec:
            current_subsection = subsec.group(1).strip()
            art = re.sub(r"제\s*\d+관\s*.+", "", art)
        m = re.match(r"(제\d+조(?:의\d+)?)\s*\((.+?)\)", art)
        if not m:
            continue
        article_number = m.group(1)
        article_title = m.group(2)
        body = art[m.end():].strip()
        if body and len(body) > 10:
            chunks.append({
                "article_number": article_number,
                "article_title": article_title,
                "chapter": current_chapter,
                "section": current_section,
                "subsection": current_subsection,
                "paragraphs": split_paragraphs(body),
                "law_name": law_name,
                "page_number": page_map.get(article_number),
                "bbox": bbox_map.get(article_number)
            })
    return chunks

# --------------------------
# PDF → JSON 변환
# --------------------------
def pdf_to_chunks(pdf_path: str):
    full_text = ""
    page_map, bbox_map = {}, {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            cleaned = clean_text(text)
            full_text += cleaned + "\n"
            words = page.extract_words()
            for match in re.finditer(r"(제\d+조(?:의\d+)?)", cleaned):
                article_num = match.group(1)
                page_map[article_num] = page_number
                bbox_map[article_num] = get_bbox_for_text(words, article_num)
    law_name = extract_law_name(full_text.split("제1편")[0])
    chunks = chunk_by_articles(full_text, law_name, page_map, bbox_map)
    return chunks

# --------------------------
# 실행
# --------------------------
if __name__ == "__main__":
    pdf_folder = "pdfs"
    output_folder = "texts"
    os.makedirs(output_folder, exist_ok=True)
    for pdf_file in os.listdir(pdf_folder):
        if pdf_file.endswith(".pdf"):
            pdf_path = os.path.join(pdf_folder, pdf_file)
            chunks = pdf_to_chunks(pdf_path)
            output_file = os.path.join(output_folder, pdf_file.replace(".pdf", ".json"))
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            print(f"📖 {pdf_file} → {len(chunks)}개 조문 저장 완료 → {output_file}")

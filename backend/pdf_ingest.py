# pdf_ingest.py
import pdfplumber
import re
import os
import json
from typing import List, Dict, Any, Tuple, Optional

# --------------------------
# 텍스트 전처리
# --------------------------
def clean_text(text: str) -> str:
    text = re.sub(r"법제처\s+.*국가법령정보센터", "", text)  # 머리글/꼬리글 제거
    text = re.sub(
        r"\n\s*(산업안전보건기준에 관한 규칙|산업안전보건법 시행규칙|재난 및 안전관리 기본법 시행령|재난 및 안전관리 기본법|중대재해 처벌 등에 관한 법률 시행령|중대재해 처벌 등에 관한 법률)\s*\n",
        "\n",
        text,
    )  # 문서명 제거
    text = re.sub(r"\s+\d+\s+", " ", text)  # 페이지 번호 제거
    text = re.sub(r"\n{2,}", "\n", text)  # 연속 개행 정리
    return text.strip()

def normalize_structure(text: str) -> str:
    # 항
    text = re.sub(r"\n*([①-⑳])", r"\n\1", text)
    # 호
    text = re.sub(r"\n*(\d+\.\s)", r"\n\1", text)
    # 목
    text = re.sub(r"\n*([가-하]\.\s)", r"\n\1", text)
    return text

def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\n+", " ", text)   # 여러 줄바꿈 → 공백
    text = re.sub(r"\s{2,}", " ", text)  # 연속 공백 → 하나
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
                current["text"] = normalize_structure(current["text"])
                subitems.append(current)
            current = {"subitem_number": part, "text": ""}
        else:
            if current:
                current["text"] += part.strip() + " "
    if current:
        current["text"] = normalize_structure(current["text"])
        subitems.append(current)
    return subitems if subitems else None

def split_items(paragraph_text: str):
    annotations, clean_txt = extract_annotations(paragraph_text)
    pattern = r"(?:^|\s)([1-9][0-9]?)\.\s"
    if not re.search(pattern, clean_txt):
        return None, clean_txt.strip(), annotations
    parts = re.split(pattern, clean_txt)
    items, current = [], None
    intro_text = ""
    for idx, part in enumerate(parts):
        if re.match(r"^[1-9][0-9]?$", part):
            if current:
                current["text"] = normalize_structure(current["text"])
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
                intro_text = normalize_structure(part)
            else:
                if current:
                    current["text"] += part.strip() + " "
    if current:
        current["text"] = normalize_structure(current["text"])
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
                current["text"] = normalize_structure(current["text"])
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
        current["text"] = normalize_structure(current["text"])
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
                "type": "article",
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
# [ADDED] Annex(별표/부칙/별지) 처리 유틸
# ============================================================

# 별표 헤더: 라인의 어느 위치든 [별표 N] 형태가 등장 (앞에 ■, 문서명 등이 붙을 수 있음)
ANNEX_HEADER_REGEX = re.compile(
    r"(?m)^\s*(?:■\s*)?.{0,100}?\[별표\s*(?P<num>\d+)\]\s*(?P<header_rest>[^\n]*)"
)

# '... 관련'에서 조문 연결
RELATED_ARTICLE_REGEX = re.compile(r"(제\d+조(?:제\d+항)?)\s*관련")

def clean_cell(v):
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()

def normalize_header_row(row: List[Any]) -> List[str]:
    headers = [clean_cell(c) for c in row]
    for i, h in enumerate(headers):
        if not h:
            headers[i] = f"col_{i+1}"
    return headers

def table_to_records(table: List[List[Any]]) -> List[Dict[str, Any]]:
    """
    pdfplumber.extract_tables()에서 얻은 단일 테이블(list[list])을
    dict 레코드 리스트로 변환
    """
    if not table or not any(row for row in table):
        return []
    header = normalize_header_row(table[0])
    records = []
    for r in table[1:]:
        row = [clean_cell(c) for c in r]
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        elif len(row) > len(header):
            row = row[:len(header)]
        rec = {header[i]: row[i] for i in range(len(header))}
        records.append(rec)
    return records

def records_to_embed_text_rows(records: List[Dict[str, Any]], annex_meta: Dict[str, Any]) -> List[str]:
    """
    행 단위 임베딩용 직렬 문자열 생성
    ex) "유해인자=벤젠 | TWA(ppm)=0.5 | ... | 근거=별표 19 / 제145조제1항 / 유해인자별 노출 농도의 허용기준"
    """
    out = []
    basis = []
    if annex_meta.get("annex_number"):
        basis.append(annex_meta["annex_number"])
    if annex_meta.get("related_article"):
        basis.append(annex_meta["related_article"])
    if annex_meta.get("title"):
        basis.append(annex_meta["title"])
    basis_str = " / ".join(basis) if basis else ""
    for rec in records:
        pairs = [f"{k}={v}" for k, v in rec.items() if str(v).strip() != ""]
        line = " | ".join(pairs)
        if basis_str:
            line = f"{line} | 근거={basis_str}"
        out.append(line)
    return out

def build_page_spans(page_texts: List[str]) -> List[Tuple[int, int]]:
    """
    각 페이지 텍스트 길이를 바탕으로 full_text에서의 [start, end) span을 계산.
    return: [(start0, end0), (start1, end1), ...]
    """
    spans = []
    cur = 0
    for t in page_texts:
        start = cur
        end = cur + len(t) + 1  # 페이지 간 개행 포함
        spans.append((start, end))
        cur = end
    return spans

def index_to_page(page_spans: List[Tuple[int, int]], idx: int) -> int:
    """
    full_text 인덱스 → 페이지 번호(1-based) 추정
    """
    for i, (s, e) in enumerate(page_spans):
        if s <= idx < e:
            return i + 1
    return len(page_spans)  # 말미면 마지막 페이지로

def span_to_pages(page_spans: List[Tuple[int, int]], start_idx: int, end_idx: int) -> List[int]:
    """
    구간[start_idx, end_idx) 이 걸치는 페이지 번호 리스트(1-based)
    """
    pages = set()
    for i, (s, e) in enumerate(page_spans):
        if not (end_idx <= s or e <= start_idx):
            pages.add(i + 1)
    return sorted(pages)

def extract_annex_blocks(full_text: str) -> List[Dict[str, Any]]:
    """
    full_text에서 [별표 N] 헤더들을 찾아 각 블록의 시작/끝 인덱스를 산정
    """
    matches = list(ANNEX_HEADER_REGEX.finditer(full_text))
    annexes = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        annex_number = f"별표 {m.group('num')}"
        header_rest = m.group("header_rest").strip()
        header_text = full_text[start: full_text.find("\n", start) if "\n" in full_text[start:] else end]
        annexes.append({
            "start_idx": start,
            "end_idx": end,
            "annex_number": annex_number,
            "header_rest": header_rest,
            "header_text": header_text
        })
    return annexes

def annex_title_and_related(annex_text: str, header_rest: str) -> Tuple[Optional[str], Optional[str]]:
    """
    별표 제목/관련 조문 추출
    """
    # 제목 후보: 헤더 라인 바로 뒤 첫 비어있지 않은 줄 또는 header_rest
    lines = [ln.strip() for ln in annex_text.splitlines() if ln.strip()]
    title = header_rest if header_rest else (lines[1] if len(lines) > 1 else (lines[0] if lines else None))
    # '... (제145조제1항 관련)' 같은 문구에서 관련 조문
    rel = None
    m = RELATED_ARTICLE_REGEX.search(annex_text)
    if m:
        rel = m.group(1)
    return title, rel

def extract_tables_from_pages(pdf: pdfplumber.PDF, page_numbers: List[int]) -> List[List[List[Any]]]:
    """
    해당 페이지들에서 표 추출 시도 (여러 테이블 합침)
    """
    all_tables: List[List[List[Any]]] = []
    for pno in page_numbers:
        try:
            page = pdf.pages[pno - 1]
            tables = page.extract_tables() or []
            for tb in tables:
                # 표로 인정 가능한 최소 조건: 행 2줄 이상(헤더+데이터)
                if tb and len(tb) >= 2 and any(any(cell for cell in row) for row in tb):
                    all_tables.append(tb)
        except Exception:
            # 표 추출 실패 시 무시(아래에서 텍스트 fallback)
            continue
    return all_tables

def page_bbox(words_by_page: Dict[int, List[Dict[str, Any]]], page_numbers: List[int]) -> List[Optional[List[float]]]:
    """
    각 페이지의 bbox 리스트 (워드 전역 범위)
    """
    bboxes = []
    for pno in page_numbers:
        words = words_by_page.get(pno)
        bboxes.append(get_bbox_for_text(words, ""))  # 전체 범위
    return bboxes

def parse_annexes(full_text: str,
                  page_spans: List[Tuple[int, int]],
                  pdf: pdfplumber.PDF,
                  words_by_page: Dict[int, List[Dict[str, Any]]],
                  law_name: Optional[str],
                  source_pdf: str) -> List[Dict[str, Any]]:
    """
    full_text 기반으로 별표 블록을 추출하고, 페이지/표 여부를 판단하여 annex chunk 생성
    """
    annex_blocks = extract_annex_blocks(full_text)
    annex_chunks: List[Dict[str, Any]] = []

    for blk in annex_blocks:
        start_idx, end_idx = blk["start_idx"], blk["end_idx"]
        pages = span_to_pages(page_spans, start_idx, end_idx) or [index_to_page(page_spans, start_idx)]
        text_block = full_text[start_idx:end_idx].strip()

        title, related = annex_title_and_related(text_block, blk.get("header_rest", ""))

        # 표 추출 시도
        tables = extract_tables_from_pages(pdf, pages)
        table_records: List[Dict[str, Any]] = []
        if tables:
            # 여러 테이블을 순서대로 records로 확장
            for tb in tables:
                recs = table_to_records(tb)
                # 빈 레코드만 있는 테이블은 스킵
                if recs:
                    table_records.extend(recs)

        chunk: Dict[str, Any] = {
            "type": "annex",
            "annex_number": blk["annex_number"],
            "title": title,
            "related_article": related,
            "law_name": law_name,
            "source_pdf": source_pdf,
            # 별표는 여러 페이지를 걸칠 수 있음
            "page_numbers": pages,
            "bboxes": page_bbox(words_by_page, pages),
        }

        if table_records:
            chunk["table"] = table_records
            # 임베딩용 행 직렬 문자열(자동) — 후속 파이프라인에서 선택 사용
            chunk["embed_text_rows"] = records_to_embed_text_rows(
                table_records,
                {"annex_number": blk["annex_number"], "title": title, "related_article": related},
            )
            # 텍스트 원문도 함께 보관(검증/검색용)
            chunk["content"] = text_block
        else:
            # 표가 추출되지 않으면 텍스트 블록 그대로 저장 (UI에서 PDF 원문 확인)
            chunk["content"] = text_block

        annex_chunks.append(chunk)

    return annex_chunks


# --------------------------
# PDF → JSON 변환
# --------------------------
def pdf_to_chunks(pdf_path: str):
    full_text = ""
    page_map, bbox_map = {}, {}
    page_texts: List[str] = []
    words_by_page: Dict[int, List[Dict[str, Any]]] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                page_texts.append("")
                continue
            cleaned = clean_text(text)
            page_texts.append(cleaned)
            full_text += cleaned + "\n"

            words = page.extract_words() or []
            words_by_page[page_number] = words

            for match in re.finditer(r"(제\d+조(?:의\d+)?)", cleaned):
                article_num = match.group(1)
                page_map[article_num] = page_number
                bbox_map[article_num] = get_bbox_for_text(words, article_num)

        head_for_law = ""
        try:
            head_for_law = full_text.split("제1편")[0]
        except Exception:
            head_for_law = full_text[:1000]
        law_name = extract_law_name(head_for_law)

        article_chunks = chunk_by_articles(full_text, law_name, page_map, bbox_map)
        src_pdf_name = os.path.basename(pdf_path)
        for c in article_chunks:
            c["source_pdf"] = src_pdf_name

        page_spans = build_page_spans(page_texts)
        annex_chunks = parse_annexes(
            full_text=full_text,
            page_spans=page_spans,
            pdf=pdf,
            words_by_page=words_by_page,
            law_name=law_name,
            source_pdf=src_pdf_name,
        )

    chunks = article_chunks + annex_chunks

    # [마지막 단계] 모든 텍스트에 whitespace 정리 적용
    for c in chunks:
        if "paragraphs" in c:
            for p in c["paragraphs"]:
                if "text" in p:
                    p["text"] = normalize_whitespace(p["text"])
                if "items" in p:
                    for item in p["items"]:
                        if "text" in item:
                            item["text"] = normalize_whitespace(item["text"])
                        if "subitems" in item:
                            for sub in item["subitems"]:
                                if "text" in sub:
                                    sub["text"] = normalize_whitespace(sub["text"])
        if "content" in c:
            c["content"] = normalize_whitespace(c["content"])

    return chunks

# --------------------------
# 실행
# --------------------------
if __name__ == "__main__":
    pdf_folder = "pdfs"
    output_folder = "texts"
    os.makedirs(output_folder, exist_ok=True)

    for pdf_file in os.listdir(pdf_folder):
        if not pdf_file.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_folder, pdf_file)
        try:
            chunks = pdf_to_chunks(pdf_path)
            output_file = os.path.join(output_folder, pdf_file.replace(".pdf", ".json"))
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            print(f"📖 {pdf_file} → {len(chunks)}개 청크 저장 완료 → {output_file}")
        except Exception as e:
            print(f"⚠️ {pdf_file} 처리 중 오류: {e}")

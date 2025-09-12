import os
import json

INPUT_DIR = "./jsonData"
OUTPUT_DIR = "./ArticleCleanData"
os.makedirs(OUTPUT_DIR, exist_ok=True)

circled_num_map = {
    "①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5",
    "⑥": "6", "⑦": "7", "⑧": "8", "⑨": "9", "⑩": "10",
    "⑪": "11", "⑫": "12", "⑬": "13", "⑭": "14", "⑮": "15",
    "⑯": "16", "⑰": "17", "⑱": "18", "⑲": "19", "⑳": "20",
}

def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    for k, v in circled_num_map.items():
        text = text.replace(k, v)
    return text.strip()

def clean_article(article: dict) -> dict:
    cleaned = {}
    for k, v in article.items():
        if k in ["조문변경여부", "조문이동이전", "조문이동이후", "호번호", "목번호", "항번호"]:
            continue
        if k in ["조문내용", "조문제목", "항내용", "호내용", "목내용"]:
            cleaned[k] = normalize_text(v)
        elif k == "항":
            if isinstance(v, list):
                cleaned[k] = [clean_article(x) for x in v if isinstance(x, dict)]
            elif isinstance(v, dict):
                cleaned[k] = clean_article(v)
        elif k == "호":
            if isinstance(v, list):
                cleaned[k] = [clean_article(x) for x in v if isinstance(x, dict)]
            elif isinstance(v, dict):
                cleaned[k] = clean_article(v)
        elif k == "목":
            if isinstance(v, list):
                cleaned[k] = [clean_article(x) for x in v if isinstance(x, dict)]
            elif isinstance(v, dict):
                cleaned[k] = clean_article(v)
        elif k == "항번호":
            cleaned[k] = normalize_text(v)
        else:
            cleaned[k] = v
    return cleaned

def clean_json(data: dict) -> dict:
    if "법령" not in data:
        return data
    law = data["법령"]

    # ✅ 조문만 남기고 나머지는 제거
    cleaned_law = {}
    if isinstance(law.get("조문"), dict) and "조문단위" in law["조문"]:
        cleaned_law["조문"] = {
            "조문단위": [clean_article(x) for x in law["조문"]["조문단위"]]
        }

    return {"법령": cleaned_law}

def main():
    for fname in os.listdir(INPUT_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        cleaned = clean_json(data)
        out_name = fname.replace(".json", "_clean.json")
        with open(os.path.join(OUTPUT_DIR, out_name), "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        print(f"✅ {fname} → {out_name} 저장 완료")

if __name__ == "__main__":
    main()

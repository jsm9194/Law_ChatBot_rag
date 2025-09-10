import os
import json
import hashlib
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams
from openai import OpenAI

# 이 파일은 JSON 파일을 읽어서 Qdrant에 임베딩 벡터와 함께 저장합니다.

# --------------------------
# 환경설정
# --------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Qdrant 연결
qdrant = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "laws"
DIM = 3072  # text-embedding-3-large 차원 수

# 컬렉션 없으면 생성
if COLLECTION_NAME not in [c.name for c in qdrant.get_collections().collections]:
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=DIM, distance="Cosine")
    )

# --------------------------
# 유틸 함수
# --------------------------
def hash_id(text: str) -> str:
    """텍스트를 해시해서 Qdrant point_id로 사용"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def embed_text(text: str):
    """OpenAI 임베딩"""
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    return response.data[0].embedding

def build_article_text(article: dict) -> str:
    """조문 JSON(dict) → 합쳐진 텍스트(str) 변환"""
    lines = []
    lines.append(f"{article['law_name']} {article['article_number']}({article['article_title']})")

    if article.get("chapter"):
        lines.append(article["chapter"])
    if article.get("section"):
        lines.append(article["section"])
    if article.get("subsection"):
        lines.append(article["subsection"])

    for p in article.get("paragraphs", []):
        if p["paragraph_number"] == "본문":
            lines.append(f"[본문] {p['text']}")
        else:
            lines.append(f"[제{p['paragraph_number']}항] {p['text']}")

        if "items" in p:
            for item in p["items"]:
                lines.append(f"  - [제{item['item_number']}호] {item['text']}")
                if "subitems" in item:
                    for sub in item["subitems"]:
                        lines.append(f"    * [{sub['subitem_number']}목] {sub['text']}")

    return "\n".join(lines).strip()

# --------------------------
# JSON → 임베딩 → Qdrant 저장
# --------------------------
def process_json(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    points = []
    for c in chunks:
        full_text = build_article_text(c)
        vector = embed_text(full_text)
        point_id = hash_id(c["article_number"] + c["article_title"])

        payload = {
            "law_name": c.get("law_name"),
            "article_number": c["article_number"],
            "article_title": c["article_title"],
            "chapter": c.get("chapter"),
            "section": c.get("section"),
            "subsection": c.get("subsection"),
            "text": full_text
        }

        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"✅ {json_file} → {len(points)}개 업로드 완료")

# --------------------------
# 실행
# --------------------------
if __name__ == "__main__":
    json_dir = "texts"
    for file in os.listdir(json_dir):
        if file.endswith(".json") and not file.endswith("_metadata.json"):
            process_json(os.path.join(json_dir, file))
    print("🎉 모든 JSON 업로드 완료")

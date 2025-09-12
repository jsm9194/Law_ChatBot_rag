import os
import json
import hashlib
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams
from openai import OpenAI
from tqdm import tqdm

# --------------------------
# 환경설정
# --------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

qdrant = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "laws"
DIM = 3072  # text-embedding-3-large 차원 수

# --------------------------
# Qdrant 컬렉션 생성 (없으면)
# --------------------------
if COLLECTION_NAME not in [c.name for c in qdrant.get_collections().collections]:
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=DIM, distance="Cosine"),
    )

# --------------------------
# 유틸 함수
# --------------------------
def hash_id(law_name: str, article_key: str, text: str) -> str:
    """법령명 + 조문키 + 텍스트를 해시해서 point_id로 사용"""
    raw = law_name + article_key + text
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def get_embeddings(texts: list[str]) -> list[list[float]]:
    """OpenAI API로 배치 임베딩 생성"""
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=texts
    )
    return [d.embedding for d in response.data]

# --------------------------
# 메인 로직
# --------------------------
INPUT_DIR = "./ChunkedData"

def main():
    for fname in os.listdir(INPUT_DIR):
        if not fname.endswith("_chunked.json"):
            continue

        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)

        articles = data["법령"]["조문"].get("조문단위", [])

        for article in tqdm(articles, desc=f"{fname} 업로드 중"):
            if "embedding_chunks" not in article:
                continue

            law_name = article.get("law_name", fname.replace("_chunked.json", ""))
            article_key = article.get("조문키", "")
            article_number = article.get("조문번호", "")
            article_title = article.get("조문제목", "")

            chunks = article["embedding_chunks"]

            # ✅ 배치로 임베딩 생성
            embeddings = get_embeddings(chunks)

            # ✅ PointStruct 모아서 한 번에 upsert
            points = []
            for chunk, emb in zip(chunks, embeddings):
                point_id = hash_id(law_name, article_key, chunk)

                payload = {
                    "law_name": law_name,
                    "article_number": article_number,
                    "article_title": article_title,
                    "article_key": article_key,
                    "text": chunk,
                    "amendments": article.get("amendments", []),
                    "all_change_dates": article.get("all_change_dates", []),
                }

                points.append(PointStruct(id=point_id, vector=emb, payload=payload))

            if points:
                qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

        print(f"✅ {fname} 임베딩 및 Qdrant 적재 완료")

if __name__ == "__main__":
    main()

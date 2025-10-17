import os
import json
import hashlib
import time
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams
from FlagEmbedding import BGEM3FlagModel  # ✅ BGE-M3
# from dotenv import load_dotenv  # 필요 시 주석 해제

# --------------------------
# 환경설정
# --------------------------
# load_dotenv()

print("🧠 BGE-M3 모델 로딩 중...")
model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)  # ✅ FP16으로 GPU 메모리 절약
print("✅ 모델 로드 완료")

# ✅ Qdrant 연결
qdrant = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "laws_bge_m3"
DIM = 1024  # ✅ BGE-M3 dense 벡터 차원
BATCH_SIZE = 100
INPUT_DIR = "./ChunkedData"

# --------------------------
# Qdrant 컬렉션 초기화
# --------------------------
try:
    qdrant.delete_collection(COLLECTION_NAME)
    print(f"🗑 기존 컬렉션 {COLLECTION_NAME} 삭제 완료")
except Exception:
    print("⚠️ 기존 컬렉션 없음, 새로 생성합니다")

qdrant.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=DIM, distance="Cosine"),
)
print(f"✅ 새 컬렉션 {COLLECTION_NAME} 생성 완료")

# --------------------------
# 유틸 함수
# --------------------------
def hash_id(law_name: str, article_key: str, text: str) -> str:
    """법령명 + 조문키 + 텍스트를 해시해서 point_id로 사용"""
    raw = law_name + article_key + text
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    ✅ BGE-M3 임베딩 생성
    - 'dense_vecs' (1024차원) 반환
    - 필요 시 sparse나 colbert_vecs도 함께 받을 수 있음
    """
    try:
        output = model.encode(texts, batch_size=len(texts))
        dense_vecs = output["dense_vecs"]  # 핵심: 이게 우리가 Qdrant에 저장할 벡터
        return dense_vecs.tolist()
    except Exception as e:
        print(f"❌ 임베딩 실패: {e}")
        raise


# --------------------------
# 메인 로직
# --------------------------
def main():
    start_time = time.time()

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

            # ✅ 빈 텍스트 제거
            chunks = [c for c in article["embedding_chunks"] if c.strip()]
            if not chunks:
                continue

            # ✅ 배치 단위로 임베딩 생성
            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i : i + BATCH_SIZE]
                embeddings = get_embeddings(batch)

                points = []
                for chunk, emb in zip(batch, embeddings):
                    if len(emb) != DIM:
                        raise ValueError(
                            f"❌ 벡터 차원 불일치: expected {DIM}, got {len(emb)} "
                            f"(텍스트 앞부분: {chunk[:50]!r})"
                        )

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

                # ✅ upsert 실행
                if points:
                    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

        print(f"✅ {fname} 임베딩 및 Qdrant 적재 완료")

    elapsed = time.time() - start_time
    print(f"⏱ 전체 처리 완료 ({elapsed:.1f}초 경과)")


if __name__ == "__main__":
    main()

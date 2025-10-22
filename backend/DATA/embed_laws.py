import os
import json
import hashlib
import time
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
BATCH_SIZE = 100  # 임베딩 배치 크기
MAX_RETRIES = 3   # 재시도 횟수
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
def hash_id(*args) -> str:
    """여러 식별 정보를 합쳐 해시 생성"""
    raw = "_".join(str(a) for a in args if a)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_embeddings_with_retry(texts: list[str]) -> list[list[float]]:
    """OpenAI API 임베딩 요청 (재시도 포함)"""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.embeddings.create(
                model="text-embedding-3-large",
                input=texts
            )
            embeddings = [d.embedding for d in response.data]
            return embeddings
        except Exception as e:
            print(f"❌ 임베딩 요청 실패 (시도 {attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(2 ** attempt)  # 지수 백오프
    raise RuntimeError("임베딩 생성 실패 (재시도 초과)")


def extract_all_chunks(article: dict) -> list[str]:
    """
    조문 및 하위 항목(항, 호, 목 등)의 embedding_chunks를 재귀적으로 추출
    다양한 JSON 구조(리스트/문자열 혼합)를 안전하게 처리
    """
    chunks = []

    # 현재 레벨의 embedding_chunks
    if "embedding_chunks" in article:
        chunks.extend([c for c in article["embedding_chunks"] if c.strip()])

    # 하위 구조 재귀 탐색
    for key in ["항", "호", "목"]:
        if key not in article:
            continue

        sub_item = article[key]

        # 1️⃣ 리스트일 경우
        if isinstance(sub_item, list):
            for sub in sub_item:
                if isinstance(sub, dict):
                    chunks.extend(extract_all_chunks(sub))

        # 2️⃣ 딕셔너리일 경우
        elif isinstance(sub_item, dict):
            chunks.extend(extract_all_chunks(sub_item))

        # 3️⃣ 문자열(단순 텍스트)일 경우
        elif isinstance(sub_item, str):
            if sub_item.strip():
                chunks.append(sub_item.strip())

    return chunks


def build_payload(article: dict, chunk: str, law_name: str) -> dict:
    """Qdrant에 저장할 payload 구성"""
    return {
        "law_name": law_name,
        "조문번호": article.get("조문번호", ""),
        "항번호": article.get("항번호", ""),
        "호번호": article.get("호번호", ""),
        "목번호": article.get("목번호", ""),
        "조문제목": article.get("조문제목", ""),
        "조문내용": chunk,
        "조문키": article.get("조문키", ""),
        "조문시행일자": article.get("조문시행일자", ""),
        "amendments": article.get("amendments", []),
        "all_change_dates": article.get("all_change_dates", []),
    }


# --------------------------
# 메인 로직
# --------------------------
def main():
    for fname in os.listdir(INPUT_DIR):
        if not fname.endswith("_chunked.json"):
            continue

        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)

        articles = data["법령"]["조문"].get("조문단위", [])
        total_points = 0

        for article in tqdm(articles, desc=f"{fname} 업로드 중"):
            # ✅ 조문 및 하위 항목 전체에서 청크 추출
            all_chunks = extract_all_chunks(article)
            if not all_chunks:
                continue

            law_name = article.get("law_name", fname.replace("_chunked.json", ""))
            article_key = article.get("조문키", "")

            # ✅ 배치 단위 임베딩 생성 및 업로드
            for i in range(0, len(all_chunks), BATCH_SIZE):
                batch = all_chunks[i:i + BATCH_SIZE]
                embeddings = get_embeddings_with_retry(batch)

                points = []
                for chunk, emb in zip(batch, embeddings):
                    if len(emb) != DIM:
                        raise ValueError(
                            f"❌ 벡터 차원 불일치: expected {DIM}, got {len(emb)} "
                            f"(텍스트 앞부분: {chunk[:50]!r})"
                        )

                    point_id = hash_id(law_name, article_key, chunk)
                    payload = build_payload(article, chunk, law_name)
                    points.append(PointStruct(id=point_id, vector=emb, payload=payload))

                if points:
                    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
                    total_points += len(points)

        print(f"✅ {fname} 임베딩 및 Qdrant 적재 완료 ({total_points}개 벡터)")

if __name__ == "__main__":
    main()

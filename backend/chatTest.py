from qdrant_client import QdrantClient
import dotenv
from openai import OpenAI
import os

# --------------------------
# 설정
# --------------------------
dotenv.load_dotenv()
# --------------------------
qdrant = QdrantClient(host="localhost", port=6333)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
COLLECTION_NAME = "laws"

# --------------------------
# 검색 함수
# --------------------------
def search_laws(query: str, top_k: int = 3):
    # 1. 쿼리 임베딩
    embedding = client.embeddings.create(
        model="text-embedding-3-large",
        input=query
    ).data[0].embedding

    # 2. Qdrant에서 검색
    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        limit=top_k
    )

    # 3. 출력
    for i, r in enumerate(results, start=1):
        print(f"--- Top {i} ---")
        print(f"점수: {r.score:.3f}")
        print(f"법령명: {r.payload.get('law_name')}")
        print(f"조문번호: {r.payload.get('article_number')}")
        print(f"조문제목: {r.payload.get('article_title')}")
        print(f"본문:\n{r.payload.get('text')[:300]}...\n")

# --------------------------
# 테스트 실행
# --------------------------
if __name__ == "__main__":
    query = "자동문에는 어떤 안전장치를 설치해야 합니까?"
    search_laws(query)

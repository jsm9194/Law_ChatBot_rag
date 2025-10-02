import json
import os
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from .law_mapping import make_law_link
import dotenv

dotenv.load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "laws"


def ask(query: str, model: str = "", top_k: int = 5):
    """
    Qdrant에서 관련 법령 검색 후, LLM으로 답변 생성.
    ChatGPT citation 스타일:
    - answer: 마크다운 본문 (문단마다 [1], [2] superscript 포함)
    - sources: [{id, law, article, url}, ...]
    """

    # 1) 임베딩 생성
    try:
        embedding = client.embeddings.create(
            model="text-embedding-3-large",
            input=query
        ).data[0].embedding
    except Exception as e:
        return {
            "query": query,
            "context": [],
            "sources": [],
            "error": str(e)
        }

    # 2) Qdrant에서 관련 문서 검색
    try:
        search_results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            limit=top_k
        ).points
    except Exception as e:
        return {
            "query": query,
            "context": [],
            "sources": [],
            "error": str(e)
        }

    # 3) 출처 데이터 가공
    sources = []
    context_chunks = []
    for idx, r in enumerate(search_results, start=1):
        payload = r.payload
        law_name = payload.get("law_name", "")
        jo = payload.get("article_number", "")
        text = payload.get("text", "")
        link = make_law_link(law_name, jo)

        sources.append({
            "id": idx,
            "law": law_name,
            "article": f"제{jo}조" if jo else "",
            "url": link
        })

        context_chunks.append(f"[{idx}] {law_name} {jo}조: {text}")

    context = "\n\n".join(context_chunks)

    return {
        "query": query,
        "context": context_chunks,
        "sources": sources
    }


if __name__ == "__main__":
    query = "산업안전보건법에서 사업주의 안전조치 의무는 어떻게 규정되어 있나요?"

    result = ask(query)

    # 추출 결과 확인
    print("=== 컨텍스트 ===")
    for item in result.get("context", []):
        print(item)
    print("\n=== 출처 ===")
    print(json.dumps(result.get("sources", []), ensure_ascii=False, indent=2))

    if "error" in result:
        print("\n=== 오류 ===")
        print(result["error"])

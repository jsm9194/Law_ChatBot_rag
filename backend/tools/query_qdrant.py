import json
import os
from openai import OpenAI
from qdrant_client import QdrantClient
from .law_mapping import make_law_link
import dotenv

dotenv.load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "laws"


def rewrite_query_for_search(query: str, model: str = "gpt-4.1-mini") -> str:
    """
    사용자의 자연어 질문을 Qdrant 벡터 검색에 최적화된 질의로 리라이팅.
    예: '사업주의 안전조치 의무는?' -> '산업안전보건법 사업주 안전조치 의무 관련 조문'
    """
    prompt = f"""
    너는 한국 법령 검색 최적화 전문가야.
    사용자가 입력한 질문의 의도를 파악하고 법령 검색에 최적화된 형태로 질문을 리라이팅해줘.
    불필요한 단어는 제거하고, 핵심 키워드를 중심으로 문장을 재구성해줘.
    임베딩에 사용한 청크데이터는 법령명, 조문번호, 조문내용의 json 파일이야.
    임베딩 청크 데이터 예시:
    {{
      "law_name": "산업안전보건법",
      "조문번호": "29",
      "조문내용": "사업주는 근로자의 안전과 보건을 유지하기 위하여 필요한 조치를 하여야 한다."
    }}

    사용자 질문:
    {query}
    """

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "너는 법령 질의 검색 전문가야."},
                {"role": "user", "content": prompt}
            ]
        )
        rewritten_query = response.choices[0].message.content.strip()
        return rewritten_query
    except Exception as e:
        return query  # 실패 시 원문 그대로 사용


def ask(query: str, model: str = "gpt-4o-mini", top_k: int = 5):
    """
    Qdrant에서 관련 법령 검색 후 LLM으로 리라이팅된 쿼리 기반 검색.
    """
    # 1) 사용자 질문 리라이팅
    rewritten_query = rewrite_query_for_search(query)
    print(f"[리라이팅된 검색 쿼리] {rewritten_query}")

    # 2) 임베딩 생성
    try:
        embedding = client.embeddings.create(
            model="text-embedding-3-large",
            input=rewritten_query
        ).data[0].embedding
    except Exception as e:
        return {"query": query, "error": f"임베딩 생성 실패: {e}"}

    # 3) Qdrant 검색
    try:
        search_results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            limit=top_k
        ).points
    except Exception as e:
        return {"query": query, "error": f"Qdrant 검색 실패: {e}"}

    # 4) 결과 정리
    sources = []
    context_chunks = []
    for idx, r in enumerate(search_results, start=1):
        payload = r.payload
        law_name = payload.get("law_name", "")
        jo = payload.get("조문번호", "")
        text = payload.get("조문내용", "")
        link = make_law_link(law_name, jo)

        sources.append({
            "id": idx,
            "law": law_name,
            "article": f"제{jo}조" if jo else "",
            "url": link
        })

        context_chunks.append(f"[{idx}] {law_name} 제{jo}조: {text}")

    return {
        "original_query": query,
        "rewritten_query": rewritten_query,
        "context": context_chunks,
        "sources": sources
    }


if __name__ == "__main__":
    query = "산업안전보건법에서 사업주의 안전조치 의무는 어떻게 규정되어 있나요?"
    result = ask(query)

    print("\n=== 원문 ===")
    print(result["original_query"])

    print("\n=== 리라이팅된 검색 쿼리 ===")
    print(result["rewritten_query"])

    print("\n=== 검색 결과 ===")
    for c in result["context"]:
        print(c)

    print("\n=== 출처 ===")
    print(json.dumps(result["sources"], ensure_ascii=False, indent=2))

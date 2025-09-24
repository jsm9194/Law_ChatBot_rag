import json
import os
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from law_mapping import make_law_link
import dotenv

dotenv.load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "laws"


def ask(query: str, model: str = "gpt-5-mini", top_k: int = 5):
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
            "answer": "❌ 질문 분석(임베딩) 중 오류가 발생했습니다.",
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
            "answer": "❌ 법령 데이터베이스(Qdrant) 검색 중 오류가 발생했습니다.",
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

    # 4) LLM 프롬프트 작성
    context = "\n\n".join(context_chunks)
    prompt = f"""
너는 법령 문서를 참고해 답변하는 법률 상담 챗봇이야.
아래 질문과 참고 문서를 보고, 사용자가 보기 쉽게 답변을 작성하라.

질문:
{query}

참고 문서 (각 문단 앞의 번호는 citation 번호):
{context}
출력 규칙:
1. 답변은 자연스럽게 요약·설명할 것. 
2. 반드시 **마크다운 형식**으로 작성할 것.
3. 법령 조문을 언급할 때는 sources 배열의 정보를 이용해
   `[법령명 제oo조](URL)` 형식으로 링크를 붙여라.
   - URL은 반드시 sources 배열의 url을 그대로 사용해야 한다.
   - 예: "... 안전조치를 해야 한다 [산업안전보건법 제15조](http://www.law.go.kr/...)."
4. 불필요하게 '참고', '출처' 섹션을 따로 만들지 말고, 본문 안에만 인용하라.
"""

    # 5) 모델 호출
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "너는 한국 법령/판례 전문 상담 챗봇이다."},
                {"role": "user", "content": prompt}
            ]
        )
        answer_text = response.choices[0].message.content
    except Exception as e:
        return {
            "answer": "❌ 답변 생성 중 오류가 발생했습니다.",
            "sources": sources,
            "error": str(e)
        }

    # 6) 최종 반환
    return {
        "answer": answer_text,  # 마크다운 + citation [번호]
        "sources": sources      # JSON 배열 (id와 매핑됨)
    }


if __name__ == "__main__":
    query = "산업안전보건법에서 사업주의 안전조치 의무는 어떻게 규정되어 있나요?"

    result = ask(query)

    # 보기 좋게 출력
    print("=== 답변 ===")
    print(result["answer"])
    print("\n=== 출처 ===")
    print(json.dumps(result["sources"], ensure_ascii=False, indent=2))

    if "error" in result:
        print("\n=== 오류 ===")
        print(result["error"])
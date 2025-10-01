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

    # 4) LLM 프롬프트 작성
    context = "\n\n".join(context_chunks)
    # 5) 모델 호출 (이전 버전)
    # 아래 코드는 GPT 요약을 생성하던 로직입니다. 필요 시 복원할 수 있도록 주석으로 남겨둡니다.
    # prompt = f"""
    # 나는 법령 문서를 참고하여 답하는 법률 상담 챗봇이야.
    # 아래 질문과 참고 문서를 보고, 사용자가 보기 쉽게 답변을 작성해라.
    #
    # 질문:
    # {query}
    #
    # 참고 문서 (각 문단 앞의 번호는 citation 번호):
    # {context}
    # 출력 규칙:
    # 1. 질문에 직접적으로 관련된 핵심만 요약·설명할 것
    # 2. 반드시 **마크다운 형식**으로 작성할 것
    # 3. 법령 조문을 인용할 때 sources 배열의 정보만 사용,
    #    `[법령명 조문번호](URL)` 형태로 링크 달 것
    #    - URL은 반드시 sources 배열의 url과 동일해야 한다.
    #    - 예: "... 안전조치를 해야 한다 [산업안전보건법 제5조](http://www.law.go.kr/...)."
    # 4. 별도의 "참고", "출처" 섹션을 만들지 말고, 본문 안에 자연스럽게 넣을 것
    # """
    #
    # try:
    #     response = client.chat.completions.create(
    #         model=model,
    #         messages=[
    #             {"role": "system", "content": "나는 한국 법령/조문 상담 챗봇이다."},
    #             {"role": "user", "content": prompt}
    #         ]
    #     )
    #     answer_text = response.choices[0].message.content
    # except Exception as e:
    #     return {
    #         "answer": "요약 생성 중 오류가 발생했습니다.",
    #         "sources": sources,
    #         "error": str(e)
    #     }

    # 6) 최종 반환
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

import json
import os
from openai import OpenAI
from qdrant_client import QdrantClient
from law_mapping import make_law_link  # ✅ 출처 링크 생성 함수
import dotenv
dotenv.load_dotenv()
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant = QdrantClient(host="localhost", port=6333)

COLLECTION_NAME = "laws"

def ask(query: str, model: str = "gpt-5-mini", top_k: int = 3, history: str = ""):
    """
    Qdrant에서 관련 법령 검색 후, LLM으로 답변 생성.
    항상 JSON 형식으로 반환:
    {
      "answer": "...",
      "sources": ["산업안전보건기준에관한규칙 제12조 (링크)", ...]
    }
    """

    # 1) Qdrant에서 관련 텍스트 검색
    search_results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=client.embeddings.create(
            model="text-embedding-3-large",
            input=query
        ).data[0].embedding,
        limit=top_k
    )

    # 2) 검색 결과를 컨텍스트/출처로 정리
    sources = []
    context_chunks = []

    for r in search_results:
        payload = r.payload
        law_name = payload.get("law_name", "")
        jo = payload.get("article_number", "")  # 조문번호
        text = payload.get("text", "")

        # ✅ 출처 링크 생성
        link = make_law_link(law_name, jo)

        # 출처 텍스트 구성
        src_text = f"{law_name} 제{jo}조"
        if link:
            src_text += f" ({link})"

        sources.append(src_text)
        context_chunks.append(payload.get("text", ""))

    # LLM에 넘길 컨텍스트
    context = "\n\n".join(context_chunks)

    # 3) LLM 호출 (JSON 출력 강제)
    prompt = f"""
너는 법령 문서를 참고해 답변하는 법률 상담 챗봇이야.
아래 질문과 참고 문서를 보고 반드시 JSON 형식으로만 답변해.

질문:
{query}

참고 문서:
{context}

출력 형식 (반드시 그대로 지켜라):
{{
  "answer": "여기에 자연어 답변을 작성하되, 반드시 문단마다 줄바꿈(\n\n)을 사용하고,
             항목 설명이 여러 개일 경우 번호 목록으로 구분해 가독성을 높여라.",
  "sources": ["법령명 제조문", "법령명 제oo조"]
}}

sources 배열에는 실제 참고한 조문만 넣어라.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "너는 법률 전문가다. 반드시 JSON 형식으로 답변해라."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}  # ✅ JSON 강제 옵션
    )

   # 4) JSON 파싱 (실패 시 fallback)
    try:
        result = json.loads(response.choices[0].message.content)
    except Exception:
        result = {"answer": response.choices[0].message.content}

    # ✅ 모델이 뭐라고 하든 sources는 우리가 만든 sources로 덮어씀
    result["sources"] = sources

    return result["answer"], result["sources"]
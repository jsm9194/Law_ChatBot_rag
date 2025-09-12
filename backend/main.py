# 백엔스 api코드임
# qdrant에서 백터검색하고 gpt로 답변 생성

import os
from fastapi import FastAPI

app = FastAPI()

# 요청/응답 모델 정의
class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    answer: str
    sources: list[dict]

# ----------------------
# 유틸 함수
# ----------------------

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return response.data[0].embedding

def retrieve_from_qdrant(query: str, top_k: int = 5):
    query_vector = get_embedding(query)
    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    return results

def build_prompt(question: str, contexts: list):
    context_texts = []
    for match in contexts:
        payload = match.payload
        context_texts.append(
            f"{payload.get('law_name')} 제{payload.get('article_number')}조 {payload.get('article_title')}\n{payload.get('text')}"
        )
    context_block = "\n\n".join(context_texts)

    prompt = f"""
너는 법령에 근거해서 대답하는 AI야.
아래는 관련 법령 조문이야:

{context_block}

질문: {question}

위 법령만 근거로 해서 답변해. 출처도 반드시 조문과 함께 적어.
"""
    return prompt

# ----------------------
# API 엔드포인트
# ----------------------
@app.post("/ask", response_model=AnswerResponse)
def ask(request: QuestionRequest):
    # 1. Qdrant에서 관련 문서 검색
    results = retrieve_from_qdrant(request.question, top_k=5)

    # 2. GPT 모델 호출
    prompt = build_prompt(request.question, results)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # 속도 빠른 모델 추천
        messages=[{"role": "user", "content": prompt}],
    )

    answer_text = completion.choices[0].message.content

    # 3. 출처 정리
    sources = []
    for match in results:
        payload = match.payload
        sources.append({
            "law_name": payload.get("law_name"),
            "article_number": payload.get("article_number"),
            "article_title": payload.get("article_title"),
        })

    return AnswerResponse(answer=answer_text, sources=sources)

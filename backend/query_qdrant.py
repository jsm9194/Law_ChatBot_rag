import os
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

# .env 불러오기
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

qdrant = QdrantClient("http://localhost:6333")

def ask(query):
    # 쿼리 임베딩
    q_emb = client.embeddings.create(
        input=query,
        model="text-embedding-3-small"
    ).data[0].embedding

    # Qdrant 검색
    results = qdrant.search(
        collection_name="laws",
        query_vector=q_emb,
        limit=10
    )

    # 검색된 컨텍스트 모으기 (출처 포함)
    context = "\n".join(
        [f"[출처: {r.payload['source']}] {r.payload['text']}" for r in results]
    )

    # GPT 호출
    prompt = f"""
    다음은 관련 법령 내용입니다. 출처를 참고해서 질문에 답변해줘.
    {context}

    질문: {query}
    답변:
    """

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return completion.choices[0].message.content

if __name__ == "__main__":
    question = "안전모 착용 의무는 어디에 규정돼 있어?"
    answer = ask(question)
    print("🧑 질문:", question)
    print("🤖 답변:", answer)

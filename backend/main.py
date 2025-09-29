from fastapi import FastAPI, Depends
from pydantic import BaseModel
from openai import OpenAI
import os
import json
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse # 스트리밍식 답변출력

# ✅ DB 관련 import
from sqlalchemy.orm import Session
from DB.database import SessionLocal
from DB.models import ChatLog

# 라우터
from routers import conversations, messages


# 툴 모듈
from query_qdrant import ask as ask_law
from case_api import search_case_list, get_case_detail
from search_goolge import google_search

# 툴 정의 불러오기
from tools_config import tools

app = FastAPI()
app.include_router(conversations.router)
app.include_router(messages.router)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ===============================
# CORS
# ===============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev 서버 주소
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# DB 세션 의존성
# ===============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===============================
# 요청 Body
# ===============================
class Query(BaseModel):
    conversation_id: str
    question: str

# ===============================
# 실제 툴 함수 매핑
# ===============================
def call_tool(name: str, arguments: dict):
    print("⚡ [TOOL CALL]")
    print(f"  📌 실행된 툴: {name}")
    print(f"  📎 전달 인자: {json.dumps(arguments, ensure_ascii=False)}")

    if name == "law":
        result = ask_law(arguments["query"])

    elif name == "search_cases":
        # 상세조회 요청인데 search_cases로 잘못 온 경우 보정
        if "case_id" in arguments:
            # case_id 기반 상세조회
            result = get_case_detail(arguments["case_id"])
        elif "nb" in arguments and not arguments.get("query"):
            # 사건번호(nb)만 들어온 경우 → 상세조회로 보정
            result = get_case_detail(arguments["nb"])
        else:
            # 정상적인 검색 요청
            result = {"cases": search_case_list(**arguments)}

    elif name == "case_detail":
        result = get_case_detail(arguments["case_id"])

    elif name == "web_search":
        result = google_search(
            arguments["query"],
            arguments.get("count", 5),
            arguments.get("time_range", "any")
        )

    else:
        result = {"error": f"Unknown tool: {name}"}

    # ✅ 툴 결과도 로깅
    preview = str(result)
    if len(preview) > 500:  # 너무 길면 자르기
        preview = preview[:500] + " ... (생략)"
    print(f"  ✅ 툴 결과: {preview}\n")

    return result

    
# ===============================
# /ask 엔드포인트 (DB 기반 history 추가)
# ===============================
@app.post("/ask")
def ask_api(query: Query, db: Session = Depends(get_db)):
    print("\n🚀 [ASK 호출됨]")
    print(f"  대화 ID: {query.conversation_id}")
    print(f"  질문: {query.question}\n")

    # ✅ DB에서 최근 10개 로그 불러오기
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.conversation_id == query.conversation_id)
        .order_by(ChatLog.created_at.desc())
        .limit(10)
        .all()
    )
    history_text = "\n".join([f"{log.role}: {log.content}" for log in reversed(logs)])
    print(f"  히스토리: \n{history_text}")

    # ===============================
    # 1차 요청: 툴콜 여부 판단
    # ===============================
    first_response = client.chat.completions.create(
        model="gpt-4o-mini",  # 툴콜 허용 모델
        messages=[
            {
                "role": "system",
                "content": (
                    "너의 임무는 사용자의 질문이 툴 호출이 필요한지 판단하는 것이다.\n\n"
                    "툴 선택 규칙:\n"
                    "- 법령/조문 질문 → 반드시 law 툴 호출\n"
                    "- 판례 질문 → search_cases 또는 case_detail 호출\n"
                    "- 최신 뉴스/웹자료 질문 → web_search 호출\n"
                    "- 그 외 툴이 필요 없는 질문 → 직접 답변\n\n"
                    "툴 호출이 필요한 경우에는 반드시 tool_calls로 반환하고, "
                    "툴이 필요 없으면 직접 답변을 제공한다.\n"
                ),
            },
            {"role": "user", "content": history_text},
            {"role": "user", "content": query.question},
        ],
        tools=tools,
        tool_choice="auto",
    )

    message = first_response.choices[0].message

    # ===============================
    # 툴콜링 여부 확인
    # ===============================
    if message.tool_calls:
        prep_message = message.content or "검색해 정보를 찾아오겠습니다. 잠시만 기다려 주세요."

        tool_results_texts = []
        all_sources = []

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            tool_result = call_tool(name, arguments)

            # 툴 결과 문자열화
            tool_results_texts.append(json.dumps(tool_result, ensure_ascii=False))

            if "sources" in tool_result:
                all_sources.extend(tool_result["sources"])

        # system 프롬프트용 출처 텍스트
        sources_text = "\n".join([
            f"- {s.get('law','')} {s.get('article','')} → {s.get('url','')}"
            for s in all_sources
        ])

        # ===============================
        # 2차 요청: 툴 결과 기반 최종 답변
        # ===============================
        followup = client.chat.completions.create(
            model="gpt-4o-mini",  # followup은 툴콜 금지
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 시설관리 법령·판례·뉴스 상담 챗봇이다.\n\n"
                        "⚠️ 주어진 툴 결과만 활용하여 답변하라. "
                        "새로운 툴 호출은 절대 하지 마라.\n\n"
                        "답변 작성 규칙:\n"
                        "- 뉴스: 기사마다 3문장 이내 핵심 요약 + `[기사 제목](URL)` 형식 링크\n"
                        "- 법령: `[법령명 제oo조](URL)` 형식으로 링크\n"
                        "- 판례: 사건 배경 → 판결 이유 → 결론 순 요약\n"
                        "- 결과 없으면 '관련 자료를 찾을 수 없습니다'라고 답하기\n"
                        "- 문단은 두 줄 간격으로 구분, 불릿/번호목록 적극 활용\n"
                        "- 중요한 키워드는 **굵게** 표시, 🙂 ⚡ 📌 같은 이모지 포인트로 활용\n\n"
                        f"Sources:\n{sources_text}"
                    ),
                },
                {"role": "user", "content": query.question},
                {"role": "assistant", "content": prep_message},
                {
                    "role": "system",
                    "content": "아래는 툴 실행 결과입니다:\n\n" + "\n\n".join(tool_results_texts),
                },
            ],
        )

        return {
            "prep": prep_message,
            "answer": followup.choices[0].message.content,
            "sources": all_sources,
        }

    # ===============================
    # 툴콜링 불필요 → 바로 답변
    # ===============================
    return {"answer": message.content}



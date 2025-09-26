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
# /ask_stream (스트리밍 응답)
# ===============================
@app.post("/ask_stream")
def ask_stream(query: Query, db: Session = Depends(get_db)):

    # ✅ DB에서 최근 대화 기록 가져오기
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.conversation_id == query.conversation_id)
        .order_by(ChatLog.created_at.desc())
        .limit(10)
        .all()
    )
    history_text = "\n".join([f"{log.role}: {log.content}" for log in reversed(logs)])

    # ✅ 모델 호출 (tool_calls 포함)
    first = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 한국 시설관리 법령·판례·뉴스 상담 챗봇이다.\n"
                    "필요하면 툴을 호출하고, 툴 결과를 정리해서 사용자의 질문에 답해라.\n"
                    "- 답변 문단은 두 줄 간격으로 구분\n"
                    "- 법령은 [법령명 제oo조](URL) 형식으로 링크\n"
                    "- 뉴스는 [기사 제목](URL) 형식으로 링크\n"
                    "- 판례는 사건 배경 → 판결 이유 → 결론 순으로 요약\n"
                ),
            },
            {"role": "user", "content": history_text},
            {"role": "user", "content": query.question},
        ],
        tools=tools,
        tool_choice="auto",
    )

    message = first.choices[0].message

    # ✅ 툴콜링이 없을 때 → 바로 스트리밍
    if not message.tool_calls:
        def generate_direct():
            with client.chat.completions.create(
                model="gpt-5-mini",
                stream=True,
                messages=[
                    {"role": "system", "content": "너는 한국 시설관리 법령·판례·뉴스 상담 챗봇이다."},
                    {"role": "user", "content": query.question},
                ],
            ) as response:
                for event in response:
                    delta = event.choices[0].delta
                    if "content" in delta and delta.content:
                        yield json.dumps({"type": "content", "delta": delta.content}) + "\n"

        return StreamingResponse(generate_direct(), media_type="application/jsonl")

    # ✅ 툴 실행 결과 모으기
    tool_results = []
    all_sources = []
    for tool_call in message.tool_calls:
        name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        tool_result = call_tool(name, arguments)

        tool_results.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_result, ensure_ascii=False),
        })

        if "sources" in tool_result:
            all_sources.extend(tool_result["sources"])

    # ✅ 툴 결과 기반 최종 답변 스트리밍
    def generate_followup():
        with client.chat.completions.create(
            model="gpt-5-mini",
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 시설관리 법령·판례·뉴스 상담 챗봇이다.\n"
                        "아래 tool 결과를 활용해 사용자의 질문에 답변을 작성하라.\n"
                        "- 답변 문단마다 관련 출처 번호 인덱스([1], [2])를 붙여라.\n"
                        "- 최종 답변은 반드시 마크다운 문법을 사용하라.\n"
                    ),
                },
                {"role": "user", "content": query.question},
                message,
                *tool_results,
            ],
        ) as response:
            for event in response:
                delta = event.choices[0].delta
                if "content" in delta and delta.content:
                    yield json.dumps({"type": "content", "delta": delta.content}) + "\n"

        yield json.dumps({"type": "sources", "data": all_sources}) + "\n"

    return StreamingResponse(generate_followup(), media_type="application/jsonl")
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from openai import OpenAI
import os
import json
from fastapi.middleware.cors import CORSMiddleware

# ✅ DB 관련 import
from sqlalchemy.orm import Session
from DB.database import SessionLocal
from DB.models import ChatLog

# 라우터
from routers import conversations, messages

# 툴 모듈
from query_qdrant import ask as ask_law
from case_api import search_case_list, get_case_detail

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
# 툴 정의
# ===============================
tools = [
    {
        "type": "function",
        "function": {
            "name": "law",
            "description": (
                "법령 검색 툴. "
                "사용자가 특정 조문, 규정, 의무, 시설 기준(예: 계단, 난간, 환기, 조명, 보호구, 화재예방 등)에 대해 물어볼 때 사용. "
                "법령/조문/규정/법률명과 관련된 질문은 반드시 law 툴을 호출해서 Qdrant 검색 결과를 활용하라."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_cases",
            "description": "판례 검색 툴. 사건/판결/처벌 사례 질문 시 사용.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {"type": "integer", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "case_detail",
            "description": "판례 상세 조회 (사건 ID 기반). search_cases 결과의 case_id 필요.",
            "parameters": {
                "type": "object",
                "properties": {"case_id": {"type": "string"}},
                "required": ["case_id"],
            },
        },
    },
]

# ===============================
# 실제 툴 함수 매핑
# ===============================
def call_tool(name: str, arguments: dict):
    print(f"⚡ call_tool 실행됨: {name}, {arguments}")
    if name == "law":
        return ask_law(arguments["query"])
    elif name == "search_cases":
        return search_case_list(arguments["query"], arguments.get("count", 5))
    elif name == "case_detail":
        return get_case_detail(arguments["case_id"])
    else:
        return {"error": f"Unknown tool: {name}"}

# ===============================
# /ask 엔드포인트 (DB 기반 history 추가)
# ===============================
@app.post("/ask")
def ask_api(query: Query, db: Session = Depends(get_db)):
    # ✅ DB에서 최근 10개 로그 불러오기
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.conversation_id == query.conversation_id)
        .order_by(ChatLog.created_at.desc())
        .limit(10)
        .all()
    )
    history_text = "\n".join([f"{log.role}: {log.content}" for log in reversed(logs)])

    # 1차 요청: 모델이 툴콜링 여부 결정
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "너는 한국 시설관리 법령 및 판례 상담 챗봇이다.\n"
                    "⚠️ 반드시 아래 규칙을 지켜라:\n"
                    "1. 법령/조문/규정/법률명 질문 → 무조건 law 툴 호출\n"
                    "2. 판례 검색 요청 → search_cases 툴 호출\n"
                    "3. 사건 ID 판례 상세 → case_detail 툴 호출\n"
                    "4. 스스로 추측 금지, 반드시 툴을 사용\n"
                ),
            },
            {"role": "user", "content": history_text},
            {"role": "user", "content": query.question},
        ],
        tools=tools,
        tool_choice="auto",
    )

    message = response.choices[0].message

    # 모델이 툴콜링 요청을 했는지 확인
    if message.tool_calls:
        tool_call_results = []
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            tool_result = call_tool(name, arguments)

            tool_call_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        # 2차 요청: 툴 결과를 포함해 최종 답변 생성
        followup = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 시설관리 법령 및 판례 상담 챗봇이다.\n\n"
                        "답변 규칙:\n"
                        "1. 법령/조문 질문 → 툴에서 제공한 context로 답변\n"
                        "2. 답변 끝마다 반드시 [법령명 제oo조] 형식으로 출처 표시\n"
                        "3. 같은 조문 반복 인용 시에도 항상 표시\n"
                        "4. 출처는 tool에서 제공된 sources와 일치해야 함"
                    ),
                },
                {"role": "user", "content": query.question},
                message,  # 모델의 tool_calls 메시지
                *tool_call_results,
            ],
        )

        return {
            "answer": followup.choices[0].message.content,
            "sources": [
                json.loads(t["content"]).get("sources", [])
                for t in tool_call_results
            ],
        }

    # 툴콜링이 필요 없을 때 바로 답변
    return {"answer": message.content}

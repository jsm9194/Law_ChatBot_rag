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
from search_goolge import google_search

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
            "description": "판례 검색 툴. 사건명, 사건번호, 법원, 선고일자 등 다양한 조건으로 판례를 검색한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어 (사건명/본문 등)"},
                    "search": {"type": "integer", "enum": [1,2], "default": 1, "description": "검색 범위 (1=사건명, 2=본문)"},
                    "count": {"type": "integer", "default": 5, "description": "검색 결과 개수 (최대 100)"},
                    "page": {"type": "integer", "default": 1, "description": "페이지 번호"},
                    "org": {"type": "string", "description": "법원종류 (대법원:400201, 하위법원:400202)"},
                    "curt": {"type": "string", "description": "법원명 (대법원, 서울고등법원 등)"},
                    "nb": {"type": "string", "description": "사건번호 (예: 94누5496)"},
                    "prncYd": {"type": "string", "description": "선고일자 범위 (예: 20090101~20090130)"},
                    "JO": {"type": "string", "description": "참조법령명 (예: 형법, 민법)"},
                    "datSrcNm": {"type": "string", "description": "데이터출처명 (예: 근로복지공단산재판례)"},
                    "sort": {"type": "string", "enum": ["lasc","ldes","dasc","ddes","nasc","ndes"], "description": "정렬옵션"}
                }
            }
        }
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
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Google Custom Search 기반 웹 검색 툴. "
                "최신 뉴스, 나무위키, 법제처 등 자료를 검색할 때 사용. "
                "검색 정확도를 위해 site:, filetype:, intitle:, OR, -제외어 같은 Google 연산자도 활용 가능."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 키워드 (Google 연산자 사용 가능)"
                    },
                    "count": {
                        "type": "integer",
                        "default": 5,
                        "description": "가져올 검색 결과 개수 (최대 10)"
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["any", "day", "week", "month", "year"],
                        "default": "any",
                        "description": "검색 기간 제한"
                    },
                },
                "required": ["query"],
            },
        },
    }
]

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
        result = {"cases": search_case_list(arguments["query"], arguments.get("count", 5))}
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

    # 1차 요청: 모델이 툴콜링 여부 판단
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "너의 임무는 사용자의 질문이 툴 호출이 필요한지 판단하는 것이다.\n"
                    "- 법령/조문 질문 → 반드시 law 툴 호출\n"
                    "- 판례 질문 → search_cases 또는 case_detail 툴 호출,\n"
                    "불필요한 파라미터는 넣지 말고, 사용자의 요청에 해당하는 값만 사용하라."
                    
                    "- 최신 뉴스/웹자료 질문 → web_search 툴 호출\n"
                    "- 그 외 툴이 필요 없는 일반 질문 → 직접 자연스럽게 답변\n\n"
                    "툴 호출이 필요한 경우에는 반드시 tool_calls로 반환하고, "
                    "툴이 필요 없으면 직접 답변을 제공하라."
                    "답변 작성 규칙:"
                        "세부 제목은 반드시 단독 줄에서 굵게 표시하고, 그 다음 줄에 본문을 작성해라."
                        "1. 문단, 세부내용은 반드시 두 줄 간격(\n\n)으로 구분해라."
                        "2. 항목은 번호 목록(1., 2., 3.) 또는 불릿(-)으로 정리해라."
                        "3. 중요한 키워드는 **굵게** 표시해라."
                        "4. 필요할 경우 중간에 구분선(---)을 사용 구분선 전후로 두줄간격(\n\n)해라."
                        "5. 적절한 위치에 🙂, ⚡, 📌 같은 이모지를 사용해라. (너무 많이 말고 포인트에만)"
                        "6. 여러개를 나열할때는 불릿(-) 으로 정리하라"
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
        all_sources = []  # 모든 툴에서 모은 sources 저장

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            tool_result = call_tool(name, arguments)

            tool_call_results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })

            if "sources" in tool_result:
                all_sources.extend(tool_result["sources"])

        # system 프롬프트에 주입할 출처 텍스트
        sources_text = "\n".join([
            f"- {s['law']} {s['article']} → {s['url']}"
            for s in all_sources
        ])

        # 2차 요청: 툴 결과를 포함해 최종 답변 생성
        followup = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 시설관리 법령·판례·뉴스 상담 챗봇이다.\n\n"
                        "답변 원칙:\n"
                        "1. 툴 결과를 그대로 나열하지 말고, 사용자의 질문 의도에 맞게 요약·정리한다.\n\n"
                        "2. 뉴스/웹자료 질문:\n"
                        "- 기사마다 1~2문장으로 핵심 요약\n"
                        "- 출처는 반드시 `📎 [기사 제목](URL)` 형식으로 넣을 것\n"
                        "- URL은 직접 보이지 않게 하고, 기사 제목을 클릭하면 열리도록 한다\n\n"
                        "3. 법령/판례 질문:\n"
                        "- 법령 → 아래 sources 목록의 URL을 반드시 인용해라.\n"
                        f"Sources:\n{sources_text}\n\n"
                        "- 법령 인용 시 `[법령명 제oo조](URL)` 형식으로 링크 달기\n"
                        "툴 결과에 '판례전문'이나 '판결요지'가 있으면 반드시 사건 배경 → 판결 이유 → 결론 순으로 요약하라.\n"
                        
                        "답변 작성 규칙:"
                        "1. 문단 세부내용은 반드시 두 줄 간격(\n\n)으로 구분해라."
                        "2. 항목은 번호 목록(1., 2., 3.) 또는 불릿(-)으로 정리해라."
                        "3. 중요한 키워드는 **굵게** 표시해라."
                        "4. 필요할 경우 중간에 구분선(---) 구분선 전후로 줄바꿈 두번(\n\n)을 사용해라."
                        "5. 적절한 위치에 🙂, ⚡, 📌 같은 이모지를 사용해라. (너무 많이 말고 포인트에만)"
                        "6. 여러개를 나열할때는 불릿(-) 으로 정리하라"
                        "4. 항상 마크다운 형식으로 답해 가독성을 높여라.\n"
                        "5. 툴 결과가 없으면 '관련 자료를 찾을 수 없습니다'라고 답하라."
                        "세부 제목은 반드시 단독 줄에서 굵게 표시하거나 마크다운 소제목(# ## ###)를 활용하라, 그 다음 줄에 본문을 작성해라."
                    ),
                },
                {"role": "user", "content": query.question},
                message,  # 모델의 tool_calls 메시지
                *tool_call_results,
            ],
        )

        return {
            "answer": followup.choices[0].message.content,
            "sources": all_sources,  # ✅ sources 배열 그대로 반환
        }

    # 툴콜링이 필요 없을 때 바로 답변
    return {"answer": message.content}
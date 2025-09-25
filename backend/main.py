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
    # 1차 요청: 모델이 툴콜링 여부 판단
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                "너의 임무는 사용자의 질문이 툴 호출이 필요한지 판단하는 것이다.\n\n"
                "툴 선택 규칙:\n"
                "- 법령/조문 질문 → 반드시 law 툴 호출\n"
                "- 판례 질문 → "
                "- 사용자가 새로운 판례를 찾으려 하면 → search_cases 호출"
                "- 이미 제시된 판례 목록 중 특정 사건(사건번호/사건명/‘첫 번째’, ‘마지막’ 등)을 골라 상세 요약 요청 시 → 반드시 case_detail 호출"
                "- search_cases 결과를 다시 반복 호출하지 말 것"
                "  (불필요한 파라미터는 넣지 말고, 사용자의 요청에 해당하는 값만 사용한다)\n"
                "- 최신 뉴스/웹자료 질문 → web_search 툴 호출\n"
                "- 그 외 툴이 필요 없는 일반 질문 → 직접 자연스럽게 답변\n\n"
                "툴 호출이 필요한 경우에는 반드시 tool_calls로 반환하고, "
                "툴이 필요 없으면 직접 답변을 제공한다.\n\n"
                "답변 작성 규칙:\n"
                "1. 세부 제목은 반드시 단독 줄에서 굵게 표시하고, 그 다음 줄에 본문을 작성한다.\n"
                "2. 문단·세부 내용은 반드시 두 줄 간격(\\n\\n)으로 구분한다.\n"
                "3. 항목은 번호 목록(1., 2., 3.) 또는 불릿(-)으로 정리한다.\n"
                "4. 중요한 키워드는 **굵게** 표시한다.\n"
                "5. 필요할 경우 중간에 구분선(---)을 사용하고, 구분선 전후로 두 줄 간격을 둔다.\n"
                "6. 여러 개를 나열할 때는 불릿(-)으로 정리한다.\n\n"
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
        prep_message = message.content or "검색해 정보를 찾아오겠습니다. 잠시만 기다려 주세요."

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

        # ✅ assistant 메시지에 prep_message + tool_calls 같이 넘기기
        assistant_tool_message = {
            "role": "assistant",
            "content": prep_message,
            "tool_calls": message.tool_calls,
        }

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
                        "- 출처는 반드시 `[기사 제목](URL)` 형식으로 넣을 것\n"
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
                assistant_tool_message,
                *tool_call_results,

            ],
        )

        return {
            "prep": prep_message,  
            "answer": followup.choices[0].message.content,
            "sources": all_sources,  # ✅ sources 배열 그대로 반환
        }
    # 툴콜링이 필요 없을 때 바로 답변
    return {"answer": message.content}
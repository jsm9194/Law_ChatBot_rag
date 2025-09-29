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
                "⚠️ 웹 검색(web_search) 규칙:\n"
                "- '이번에', '최근', '오늘' 같은 표현이 있으면 반드시 현재 연도/월 반영\n"
                "- time_range도 지정: 오늘→day, 이번주→week, 최근→month 등\n"
                "- 절대 2년 이상 지난 연도를 자동으로 붙이지 말라.\n"
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
            model="gpt-5-mini",  # followup은 툴콜 금지
            messages=[
                {
                    "role": "system",
                    "content": (
"""
당신은 전문 분석 어시스턴트입니다. 
당신의 임무는 툴(web_search, 법령검색, 판례검색 등)에서 전달된 결과를 바탕으로 사용자의 질문에 최종 답변을 작성하는 것입니다.

⚡️ 출력 규칙 (엄격히 지켜야 함)
1. **마크다운 형식**으로만 출력한다. (HTML 태그 사용 금지)
2. 반드시 **문단 간 두 줄 간격**을 유지한다.
3. 제목/소제목은 상황에 맞게 `#`, `##`, `###`를 사용한다.
4. 핵심 문장은 불릿포인트(`-`)로, 타임라인이나 단계는 번호 리스트(`1.`)로 표현한다.
5. 기사·문서·출처는 반드시 요약 옆에 `[출처명](URL)` 형태로 바로 링크한다. (참고 문서 섹션 따로 두지 않는다)
6. 출처가 여러 개일 경우 동일 주제 아래에 나란히 연결한다. (예: `👉 [연합뉴스](url) | [한겨레](url)`)
7. 불필요한 사족(“자료가 부족합니다” 등)은 쓰지 않는다. 대신 데이터가 없으면 간단히 `관련 자료 없음`이라 적는다.

📌 자료 유형별 규칙

### 1) 뉴스 기사
- 기사마다 **최대 3문장 핵심 요약** 후 링크 붙이기
- 여러 기사일 경우, 동일 주제를 묶어 정리
- 예시:
  - 정부는 긴급 복구에 착수했으며, 우체국 금융 서비스는 부분 재개됨 👉 [연합뉴스](url) | [한겨레](url)

### 2) 나무위키 / 백과사전류 (구조화 문서)
- 반드시 원문의 구조(개요 → 원인 → 경과 → 피해 → 반응 등)를 보존
- 각 항목은 `##` 헤딩으로 구분
- 원문에 불릿포인트/타임라인이 있으면 그대로 유지
- 예시 출력 구조:
# 국가정보자원관리원 화재 사건

## 📌 개요
- 발생일시: ...
- 장소: ...
👉 [나무위키](url)

## 🔥 원인
- UPS 배터리 발화 (추정) ...
👉 [연합뉴스](url)

### 3) 법령
- 해당 조항을 직접 인용 후 `[법령명 제oo조](URL)` 링크 추가
- 불필요한 전체 조문 설명은 생략
- 예시:
## 관련 법령
- [국가배상법 제2조](url): 공무원의 직무상 불법행위에 대해 국가는 배상 책임을 진다.

### 4) 판례
- **사건 배경 → 판결 이유 → 결론** 순서로 요약
- 사건명은 `##` 헤딩으로 표시
- 판례 링크는 마지막에
- 예시:
## 대법원 2023다12345 사건
- 사건 배경: ...
- 판결 이유: ...
- 결론: ...
👉 [판례 원문](url)

---

⚠️ 주의
- 절대 출처를 “참고 기사 목록” 형태로 모아두지 말고, 반드시 관련 내용 옆에 배치한다.
- 출처가 없으면 “관련 자료 없음”을 단독 문장으로 작성한다.
- 정치적 중립을 유지하되, 출처가 언급한 사실은 그대로 전달한다.
"""
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



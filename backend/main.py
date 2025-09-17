from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os
import json
from fastapi.middleware.cors import CORSMiddleware 
from query_qdrant import ask as ask_law
from case_api import search_case_list, get_case_detail
app = FastAPI()

# DB 라우터 연결
from routers import conversations, messages
app.include_router(conversations.router)
app.include_router(messages.router)
# ===============================



client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev 서버 주소 (개발 단계)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# 요청 Body
# ===============================
class Query(BaseModel):
    question: str
    history: str = ""

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
                "산업안전보건법, 재난안전법, 중대재해처벌법 등 안전/보건/재난 관련 법령 전반을 검색할 수 있음. "
                "예시: '계단에 관한 규정이 있나?', '산업안전보건법 제24조 알려줘', '환기 기준이 뭐야?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_cases",
            "description": (
                "판례 검색 툴. "
                "사용자가 실제 사건, 처벌 사례, 법원 판결 내용을 물어볼 때 사용. "
                "중대재해처벌법, 산업안전보건법 등 위반 사례를 검색할 수 있음. "
                "예시: '대표이사가 중대재해처벌법 위반으로 처벌된 사례 있어?', "
                "'산업안전보건법 위반 판례 알려줘', '추락사고 관련 판례 있나?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {"type": "integer", "default": 3}
                },
                "required": ["query"]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "case_detail",
        "description": (
            "판례 상세 조회 (사건 ID 기반). "
            "반드시 search_cases 결과에서 받은 사건ID(case_id)를 사용해 호출해야 한다. "
            "예시: 'case_id가 2023001234인 판례 상세 알려줘', "
            "'사건ID 2022005678 판결요지 보여줘', "
            "'case_id 2021009101 판례전문 읽어줘'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"}
            },
            "required": ["case_id"]
            }
        }
    }
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
# API 엔드포인트
# ===============================
@app.post("/ask")
def ask_api(query: Query):
    # 1차 요청: 모델이 어떤 툴을 호출할지 결정
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "너는 한국 시설관리 법령 및 판례 상담 챗봇이다.\n"
                "⚠️ 반드시 아래 규칙을 지켜라:\n"
                "1. 사용자가 법령/조문/규정/법률명과 관련된 질문을 하면 무조건 law 툴을 호출해야 한다.\n"
                "2. 특히 다음 법령과 관련된 질문은 반드시 law 툴을 호출해라:\n"
                "   - 산업안전보건기준에관한규칙 \n"
                "   - 산업안전보건법 \n"
                "   - 산업안전보건법시행규칙 \n"
                "   - 산업안전보건법시행령 \n"
                "   - 재난및안전관리기본법 \n"
                "   - 재난및안전관리기본법시행규칙 \n"
                "   - 재난및안전관리기본법시행령 \n"
                "   - 중대재해처벌등에관한법률 \n"
                "   - 중대재해처벌등에관한법률시행령 \n"
                "3. 법령/조문이 아닌 판례 검색 요청은 search_cases 툴을 호출해야 한다.\n"
                "4. 특정 사건 ID에 대한 판례 상세 요청은 case_detail 툴을 호출해야 한다.\n"
                "5. 어떤 경우에도 너 스스로 지식으로 답을 추측하지 말고, 반드시 적절한 툴을 호출해야 한다."
            )},
            {"role": "user", "content": query.question}
        ],
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message

    # 모델이 툴콜링 요청을 했는지 확인
    if message.tool_calls:
        tool_call_results = []
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            tool_result = call_tool(name, arguments)

            # 툴 실행 결과를 messages에 연결
            tool_call_results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result, ensure_ascii=False)
            })

        # 2차 요청: 툴 결과를 기반으로 최종 답변 생성
        followup = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "system",
                      "content": (
                        "너는 한국 시설관리 법령 및 판례 상담 챗봇이다.\n\n"
                        "답변할 때는 반드시 다음 규칙을 지켜라:\n"
                        "1. 법령/조문/규정 관련 질문일 경우, 툴에서 제공된 context를 활용해 답변해야 한다.\n"
                        "2. 답변은 자연스럽게 설명하되, 문장이나 문단 끝마다 반드시 [법령명 제oo조] 형식으로 출처를 붙여라.\n"
                        "   예: '중대재해처벌법은 사업주와 경영책임자에게 의무를 부과한다【중대재해처벌등에관한법률 제1조】.'\n"
                        "3. 같은 조문을 여러 번 인용할 경우에도 반복해서 표시한다.\n"
                        "4. 출처는 반드시 tool에서 제공된 sources와 일치해야 한다."
                    )
                },
                {"role": "user", "content": query.question},
                message,  # 모델의 tool_calls 메시지
                *tool_call_results
            ]
        )


        return {
        "answer": followup.choices[0].message.content,
        "sources": [
            json.loads(t["content"]).get("sources", [])
            for t in tool_call_results
            ]
        }

    else:
        # 툴콜링이 필요 없을 때 바로 답변
        return {"answer": message.content}

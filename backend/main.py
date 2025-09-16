from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os
import json
from fastapi.middleware.cors import CORSMiddleware 
from query_qdrant import ask as ask_law
from case_api import search_case_list, get_case_detail

app = FastAPI()
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
    }
]


# ===============================
# 실제 툴 함수 매핑
# ===============================
def call_tool(name: str, arguments: dict):
    print(f"⚡ call_tool 실행됨: {name}, {arguments}")
    if name == "law":
        answer, sources = ask_law(arguments["query"])
        return {"answer": answer, "sources": sources}

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
            {"role": "system", "content": "너는 한국 시설관리 법령 및 판례 상담 챗봇이다."},
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
                {"role": "system", "content": "너는 한국 시설관리 법령 및 판례 상담 챗봇이다."},
                {"role": "user", "content": query.question},
                message,  # 모델의 tool_calls 메시지
                *tool_call_results
            ]
        )

        return {"answer": followup.choices[0].message.content}

    else:
        # 툴콜링이 필요 없을 때 바로 답변
        return {"answer": message.content}

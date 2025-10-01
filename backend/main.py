from fastapi import FastAPI, Depends, Request
from pydantic import BaseModel
from openai import OpenAI
import os
import json
import traceback
from typing import Iterator, List, Dict, Any, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

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

# 툴 정의 불러오기 (Chat Completions용 function-calling 스키마)
from tools_config import tools

# 쿼리에 날짜
from datetime import datetime

# ===============================
# 앱 & 클라이언트
# ===============================
app = FastAPI()
app.include_router(conversations.router)
app.include_router(messages.router)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VALID_MESSAGE_ROLES = {"system", "assistant", "user", "tool", "function", "developer"}

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


# 날짜 불러오기
def get_current_datetime() -> str:
    """현재 날짜와 시간을 YYYY-MM-DD HH:MM 형식으로 반환"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")



# ===============================
# 쿼리 최적화 프롬프트
# ===============================
QUERY_OPTIMIZATION_SYSTEM = """
당신은 검색 쿼리 최적화 전문가입니다.  
사용자의 자연어 질문을 받아, 구글 검색에서 최상의 결과를 얻을 수 있는 검색 쿼리 세트를 한국어와 영어로 변환해주세요.  
현재 2025년 10월 입니다.

규칙:  
1. 한국어 쿼리와 영어 쿼리를 모두 생성하세요.  
2. 각 언어별로 최소 5개 이상의 쿼리를 만들어주세요.  
   - 뉴스/시사 관련 쿼리  
   - 위키/백과사전용 쿼리  
   - 해외 언론(Reuters, NYT, TIME 등)용 쿼리  
   - 기술/전문 자료용 쿼리  
   - 최신 정보(최근/올해 등 포함)  
3. 쿼리는 짧고 명확하게 (2~6 단어) 작성하세요.  
4. 불필요한 조사/접속사는 제거하세요.  
5. 결과는 JSON으로 출력하되 아래 형식을 따르세요.  

출력 형식 (예시):
{
  "ko": ["카카오톡 롤백", "카카오톡 업데이트 논란", "카카오톡 피드백", "카카오톡 최근 뉴스", "카카오톡 사용자 반발"],
  "en": ["KakaoTalk rollback", "KakaoTalk update controversy", "KakaoTalk user backlash", "KakaoTalk latest news", "KakaoTalk criticism Reuters"]
}
"""

def optimize_search_query(question: str) -> List[str]:
    """사용자 질문을 검색에 최적화된 쿼리로 변환"""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",  # 또는 당신이 사용하는 모델
            messages=[
                {"role": "system", "content": QUERY_OPTIMIZATION_SYSTEM},
                {"role": "user", "content": question}
            ],
            temperature=0.3,  # 일관된 결과를 위해 낮은 temperature
        )
        
        result = response.choices[0].message.content
        # JSON 파싱 시도
        try:
            queries = json.loads(result)
            if isinstance(queries, dict) and "ko" in queries and "en" in queries:
                return queries
            
            if isinstance(queries, list) and len(queries) > 0:
                return {"ko": queries, "en": []}
        except:
            print(f"쿼리 최적화 결과 파싱 실패: {result}")
            
    except Exception as e:
        print(f"쿼리 최적화 오류: {str(e)}")
    
    # 실패 시 원래 질문을 그대로 리턴
    return {"ko": [question], "en": []}

# ===============================
# 검색 결과 리랭킹 프롬프트
# ===============================
SEARCH_RERANKING_SYSTEM = """
당신은 검색 결과 평가 전문가입니다.  
사용자의 질문(한국어일 수도 있고 영어일 수도 있음)과 검색 결과 목록(한국어와 영어가 섞여 있을 수 있음)을 받아, 질문과 가장 관련성 높은 결과들을 선별하세요.  

규칙:  
1. 질문이 한국어라도 영어 결과를 무시하지 마세요. 제목/스니펫이 의미적으로 관련 있다면 높은 점수를 주세요.  
2. 각 검색 결과의 제목과 스니펫을 분석해, 질문 의도와의 의미적 유사도를 평가하세요.  
3. 한국어/영어 결과 중복은 제거하세요. (같은 내용을 다룬다면 하나만 선택)  
4. 최신 정보를 우선시하세요. (출판일이 언급된 경우 최근 것을 우선)  
5. 필요하면 영어를 한국어로 번역해 의미를 이해한 뒤 관련성을 평가하세요.  

출력 형식은 관련성이 높은 결과들의 인덱스만 JSON 배열로 반환하세요:
[0, 2, 5]

다른 설명이나 부가 정보 없이 오직 JSON 배열만 출력하세요.
"""

def rerank_search_results(question: str, search_results: List[Dict]) -> List[Dict]:
    """검색 결과를 질문 관련성에 따라 리랭킹"""
    try:
        # 검색 결과가 너무 적으면 그대로 반환
        if len(search_results) <= 5:
            return search_results
            
        # 검색 결과를 텍스트로 변환
        results_text = []
        for i, result in enumerate(search_results):
            title = result.get("title", "제목 없음")
            snippet = result.get("snippet", "내용 없음")
            results_text.append(f"[{i}] 제목: {title}\n내용: {snippet}")
        
        all_results = "\n\n".join(results_text)
        
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SEARCH_RERANKING_SYSTEM},
                {"role": "user", "content": f"질문: {question}\n\n검색 결과:\n{all_results}"}
            ],
            temperature=0.2,
        )
        
        result = response.choices[0].message.content
        # JSON 파싱 시도
        try:
            indices = json.loads(result)
            if isinstance(indices, list) and len(indices) > 0:
                # 인덱스로 결과 필터링
                return [search_results[i] for i in indices if i < len(search_results)]
        except:
            print(f"리랭킹 결과 파싱 실패: {result}")
            pass
            
    except Exception as e:
        print(f"리랭킹 오류: {str(e)}")
    
    # 실패 시 원래 결과 그대로 리턴 (최대 5개)
    return search_results[:min(5, len(search_results))]

# ===============================
# 향상된 웹 검색 함수
# ===============================
def enhanced_web_search(query: str, count: int = 8, time_range: str = "any"):
    """쿼리 최적화 및 결과 리랭킹을 적용한 향상된 웹 검색"""
    # 1. 쿼리 최적화
    optimized_queries = optimize_search_query(query)
    print(f"  🔍 최적화된 쿼리: {optimized_queries}")
    
    all_results = []

    merged_queries = optimized_queries.get("ko", []) + optimized_queries.get("en", [])

    # 2. 각 최적화된 쿼리로 검색 실행
    for opt_query in merged_queries:  # ✅ 이제 여기서 슬라이싱 에러 안 남
        results = google_search(opt_query, count, time_range)
        if isinstance(results, list):
            all_results.extend(results)
        elif isinstance(results, dict) and "results" in results:
            all_results.extend(results["results"])
    
    # 3. 결과 리랭킹
    if all_results:
        reranked_results = rerank_search_results(query, all_results)
        print(f"  📊 리랭킹 후 결과 수: {len(reranked_results)}")
        return {"results": reranked_results}
    
    # 결과가 없으면 원래 쿼리로 검색
    return google_search(query, count, time_range)

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
        if "case_id" in arguments:
            result = get_case_detail(arguments["case_id"])
        elif "nb" in arguments and not arguments.get("query"):
            result = get_case_detail(arguments["nb"])
        else:
            result = {"cases": search_case_list(**arguments)}

    elif name == "case_detail":
        result = get_case_detail(arguments["case_id"])

    elif name == "web_search":
        # ⭐⭐⭐ 기존 google_search 대신 enhanced_web_search 사용 ⭐⭐⭐
        result = enhanced_web_search(
            arguments["query"],
            arguments.get("count", 8), # enhanced_web_search 내부에서 검색 쿼리별로 더 많은 결과 탐색
            arguments.get("time_range", "any")
        )

    else:
        result = {"error": f"Unknown tool: {name}"}

    # ✅ 툴 결과도 로깅(미리보기)
    preview = str(result)
    if len(preview) > 500:
        preview = preview[:500] + " ... (생략)"
    print(f"  ✅ 툴 결과: {preview}\n")
    return result

# ===============================
# 유틸: SSE 포맷
# ===============================
def _sse(event: str, data: Any) -> str:
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    lines = data.splitlines()
    if not lines:
        lines = [""]
    formatted_data = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{formatted_data}\n\n"

# ===============================
# 유틸: 팔로업 메시지 구성
# ===============================
FOLLOWUP_SYSTEM = """
당신은 전문 분석 어시스턴트입니다.  
아래 규칙을 반드시 따라 최종 답변을 작성하세요.

⚡ 출력 규칙 (엄격히 지켜야 함)
1. 반드시 **Markdown 형식**만 사용 (HTML, 버튼, 이모지, '출처', '바로가기' 같은 표현 금지).
2. 답변은 항상 두 섹션으로 작성:
   ## 관련 법률 요약
   - **법령명 (제XX조)**  
     설명 한 줄  
     [출처](URL)

   - 동일 법령의 여러 조문도 위와 같이 각각 불릿·줄바꿈
3. ## 사업장 안전관리 핵심 조치  
   1. 번호 리스트로 작성  
   2. 각 항목은 짧은 문장으로 기술  
   3. 항목 사이 반드시 줄바꿈 유지
4. 링크는 반드시 `[출처](URL)` 형식으로만 표시.  
   다른 표현(예: '출처:', '바로가기', URL 단독)은 절대 금지.
5. 문단·불릿·번호 리스트 사이에는 빈 줄 한 줄 반드시 넣을 것.
"""

def build_followup_messages(
    question: str,
    prep_message: str,
    tool_results_texts: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": FOLLOWUP_SYSTEM},
        {"role": "user", "content": question},
    ]
    # 모델 컨텍스트를 안정화하기 위해 'assistant preface' 를 명시적으로 넣어준다.
    if prep_message:
        messages.append({"role": "assistant", "content": prep_message})

    if tool_results_texts:
        joined = "아래는 툴 실행 결과입니다:\n\n" + "\n\n".join(tool_results_texts)
        messages.append({"role": "system", "content": joined})
    return messages

# ===============================
# 핵심: /ask 엔드포인트
#  - Accept 헤더가 text/event-stream이면 SSE 스트리밍
#  - 아니면 JSON 응답(기존 호환)
# ===============================
@app.post("/ask")
def ask_api(query: Query, request: Request, db: Session = Depends(get_db)):
    print("\n🚀 [ASK 호출됨]")
    print(f"  대화 ID: {query.conversation_id}")
    print(f"  질문: {query.question}\n")

    # ✅ DB에서 최근 10개 로그 불러오기 (최신 10개)
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.conversation_id == query.conversation_id)
        .order_by(ChatLog.created_at.desc())
        .limit(10)
        .all()
    )
    # 로그를 뒤집어서 시간 순서대로 정렬
    history_messages: List[Dict[str, str]] = []
    for log in reversed(logs):
        normalized_role = (log.role or "").strip().lower()
        if normalized_role not in VALID_MESSAGE_ROLES:
            print(
                "  ⚠️ 대화 로그 무시 (유효하지 않은 role)",
                {"id": getattr(log, "id", None), "role": log.role},
            )
            continue

        content = log.content or ""
        if not content.strip():
            print(
                "  ⚠️ 대화 로그 무시 (빈 content)",
                {"id": getattr(log, "id", None)},
            )
            continue

        history_messages.append({"role": normalized_role, "content": content})
    
    # 히스토리 텍스트 출력 (디버깅용)
    print("  === 과거 대화 로그 ===")
    for msg in history_messages:
        print(f"  {msg['role']}: {msg['content']}")
    print("  ====================")


    # ===============================
    # 1차: 툴콜 여부 판단 (Chat Completions)
    #  - 스트리밍 불필요, 빠르게 의사결정
    # ===============================
    # 과거 대화 로그를 툴 호출 판단에도 활용
    messages_for_tool_call = history_messages + [
        {
            "role": "system",
            "content": 
            """당신은 사용자의 질문에 답하기 위해 필요한 도구를 선택하는 전문가입니다.  
필요하다면 여러 개의 도구를 동시에 호출할 수도 있습니다.  
불필요한 도구는 호출하지 마세요.""",
        },
        {"role": "user", "content": query.question},
    ]

    first = client.chat.completions.create(
        model="gpt-4.1-mini",  # 툴 콜 정확도를 위해 gpt-4o 사용 추천
        messages=messages_for_tool_call,
        tools=tools,
        tool_choice="auto", # auto는 모델이 판단하도록 함
    )

    # 툴 호출이 필요한지 판단
    tool_calls = first.choices[0].message.tool_calls
    # 첫 응답 메시지가 툴 호출 없이 바로 컨텐츠를 포함할 수도 있음
    prep_message = first.choices[0].message.content or "" 

    # ===============================
    # 스트리밍 응답 준비 (Accept 헤더에 따라)
    # ===============================
    is_streaming = "text/event-stream" in request.headers.get("accept", "")

    # 스트리밍이 아니면 기존 JSON 응답 방식
    if not is_streaming:
        # ===============================
        # 비스트리밍 응답 로직 (기존 호환)
        # ===============================
        tool_results = []
        tool_results_texts = []

        if tool_calls:
            print("  [비스트리밍] 툴 호출 실행 중...")
            for tc in tool_calls:
                try:
                    tool_name = tc.function.name
                    args = json.loads(tc.function.arguments)
                    tool_result = call_tool(tool_name, args)
                    tool_results.append(tool_result)
                    tool_results_texts.append(f"[{tool_name}] 결과:\n{json.dumps(tool_result, ensure_ascii=False)}")
                except Exception as e:
                    print(f"  [비스트리밍] 툴 호출 오류: {str(e)}")
                    traceback.print_exc()

        # 팔로업 메시지 구성
        # 과거 대화 로그도 함께 전달하여 최종 답변 생성
        final_messages = history_messages + build_followup_messages(
            query.question, prep_message, tool_results_texts
        )

        # 최종 답변 생성
        completion = client.chat.completions.create(
            model="gpt-4.1-mini", # 최종 답변도 gpt-4o 사용 추천
            messages=final_messages,
        )
        answer = completion.choices[0].message.content

        # DB에 저장
        db.add(
            ChatLog(
                conversation_id=query.conversation_id,
                user_id="assistant",  # AI의 응답이므로 role은 assistant
                content=answer,
            )
        )
        db.commit()

        return {
            "answer": answer,
            "sources": tool_results,
        }

    # ===============================
    # 스트리밍 응답 로직 (SSE)
    # ===============================
    from typing import AsyncIterator

    async def _stream_response_generator() -> AsyncIterator[str]:
        # 사용자의 메시지는 스트리밍 시작 전에 먼저 저장
        db_session = SessionLocal() # 스트리밍 제너레이터 내에서 DB 세션 새로 생성
        try:
            db_session.add(
                ChatLog(
                    conversation_id=query.conversation_id,
                    user_id="user",
                    content=query.question,
                )
            )
            db_session.commit()
            
            # 초기 프리페이스 메시지 전송
            if prep_message:
                yield _sse("prep", prep_message)

            tool_results = []
            tool_results_texts = []

            # 툴 호출이 있으면 실행
            if tool_calls:
                print("  [스트리밍] 툴 호출 실행 중...")
                for tc in tool_calls:
                    try:
                        tool_name = tc.function.name
                        args = json.loads(tc.function.arguments)
                        
                        # 툴 호출
                        tool_result = call_tool(tool_name, args)
                        tool_results.append(tool_result)
                        
                        result_text = f"[{tool_name}] 결과:\n{json.dumps(tool_result, ensure_ascii=False)}"
                        tool_results_texts.append(result_text)
                        
                        # 소스 정보 전송
                        # 클라이언트에서 source를 받아서 별도 UI로 표시 가능
                        if tool_result:
                            yield _sse("sources", tool_result)
                            
                    except Exception as e:
                        error_msg = f"툴 호출 오류: {str(e)}"
                        print(error_msg)
                        traceback.print_exc()
                        yield _sse("error", error_msg)

            try:
                # 팔로업 메시지 구성
                # 과거 대화 로그도 함께 전달하여 최종 답변 생성
                final_messages = history_messages + build_followup_messages(
                    query.question, prep_message, tool_results_texts
                )

                # 최종 답변 스트리밍
                stream = client.chat.completions.create(
                    model="gpt-4.1-mini", # 최종 답변도 gpt-4o 사용 추천
                    messages=final_messages,
                    stream=True,
                )

                collected_chunks = []
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        collected_chunks.append(content)
                        yield _sse("chunk", content)

                # 전체 답변 저장
                full_answer = "".join(collected_chunks)
                
                # DB에 저장 (assistant 메시지)
                db_session.add(
                    ChatLog(
                        conversation_id=query.conversation_id,
                        user_id="assistant",
                        content=full_answer,
                    )
                )
                db_session.commit()
                
                # 완료 이벤트 전송
                yield _sse("done", {"status": "complete"})
                
            except Exception as e:
                error_msg = f"스트리밍 처리 중 오류 발생: {str(e)}"
                print(error_msg)
                traceback.print_exc()
                yield _sse("error", error_msg)
        finally:
            db_session.close() # 스트리밍이 끝나면 DB 세션 닫기


    return StreamingResponse(_stream_response_generator(), media_type="text/event-stream")
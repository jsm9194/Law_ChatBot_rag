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

# ===============================
# 앱 & 클라이언트
# ===============================
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
# 쿼리 최적화 프롬프트
# ===============================
QUERY_OPTIMIZATION_SYSTEM = """당신은 검색 쿼리 최적화 전문가입니다.
사용자의 자연어 질문을 받아, 구글 검색에서 최상의 결과를 얻을 수 있는 검색 쿼리로 변환해주세요.

다음 규칙을 따라주세요:
1. 원래 질문의 핵심 키워드와 의도를 파악하세요.
2. 검색엔진에 최적화된 3개의 서로 다른 쿼리를 생성하세요.
3. 각 쿼리는 짧고 명확하게 작성하세요 (보통 2-5개 단어).
4. 시간에 민감한 질문이라면 연도나 '최신', '최근' 같은 시간 키워드를 포함하세요.
5. 전문 용어가 있다면 그대로 유지하세요.
6. 불필요한 조사, 접속사는 제외하세요.

출력 형식은 JSON 배열로 정확히 다음과 같이 해주세요:
["쿼리1", "쿼리2", "쿼리3"]

다른 설명이나 부가 정보 없이 오직 JSON 배열만 출력하세요.
"""

def optimize_search_query(question: str) -> List[str]:
    """사용자 질문을 검색에 최적화된 쿼리로 변환"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # 또는 당신이 사용하는 모델
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
            if isinstance(queries, list) and len(queries) > 0:
                return queries
        except:
            print(f"쿼리 최적화 결과 파싱 실패: {result}")
            pass
            
    except Exception as e:
        print(f"쿼리 최적화 오류: {str(e)}")
    
    # 실패 시 원래 질문을 그대로 리턴
    return [question]

# ===============================
# 검색 결과 리랭킹 프롬프트
# ===============================
SEARCH_RERANKING_SYSTEM = """당신은 검색 결과 평가 전문가입니다.
사용자의 원래 질문과 검색 결과 목록을 받아, 질문과 가장 관련성 높은 결과들을 선별하세요.

다음 규칙을 따라주세요:
1. 각 검색 결과의 제목과 스니펫을 분석하세요.
2. 사용자 질문과의 관련성을 평가하세요.
3. 관련성이 높은 상위 3-5개 결과만 선택하세요.
4. 중복된 정보는 제거하세요.
5. 최신 정보를 우선시하세요.

출력 형식은 관련성이 높은 결과들의 인덱스만 JSON 배열로 반환하세요:
[0, 2, 5]  # 이는 0번, 2번, 5번 결과가 가장 관련성 높다는 의미입니다.

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
            model="gpt-3.5-turbo",
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
    # 2. 각 최적화된 쿼리로 검색 실행
    for opt_query in optimized_queries[:2]:  # 상위 2개 쿼리만 사용
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
    return f"event: {event}\ndata: {data}\n\n"

# ===============================
# 유틸: 팔로업 메시지 구성
# ===============================
FOLLOWUP_SYSTEM = """당신은 전문 분석 어시스턴트입니다.
당신의 임무는 (있다면) 툴(web_search, 법령검색, 판례검색 등)에서 전달된 결과를 바탕으로 사용자의 질문에 최종 답변을 작성하는 것입니다.

⚡️ 출력 규칙 (엄격히 지켜야 함)
1. **마크다운 형식**만 사용 (HTML 태그 금지)
2. 문단 간 두 줄 간격 유지
3. 제목/소제목은 `#`, `##`, `###`를 상황에 맞게 사용
4. 핵심은 불릿포인트(`-`), 단계/타임라인은 번호 리스트(`1.`)
5. 기사·문서·출처는 요약 옆에 `[출처명](URL)`로 바로 링크
6. 출처가 여러 개면 동일 주제 아래에 나란히 연결 (예: `👉 [연합뉴스](url) | [한겨레](url)`)
7. 불필요한 사족 금지. 데이터 없으면 `관련 자료 없음` 한 줄로.
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
    history_messages = [
        {"role": log.role, "content": log.content} for log in reversed(logs)
    ]
    
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
            "content": "당신은 사용자의 질문에 답하기 위해 필요한 도구를 선택하는 전문가입니다. 다음 도구들 중에서 적절한 것을 선택하세요. 과거 대화 맥락을 이해하고 도구 사용을 결정하세요.",
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
            model="gpt-4o", # 최종 답변도 gpt-4o 사용 추천
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
                    model="gpt-4o", # 최종 답변도 gpt-4o 사용 추천
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
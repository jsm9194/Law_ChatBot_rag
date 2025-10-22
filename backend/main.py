from fastapi import FastAPI, Depends, Request
from pydantic import BaseModel
from openai import OpenAI
import os
import json
import traceback
from typing import List, Dict, Any, Optional, AsyncIterator
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# ✅ DB 관련 import
from sqlalchemy.orm import Session
from DB.database import SessionLocal
from DB.models import ChatLog

# 라우터
from routers import conversations, messages

# 툴 모듈
from tools.query_qdrant import ask as ask_law
from tools.case_api import search_case_list, get_case_detail
from tools.search_goolge import google_search

# 툴 정의
from tools.tools_config import tools, TOOL_MESSAGES
from prompts import load_prompt_text, select_followup_prompt

from datetime import datetime

# ===============================
# 앱 & 클라이언트
# ===============================
app = FastAPI()
app.include_router(conversations.router)
app.include_router(messages.router)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# DB에 저장/복원할 role
VALID_MESSAGE_ROLES = {"assistant", "user"}

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
# DB 세션
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
# SSE 유틸 스트리밍 응답 구현용
# ===============================
def _sse(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"

# ===============================
# 답변 요약 (모델 호출)
# ===============================
def summarize_answer_with_model(content: str) -> str:
    """OpenAI 모델을 이용해 답변 요약 (3~5문장)"""
    log_tool_event("SUMMARY", "요약 요청", {"length": len(content)})
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "너는 전문적인 요약 어시스턴트다. 아래 답변을 3~5문장으로 간결하게 요약해라. 세부 목록은 묶어서 요지 위주로."},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
        )
        summary = (resp.choices[0].message.content or "").strip()
        if not summary:
            raise RuntimeError("빈 요약")
        return summary
    except Exception as e:
        log_tool_event("SUMMARY", "요약 실패 - 원본 사용", {"error": str(e)})
        print(f"[요약 실패] {e}")
        # 안전한 fallback (앞부분 300자)
        safe = (content or "").strip()
        return (safe[:300] + "...") if len(safe) > 300 else safe

# ===============================
# 로그/프리뷰 유틸
# ===============================
def _render_preview(obj: Any, limit: int = 400) -> str:
    try:
        rendered = json.dumps(obj, ensure_ascii=False)
    except TypeError:
        rendered = str(obj)
    if len(rendered) > limit:
        trimmed = rendered[:limit]
        rendered = f"{trimmed}... (+{len(rendered) - limit} chars)"
    return rendered


def log_tool_event(label: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {label:<10} {message}")
    if details:
        for key, value in details.items():
            preview = _render_preview(value)
            print(f"           - {key}: {preview}")

# ===============================
# 검색 최적화 유틸
# ===============================
QUERY_OPTIMIZATION_PROMPT = load_prompt_text("query_optimization.md")
SEARCH_RERANKING_PROMPT = load_prompt_text("search_reranking.md")


def optimize_search_query(question: str) -> Dict[str, List[str]]:
    fallback = {"ko": [question], "en": []}
    log_tool_event("SEARCH", "쿼리 최적화 요청", {"question": question})
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": QUERY_OPTIMIZATION_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("ko"):
                return {
                    "ko": [s for s in parsed.get("ko", []) if isinstance(s, str) and s.strip()],
                    "en": [s for s in parsed.get("en", []) if isinstance(s, str) and s.strip()],
                }
            if isinstance(parsed, list):
                return {"ko": [s for s in parsed if isinstance(s, str) and s.strip()], "en": []}
        except Exception:
            log_tool_event("SEARCH", "쿼리 JSON 파싱 실패", {"raw": raw})
    except Exception as e:
        log_tool_event("SEARCH", "쿼리 최적화 오류", {"error": str(e)})
    return fallback


def rerank_search_results(question: str, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(search_results) <= 5:
        return search_results
    joined = []
    for idx, item in enumerate(search_results):
        title = item.get("title", "제목 없음")
        snippet = item.get("snippet", "")
        joined.append(f"[{idx}] 제목: {title}\n요약: {snippet}")
    prompt = "\n\n".join(joined)

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SEARCH_RERANKING_PROMPT},
                {"role": "user", "content": f"질문: {question}\n\n검색결과:\n{prompt}"}
            ],
            temperature=0.1,
        )
        raw = response.choices[0].message.content or ""
        try:
            indices = json.loads(raw)
            ordered = []
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(search_results):
                    ordered.append(search_results[idx])
            if ordered:
                return ordered
        except Exception:
            log_tool_event("SEARCH", "리랭킹 JSON 파싱 실패", {"raw": raw})
    except Exception as e:
        log_tool_event("SEARCH", "리랭킹 오류", {"error": str(e)})
    return search_results[: min(5, len(search_results))]


def enhanced_web_search(query: str, count: int = 8, time_range: str = "any") -> Dict[str, Any]:
    optimized = optimize_search_query(query)
    merged: List[str] = []
    merged.extend(optimized.get("ko", []))
    merged.extend(optimized.get("en", []))
    # 중복 제거, 너무 길면 원문만 사용
    cleaned_queries: List[str] = []
    seen = set()
    for item in merged or [query]:
        trimmed = item.strip()
        if trimmed and trimmed not in seen:
            cleaned_queries.append(trimmed)
            seen.add(trimmed)
    all_results: List[Dict[str, Any]] = []
    for sub_query in cleaned_queries[:5]:  # 안전을 위해 최대 5개만 사용
        log_tool_event("SEARCH", "Google API 호출", {"query": sub_query, "time_range": time_range})
        response = google_search(sub_query, count=count, time_range=time_range)
        items = response.get("results") if isinstance(response, dict) else None
        if not items:
            continue
        for item in items:
            link = item.get("link")
            if link and all(existing.get("link") != link for existing in all_results):
                all_results.append(item)
    if not all_results:
        return google_search(query, count=count, time_range=time_range)
    ranked = rerank_search_results(query, all_results)
    return {"results": ranked[: count]}

# ===============================
# 도구 결과 포맷팅
# ===============================


def format_tool_result_for_prompt(tool_name: str, tool_result: Any) -> str:
    """도구 결과를 모델 입력용 텍스트로 정리한다."""
    if tool_name == "law" and isinstance(tool_result, dict):
        sources = tool_result.get("sources") or []
        context_items = tool_result.get("context") or []
        lines: List[str] = []
        if sources:
            lines.append("법령 출처")
            for idx, src in enumerate(sources, 1):
                law = str(src.get("law") or "").strip()
                article = str(src.get("article") or "").strip()
                label_parts = [part for part in [law, article] if part]
                label = " ".join(label_parts) if label_parts else f"법령 {idx}"
                url = str(src.get("url") or "").strip()
                entry = f"{idx}. {label}"
                if url:
                    entry += f" ({url})"
                lines.append(entry)
        if context_items:
            lines.append("")
            lines.append("조문 발췌")
            for item in context_items:
                lines.append(str(item))
        return "\n".join(line for line in lines if line).strip()

    if tool_name in {"search_cases", "case_detail"} and isinstance(tool_result, dict):
        cases = tool_result.get("cases")
        if cases and isinstance(cases, list):
            rows: List[str] = []
            for idx, case in enumerate(cases, 1):
                if not isinstance(case, dict):
                    continue
                text_values = [
                    str(value).strip() for value in case.values()
                    if isinstance(value, str) and value.strip()
                ][:3]
                label = " / ".join(text_values) if text_values else f"판례 {idx}"
                url = str(case.get("출처링크") or case.get("url") or "").strip()
                rows.append(f"{idx}. {label}{(' (' + url + ')') if url else ''}")
            if rows:
                return "\n".join(rows)
        else:
            text_values = [
                str(value).strip() for value in tool_result.values()
                if isinstance(value, str) and value.strip()
            ][:3]
            label = " / ".join(text_values) if text_values else "판례"
            url = str(tool_result.get("출처링크") or tool_result.get("url") or "").strip()
            return f"{label} ({url})" if url else label

    if tool_name == "web_search" and isinstance(tool_result, dict):
        results = tool_result.get("results") or []
        snippets: List[str] = []
        for idx, item in enumerate(results, 1):
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "자료").strip()
            link = (item.get("link") or "").strip()
            snippet = (item.get("snippet") or "").strip()
            entry = f"{idx}. {title}"
            if link:
                entry += f" ({link})"
            if snippet:
                entry += f"\n요약: {snippet}"
            snippets.append(entry)
        return "\n\n".join(snippets)

    try:
        return json.dumps(tool_result, ensure_ascii=False)
    except TypeError:
        return str(tool_result)


def extract_source_items(tool_name: str, tool_result: Any) -> List[Dict[str, Any]]:
    """프런트 표시용 출처 리스트를 정규화한다."""
    items: List[Dict[str, Any]] = []
    if tool_name == "law" and isinstance(tool_result, dict):
        for src in tool_result.get("sources", []) or []:
            if isinstance(src, dict):
                items.append({
                    "law": src.get("law"),
                    "article": src.get("article"),
                    "url": src.get("url"),
                })
        return items


    if tool_name in {"search_cases", "case_detail"} and isinstance(tool_result, dict):
        cases = tool_result.get("cases")
        if isinstance(cases, list):
            for case in cases:
                if not isinstance(case, dict):
                    continue
                label_parts = [
                    case.get("사건명") or case.get("사건명") or case.get("title"),
                    case.get("사건번호") or case.get("사건번호") or case.get("case_no"),
                    case.get("법원명") or case.get("법원명") or case.get("court"),
                ]
                label = " / ".join([str(p).strip() for p in label_parts if isinstance(p, str) and p.strip()])
                items.append({
                    "title": label or "판례",
                    "url": case.get("출처링크") or case.get("url"),
                })
        else:
            label_parts = [
                tool_result.get("사건명") or tool_result.get("사건명") or tool_result.get("title"),
                tool_result.get("사건번호") or tool_result.get("사건번호") or tool_result.get("case_no"),
                tool_result.get("법원명") or tool_result.get("법원명") or tool_result.get("court"),
            ]
            label = " / ".join([str(p).strip() for p in label_parts if isinstance(p, str) and p.strip()])
            items.append({
                "title": label or "판례",
                "url": tool_result.get("출처링크") or tool_result.get("url"),
            })
        return [item for item in items if item.get("title")]

    if tool_name == "web_search" and isinstance(tool_result, dict):
        for item in tool_result.get("results", []) or []:
            if not isinstance(item, dict):
                continue
            items.append({
                "title": item.get("title"),
                "url": item.get("link"),
                "snippet": item.get("snippet"),
            })
        return items

    return items

def load_history(db: Session, conversation_id: str, recent_turns: int = 3, max_logs: int = 40) -> List[Dict[str, str]]:
    """
    - 최근 recent_turns(기본 3) 턴은 원문 유지 (user/assistant 한 턴 = 2로그)
    - 그 이전 assistant 답변은 summary 있으면 summary, 없으면 요약 생성하여 사용
    - user 메시지는 원문 유지
    """
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.conversation_id == conversation_id)
        .order_by(ChatLog.created_at.asc())
        .limit(max_logs)
        .all()
    )

    # user/assistant만 필터
    filtered = [log for log in logs if (log.role in VALID_MESSAGE_ROLES)]
    # 최근 턴 범위 계산
    cutoff = max(0, len(filtered) - recent_turns * 2)

    history: List[Dict[str, str]] = []
    for idx, log in enumerate(filtered):
        content = log.content or ""
        if log.role == "assistant" and idx < cutoff:
            # 오래된 assistant 응답은 요약 사용
            summary = getattr(log, "summary", None)
            if summary and summary.strip():
                content = summary.strip()
            else:
                # DB에 summary가 없다면 즉석 요약 생성 (한 번만 생성해서 DB에 채우는 것도 가능)
                summary_generated = summarize_answer_with_model(content)
                log.summary = summary_generated
                try:
                    db.add(log)
                    db.commit()
                except Exception as commit_error:
                    db.rollback()
                    log_tool_event("SUMMARY", "요약 저장 실패", {"error": str(commit_error), "log_id": getattr(log, "id", None)})
                content = summary_generated
        history.append({"role": log.role, "content": content})

    # 연속 중복 제거(같은 role/같은 content 연달아 오는 경우)
    deduped: List[Dict[str, str]] = []
    for m in history:
        if deduped and deduped[-1]["role"] == m["role"] and deduped[-1]["content"] == m["content"]:
            continue
        deduped.append(m)

    return deduped

# ===============================
# 팔로업 메시지 구성 (최종 답변용)
# ===============================
def build_followup_messages(
    question: str,
    tool_results_texts: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    최종 답변 생성을 위한 메시지 빌드.
    - system 프롬프트: 선택된 템플릿
    - user: 현재 질문
    - system: 도구 결과(있으면)
    """
    selection = select_followup_prompt(question, tool_names, tool_results_texts)
    print(f"  [PROMPT] 사용된 응답 프롬프트: {selection.name} (tags={', '.join(sorted(selection.tags))})")
    log_tool_event("PROMPT", f'응답 프롬프트 선택: {selection.name}', {'tags': sorted(selection.tags)})

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": selection.content},
        {"role": "user", "content": question},
    ]
    if tool_results_texts:
        joined_header = "아래는 이번에 수행한 도구 결과입니다.\n\n"
        joined = joined_header + "\n\n".join(tool_results_texts)
        messages.append({"role": "system", "content": joined})

    return messages

# ===============================
# 툴 실행 매퍼
# ===============================
def call_tool(name: str, arguments: dict):
    log_tool_event("TOOL-CALL", f"{name} 실행", {"arguments": arguments})
    print("? [TOOL CALL]", name, arguments)
    try:
        if name == "law":
            result = ask_law(arguments["query"])
        elif name == "search_cases":
            if "case_id" in arguments:
                result = get_case_detail(arguments["case_id"])
            elif "nb" in arguments:
                result = get_case_detail(arguments["nb"])
            else:
                result = {"cases": search_case_list(**arguments)}
                
        elif name == "case_detail":
            result = get_case_detail(arguments["case_id"])
        elif name == "web_search":
            result = enhanced_web_search(arguments["query"], arguments.get("count", 8), arguments.get("time_range", "any"))
        else:
            result = {"error": f"Unknown tool: {name}"}
        log_tool_event("TOOL-DONE", f"{name} 완료", {"result": result})
        return result
    except Exception as e:
        log_tool_event("TOOL-ERR", f"{name} 실패", {"error": str(e)})
        traceback.print_exc()
        return {"error": f"Tool execution failed: {str(e)}"}
    

# ===============================
# 핵심: /ask 엔드포인트
# ===============================
@app.post("/ask")

def ask_api(query: Query, request: Request, db: Session = Depends(get_db)):
    log_tool_event("ASK", "요청 수신", {"conversation_id": query.conversation_id, "question": query.question})
    print("\n[ASK 호출됨]")
    print(f"  대화 ID: {query.conversation_id}")
    print(f"  질문: {query.question}\n")

    # 🔹 히스토리 로딩 (롤링 요약 반영)
    history_messages = load_history(db, query.conversation_id)
    log_tool_event("HISTORY", "최근 대화 불러오기", {"count": len(history_messages)})
    print("  === 과거 대화 로그(압축) ===")
    for msg in history_messages:
        print(f"  {msg['role']}: {msg['content']}")
    print("  ===========================")

    # 🔹 툴 호출 판단 (mini 사용)
    messages_for_tool_call = history_messages + [
        {"role": "system", "content": load_prompt_text("tool_selection.md")},
        {"role": "user", "content": query.question},
    ]
    
    # ✅ 추가: 모델 입력 로그
    log_tool_event("CTX-IN", "도구선택 입력 메시지 구성", {
        "messages": [
            f"{m['role']}: {m['content'][:200]}..." for m in messages_for_tool_call
        ]
    })  

    first = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages_for_tool_call,
        tools=tools,
        tool_choice="auto",
    )
    tool_calls = first.choices[0].message.tool_calls
    planned_tool_names = [tc.function.name for tc in tool_calls] if tool_calls else []
    if planned_tool_names:
        log_tool_event("TOOL-PLAN", "모델이 선택한 도구", {"tools": planned_tool_names})
    else:
        log_tool_event("TOOL-PLAN", "선택된 도구 없음", None)
    prep_message = first.choices[0].message.content or ""
    # ✅ 모델의 사전 사고 내용(prep_message) 로그 추가
    if prep_message:
        log_tool_event("PREP", "모델 사고 내용(pre-thinking)", {
            "content": (prep_message[:400] + "...") if len(prep_message) > 400 else prep_message
        })
    else:
        log_tool_event("PREP", "모델 사고 내용 없음", {})


    # ===============================
    # 스트리밍 응답
    # ===============================

    async def _stream_response_generator() -> AsyncIterator[str]:
        db_session = SessionLocal()
        try:
            # 🔹 질문을 먼저 저장
            db_session.add(ChatLog(
                conversation_id=query.conversation_id,
                role="user",
                user_id="user",
                content=query.question,
            ))
            db_session.commit()

            # prep_message는 스트림으로만 전달 (최종 입력에는 제외)
            if prep_message:
                yield _sse("prep", prep_message)

            tool_results = []
            tool_results_texts = []
            executed_tool_names: List[str] = []

            # 도구 실행
            if tool_calls:
                log_tool_event("TOOL-RUN", "도구 실행 시작", {"count": len(tool_calls)})
                for tc in tool_calls:
                    try:
                        tool_name = tc.function.name
                        args = json.loads(tc.function.arguments)

                        meta = TOOL_MESSAGES.get(tool_name, {})
                        prep_status = meta.get("prep")
                        if prep_status:
                            yield _sse("status", prep_status)

                        result = call_tool(tool_name, args)
                        tool_results.append(result)
                        executed_tool_names.append(tool_name)

                        # fallback 감지 및 Google 검색 전환
                        if "error" in str(result):
                            log_tool_event(
                                "FALLBACK",
                                f"{tool_name} 실패 → Google 검색 fallback 실행",
                                {"query": args.get("query")},
                            )
                            fallback_result = enhanced_web_search(
                                args.get("query", ""),
                                args.get("count", 8),
                                args.get("time_range", "any"),
                            )

                            # 🔹 결과 교체
                            result = fallback_result
                            tool_results[-1] = fallback_result

                            # 🔹 툴 이름도 web_search로 교체 (프롬프트 선택 영향)
                            executed_tool_names = [
                                "web_search" 
                            ]

                            # 🔹 프론트로 상태 알림
                            yield _sse("status", "법제처 API 실패로 Google 검색으로 대체합니다.")

                        formatted = format_tool_result_for_prompt(tool_name, result)
                        tool_results_texts.append(formatted)

                        done_status = meta.get("done")
                        if done_status:
                            yield _sse("status", done_status)

                        source_items = extract_source_items(tool_name, result)
                        if source_items:
                            yield _sse("sources", {"tool": tool_name, "items": source_items})
                        else:
                            yield _sse("sources", result)
                    except Exception as e:
                        yield _sse("status", f"{tool_name} 실행 중 오류가 발생했습니다.")
                        yield _sse("error", f"툴 실행 오류: {str(e)}")
            else:
                log_tool_event("TOOL-RUN", "선택된 도구 없음 - 바로 답변", None)
                yield _sse("status", "도구 없이 바로 답변을 생성합니다.")
            log_tool_event("CTX-BUILD", "도구 결과 컨텍스트 구성", {"count": len(tool_results_texts), "tools": executed_tool_names or planned_tool_names})
            final_messages = history_messages + build_followup_messages(
                query.question, tool_results_texts, executed_tool_names or planned_tool_names
            )

            # ✅ 추가: 모델 입력 로그
            log_tool_event("CTX-IN", "최종 답변 모델 입력 메시지", {
                "messages": [
                    f"{m['role']}: {m['content'][:200]}..." for m in final_messages
                ]
            })

            log_tool_event("MODEL", "최종 답변 스트리밍 시작", {"messages": len(final_messages)})
            yield _sse("status", "응답을 작성하는 중입니다.")
            stream = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=final_messages,
                stream=True,
            )

            collected_chunks: List[str] = []
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    part = chunk.choices[0].delta.content
                    collected_chunks.append(part)
                    yield _sse("chunk", {"delta": {"content": part}})

            full_answer = "".join(collected_chunks)

            # ✅ 요약 생성(모델 호출) 후 함께 저장
            log_tool_event("MODEL", "최종 답변 스트리밍 완료", {"chars": len(full_answer)})
            summary = summarize_answer_with_model(full_answer)
            log_tool_event("SUMMARY", "요약 생성 완료", {"preview": summary})
            db_session.add(ChatLog(
                conversation_id=query.conversation_id,
                role="assistant",
                user_id="system",
                content=full_answer,
                summary=summary,
            ))
            db_session.commit()

            yield _sse("done", {"choices": [{"finish_reason": "stop"}]})
        finally:
            db_session.close()

    return StreamingResponse(_stream_response_generator(), media_type="text/event-stream")
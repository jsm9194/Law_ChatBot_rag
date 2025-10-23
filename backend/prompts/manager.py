from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set
from openai import OpenAI
import os

PROMPTS_DIR = Path(__file__).resolve().parent
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ 전역 설정
USE_CACHE: bool = True  # False = 프롬프트 교체 모드
USE_LLM_TAGGING: bool = True  # True = LLM으로 태깅
USE_LLM_CONDITION: bool = True  # True = LLM으로 조건 매칭


@dataclass(frozen=True)
class PromptSelection:
    name: str
    content: str
    source_file: str
    tags: Set[str]


# =========================================================
# 기본 파일 로더
# =========================================================
def _ensure_exists(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Prompt 파일을 찾을 수 없습니다: {path}")
    return path


def load_prompt_text(filename: str, use_cache: Optional[bool] = None) -> str:
    effective_cache = USE_CACHE if use_cache is None else use_cache
    path = _ensure_exists(PROMPTS_DIR / filename)
    if effective_cache:
        return _load_prompt_text_cached(filename)
    else:
        return path.read_text(encoding="utf-8-sig")


@lru_cache(maxsize=None)
def _load_prompt_text_cached(filename: str) -> str:
    path = _ensure_exists(PROMPTS_DIR / filename)
    return path.read_text(encoding="utf-8-sig")


# =========================================================
# followup_prompts.json 로드
# =========================================================
@lru_cache(maxsize=1)
def _load_followup_config() -> List[Dict[str, Any]]:
    path = _ensure_exists(PROMPTS_DIR / "followup_prompts.json")
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("followup_prompts.json 은 리스트 형식이어야 합니다.")

    normalized: List[Dict[str, Any]] = []
    for entry in raw:
        if "prompt_file" not in entry:
            raise ValueError("각 프롬프트 항목에는 prompt_file 이 필요합니다.")
        entry = {
            "name": entry.get("name", entry["prompt_file"]),
            "prompt_file": entry["prompt_file"],
            "priority": entry.get("priority", 0),
            "conditions": entry.get("conditions", {}),
        }
        normalized.append(entry)

    normalized.sort(key=lambda item: item.get("priority", 0), reverse=True)
    return normalized


# =========================================================
# LLM 기반 태그 분류
# =========================================================
def infer_context_tags_llm(question: str) -> Set[str]:
    """
    LLM을 사용하여 문맥 태그를 추론.
    """
    prompt = f"""
    다음 한국어 질문이 어떤 주제에 속하는지 분석해.
    가능한 태그는 다음 중에서 골라서 JSON 배열로만 반환해:
    ["law", "case", "news", "general"]

    - law: 법령, 조문, 규정, 안전보건, 의무, 법적 책임 관련
    - case: 판례, 소송, 재판, 사건 관련
    - news: 최근 동향, 개정, 발표, 보도 관련
    - general: 일반적인 설명, 상식, 단순 질의

    질문: {question}
    JSON 배열로만 출력해. (예: ["law", "case"])
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "너는 법률 질의 태깅 분류기야."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = res.choices[0].message.content.strip()
        tags = set(json.loads(text))
        return tags or {"general"}
    except Exception as e:
        print(f"[WARN] LLM 태깅 실패: {e}")
        return {"general"}


# =========================================================
# 기존 키워드 기반 (fallback)
# =========================================================
LAW_KEYWORDS = ["법령", "조문", "법률", "규정", "의무", "법적"]
CASE_KEYWORDS = ["판례", "사건", "재판", "심판", "소송"]
NEWS_KEYWORDS = ["뉴스", "동향", "최근", "보도", "발표", "업데이트"]


def infer_context_tags_keywords(
    question: str,
    tool_names: Optional[Sequence[str]] = None,
    tool_results_texts: Optional[Sequence[str]] = None,
) -> Set[str]:
    tags: Set[str] = {"general"}
    focus_text = " ".join(filter(None, [question] + list(tool_results_texts or [])))
    lowered = focus_text.lower()
    tool_set = {tool.lower() for tool in (tool_names or [])}

    if tool_set & {"law"}:
        tags.add("law")
    if tool_set & {"case_detail", "search_cases"}:
        tags.add("case")
    if tool_set & {"web_search"}:
        tags = {"general", "news"}
        return tags

    if any(k.lower() in lowered for k in LAW_KEYWORDS):
        tags.add("law")
    if any(k.lower() in lowered for k in CASE_KEYWORDS):
        tags.add("case")
    if any(k.lower() in lowered for k in NEWS_KEYWORDS):
        tags.add("news")

    return tags


def infer_context_tags(
    question: str,
    tool_names: Optional[Sequence[str]] = None,
    tool_results_texts: Optional[Sequence[str]] = None,
) -> Set[str]:
    if USE_LLM_TAGGING:
        return infer_context_tags_llm(question)
    else:
        return infer_context_tags_keywords(question, tool_names, tool_results_texts)


# =========================================================
# LLM 기반 조건 매칭
# =========================================================
def _match_conditions_llm(conditions: Dict[str, Any], question: str, tags: Set[str]) -> bool:
    """
    LLM을 사용해 conditions와 question, tags의 의미적 일치 여부 판단.
    """
    if not conditions:
        return True

    prompt = f"""
    다음은 프롬프트 조건과 사용자의 질문 정보입니다.
    조건을 만족한다고 판단되면 true, 아니면 false를 소문자로만 출력하세요.

    [조건 JSON]
    {json.dumps(conditions, ensure_ascii=False, indent=2)}

    [질문]
    {question}

    [문맥 태그]
    {', '.join(tags)}

    조건에 해당하는 주제나 문맥이라면 true, 전혀 관련 없다면 false.
    반드시 true 또는 false만 출력.
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "너는 법률 도메인용 조건 매칭 판단기야."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        answer = res.choices[0].message.content.strip().lower()
        return "true" in answer
    except Exception as e:
        print(f"[WARN] LLM 조건 매칭 실패: {e}")
        return False


# =========================================================
# 메인 프롬프트 선택 로직
# =========================================================
def select_followup_prompt(
    question: str,
    tool_names: Optional[Sequence[str]] = None,
    tool_results_texts: Optional[Sequence[str]] = None,
    use_cache: Optional[bool] = None,
) -> PromptSelection:
    normalized_tools = {tool.lower() for tool in (tool_names or [])}
    tags = infer_context_tags(question, tool_names, tool_results_texts)

    for entry in _load_followup_config():
        conditions = entry.get("conditions", {})

        if USE_LLM_CONDITION:
            matched = _match_conditions_llm(conditions, question, tags)
        else:
            matched = True  # LLM이 꺼진 경우 조건은 무시하거나 기본 True

        if matched:
            content = load_prompt_text(entry["prompt_file"], use_cache=use_cache)
            return PromptSelection(
                name=entry.get("name", "unknown"),
                content=content,
                source_file=str(PROMPTS_DIR / entry["prompt_file"]),
                tags=tags,
            )

    # fallback
    fallback = load_prompt_text("followup_default.md", use_cache=False)
    return PromptSelection(
        name="default",
        content=fallback,
        source_file=str(PROMPTS_DIR / "followup_default.md"),
        tags=tags,
    )

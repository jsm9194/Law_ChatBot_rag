from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

PROMPTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PromptSelection:
    name: str
    content: str
    source_file: str
    tags: Set[str]


def _ensure_exists(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Prompt 파일을 찾을 수 없습니다: {path}")
    return path


@lru_cache(maxsize=None)
def load_prompt_text(filename: str) -> str:
    path = _ensure_exists(PROMPTS_DIR / filename)
    return path.read_text(encoding="utf-8-sig")


@lru_cache(maxsize=1)
def _load_followup_config() -> List[Dict[str, Any]]:
    path = _ensure_exists(PROMPTS_DIR / "followup_prompts.json")
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("followup_prompts.json 은 리스트 형식이어야 합니다.")

    normalised: List[Dict[str, Any]] = []
    for entry in raw:
        if "prompt_file" not in entry:
            raise ValueError("각 프롬프트 항목에는 prompt_file 이 필요합니다.")
        entry = {
            "name": entry.get("name", entry["prompt_file"]),
            "prompt_file": entry["prompt_file"],
            "priority": entry.get("priority", 0),
            "conditions": entry.get("conditions", {}),
        }
        normalised.append(entry)

    normalised.sort(key=lambda item: item.get("priority", 0), reverse=True)
    return normalised


LAW_KEYWORDS = ["법령", "조문", "법률", "규정", "의무", "법적"]
CASE_KEYWORDS = ["판례", "사건", "재판", "심판", "소송"]
NEWS_KEYWORDS = ["뉴스", "동향", "최근", "보도", "발표", "업데이트"]


def infer_context_tags(
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
        return tags  # web_search가 있으면 무조건 news

    if any(keyword.lower() in lowered for keyword in LAW_KEYWORDS):
        tags.add("law")
    if any(keyword.lower() in lowered for keyword in CASE_KEYWORDS):
        tags.add("case")
    if any(keyword.lower() in lowered for keyword in NEWS_KEYWORDS):
        tags.add("news")

    return tags


def _text_contains_any(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _match_conditions(
    conditions: Dict[str, Any],
    question: str,
    tool_names: Set[str],
    tags: Set[str],
) -> bool:
    if not conditions:
        return True

    question_lower = question.lower()

    tools_any = conditions.get("tools_any")
    if tools_any and not ({tool.lower() for tool in tools_any} & tool_names):
        return False

    tools_all = conditions.get("tools_all")
    if tools_all and not ({tool.lower() for tool in tools_all} <= tool_names):
        return False

    tags_any = conditions.get("context_tags_any")
    if tags_any and not ({tag.lower() for tag in tags_any} & {tag.lower() for tag in tags}):
        return False

    tags_all = conditions.get("context_tags_all")
    if tags_all and not ({tag.lower() for tag in tags_all} <= {tag.lower() for tag in tags}):
        return False

    keywords_any = conditions.get("question_contains_any")
    if keywords_any and not _text_contains_any(question, keywords_any):
        return False

    keywords_all = conditions.get("question_contains_all")
    if keywords_all and not all(keyword.lower() in question_lower for keyword in keywords_all):
        return False

    return True


def select_followup_prompt(
    question: str,
    tool_names: Optional[Sequence[str]] = None,
    tool_results_texts: Optional[Sequence[str]] = None,
) -> PromptSelection:
    normalized_tools = {tool.lower() for tool in (tool_names or [])}
    tags = infer_context_tags(question, tool_names, tool_results_texts)

    for entry in _load_followup_config():
        if _match_conditions(entry.get("conditions", {}), question, normalized_tools, tags):
            content = load_prompt_text(entry["prompt_file"])
            return PromptSelection(
                name=entry.get("name", "unknown"),
                content=content,
                source_file=str(PROMPTS_DIR / entry["prompt_file"]),
                tags=tags,
            )

    # fallback: 기본 프롬프트
    fallback = load_prompt_text("followup_default.md")
    return PromptSelection(
        name="default",
        content=fallback,
        source_file=str(PROMPTS_DIR / "followup_default.md"),
        tags=tags,
    )


__all__ = [
    "load_prompt_text",
    "infer_context_tags",
    "select_followup_prompt",
    "PromptSelection",
]


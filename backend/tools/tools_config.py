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
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "case_detail",
    #         "description": "판례 상세 조회 (판례정보일련번호 기반). search_cases 결과의 사건ID를 그대로 사용한다.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "case_id": {
    #                     "type": "string",
    #                     "description": "search_cases 결과에서 반환된 사건ID (판례정보일련번호)"
    #                 }
    #             },
    #             "required": ["case_id"],
    #         },
    #     },
    # },
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
                        "default": 20,
                        "description": "가져올 검색 결과 개수 (최대 100)"
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



TOOL_MESSAGES = {
    "web_search": {
        "prep": "웹에서 관련 자료를 검색하고 있습니다. 잠시만 기다려 주세요 🙂",
        "done": "웹을 검색해 자료를 수집했습니다. 📌"
    },
    "law": {
        "prep": "법령집에서 관련 조항을 확인하고 있습니다. 📚",
        "done": "법령집을 참고해 답변을 정리했습니다."
    },
    "search_cases": {
        "prep": "판례 목록을 검색하고 있습니다. ⚖️",
        "done": "판례 목록을 조사해 관련된 판례를 찾았습니다."
    },
    "case_detail": {
        "prep": "판례 전문을 확인하고 있습니다. 📝",
        "done": "판례 전문을 확인해 요약했습니다."
    }
}
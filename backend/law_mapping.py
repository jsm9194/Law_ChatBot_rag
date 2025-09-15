# law_mapping.py

LAW_NAME_TO_ID = {
    "산업안전보건기준에관한규칙": "007363",
    "산업안전보건법": "001766",
    "산업안전보건법시행규칙": "007364",
    "산업안전보건법시행령": "003786",
    "재난및안전관리기본법": "009640",
    "재난및안전관리기본법시행규칙": "009717",
    "재난및안전관리기본법시행령": "009708",
    "중대재해처벌등에관한법률": "228817",  # ⚠️ MST라면 이건 작동안 함 → ID 필요
    "중대재해처벌등에관한법률시행령": "014159",
}

BASE_URL = "http://www.law.go.kr/DRF/lawService.do"

def format_jo(article_number: str) -> str:
    """
    법제처 DRF API용 JO 파라미터 형식으로 변환
    - 입력: "391" → 출력: "039100"
    - 입력: "10의2" → 출력: "001002"
    """
    if not article_number:
        return ""

    # "의"가 있는 경우 → "제10조의 2" 같은 케이스
    if "의" in article_number:
        parts = article_number.split("의")
        jo_num = int(parts[0])  # 조번호
        sub_num = int(parts[1]) if len(parts) > 1 else 0
    else:
        jo_num = int(article_number)
        sub_num = 0

    return f"{jo_num:04d}{sub_num:02d}"


def make_law_link(law_name: str, jo: str = None, oc: str = "jsm9194") -> str:
    """
    법령명(+조문번호) → 법제처 원문 페이지 링크 반환
    """
    law_id = LAW_NAME_TO_ID.get(law_name)
    if not law_id:
        return ""

    if jo:
        jo_param = format_jo(jo)  # ✅ 여기서 변환
        return f"{BASE_URL}?OC={oc}&target=law&ID={law_id}&JO={jo_param}&type=HTML"
    else:
        return f"{BASE_URL}?OC={oc}&target=law&ID={law_id}&type=HTML"

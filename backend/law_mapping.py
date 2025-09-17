import re
import dotenv
import os
dotenv.load_dotenv()

LAW_OC_ID = os.getenv("LAW_OC_ID")  # 기본값 설정 가능

LAW_NAME_TO_ID = {
    "산업안전보건기준에관한규칙": ("ID", "007363"),
    "산업안전보건법": ("ID", "001766"),
    "산업안전보건법시행규칙": ("ID", "007364"),
    "산업안전보건법시행령": ("ID", "003786"),
    "재난및안전관리기본법": ("ID", "009640"),
    "재난및안전관리기본법시행규칙": ("ID", "009717"),
    "재난및안전관리기본법시행령": ("ID", "009708"),
    "중대재해처벌등에관한법률": ("MST", "228817"), 
    "중대재해처벌등에관한법률시행령": ("ID", "014159"),
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

    if "의" in article_number:
        parts = article_number.split("의")
        jo_num = int(parts[0])
        sub_num = int(parts[1]) if len(parts) > 1 else 0
    else:
        jo_num = int(article_number)
        sub_num = 0

    return f"{jo_num:04d}{sub_num:02d}"


def make_law_link(law_name: str, jo: str = None, oc: str = LAW_OC_ID) -> str:
    """
    법령명(+조문번호) → 법제처 원문 페이지 링크 반환
    - 중대재해처벌등에관한법률은 MST 기반
    - 나머지는 ID 기반
    """
    law_info = LAW_NAME_TO_ID.get(law_name)
    if not law_info:
        return ""

    id_type, value = law_info
    param_name = "MST" if id_type == "MST" else "ID"

    if jo:
        jo_param = format_jo(jo)
        return f"{BASE_URL}?OC={oc}&target=law&{param_name}={value}&JO={jo_param}&type=HTML"
    else:
        return f"{BASE_URL}?OC={oc}&target=law&{param_name}={value}&type=HTML"

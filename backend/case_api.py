import requests
import xml.etree.ElementTree as ET
import os
from typing import List, Dict, Optional
import dotenv
from utils.safe_request import safe_request

dotenv.load_dotenv()
LAW_OC_ID = os.getenv("LAW_OC_ID")

SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"
DETAIL_URL = "http://www.law.go.kr/DRF/lawService.do"


def search_case_list(
    query: str,
    count: int = 5,
    search: int = 2,  # 본문 검색 (1: 사건명 검색)
    curt: Optional[str] = None,
    org: Optional[str] = None,
    nb: Optional[str] = None,
    datSrcNm: Optional[str] = None,
    sort: Optional[str] = None,
    page: int = 1,
    display: int = 20
) -> List[Dict]:
    """판례 목록 검색 (XML 기반)"""
    params = {
        "OC": LAW_OC_ID,
        "target": "prec",
        "type": "XML",
        "query": query,
        "search": search,
        "page": page,
        "display": display,
    }
    if curt: params["curt"] = curt
    if org: params["org"] = org
    if nb: params["nb"] = nb
    if datSrcNm: params["datSrcNm"] = datSrcNm
    if sort: params["sort"] = sort

    resp = safe_request(SEARCH_URL, params)
    if isinstance(resp, dict) and "error" in resp:
        return [resp]  # 에러 발생 시 리스트 형태로 반환 (호출부에서 에러 메시지 처리 가능)

    try:
        resp.encoding = "utf-8"
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        return {"error": f"XML 파싱 실패: {e}"}

    cases = []
    for item in root.findall("prec")[:count]:
        case_id = item.findtext("판례일련번호")
        사건명 = item.findtext("사건명")
        사건번호 = item.findtext("사건번호")
        선고일자 = item.findtext("선고일자")
        법원명 = item.findtext("법원명")

        # 출처 링크 생성 (HTML 보기)
        link = f"{DETAIL_URL}?OC={LAW_OC_ID}&target=prec&ID={case_id}&type=HTML"

        cases.append({
            "사건ID": case_id,
            "사건명": 사건명,
            "사건번호": 사건번호,
            "선고일자": 선고일자,
            "법원명": 법원명,
            "출처링크": link
        })
    return cases


def get_case_detail(case_id: str) -> Dict:
    url = "http://www.law.go.kr/DRF/lawService.do"
    params = {
        "OC": LAW_OC_ID,
        "target": "prec",
        "ID": case_id,
        "type": "JSON"
    }

    resp = safe_request(url, params)
    if isinstance(resp, dict) and "error" in resp:
        return resp  # API 호출 자체가 실패했을 때 그대로 반환

    try:
        resp.encoding = "utf-8"
        data = resp.json()
    except Exception as e:
        return {"error": f"JSON 파싱 실패: {e}", "raw": resp.text[:300]}

    # Prec 키 확인
    item = data.get("Prec")
    if not item:
        return {"error": "판례 본문을 찾을 수 없음", "raw": data}

    import re
    def clean_html(text: str) -> str:
        if not text:
            return None
        return re.sub(r"<br\s*/?>", "\n", text).strip()

    return {
        "판례명": item.get("사건명"),
        "사건번호": item.get("사건번호"),
        "선고일자": item.get("선고일자"),
        "법원명": item.get("법원명"),
        "판시사항": clean_html(item.get("판시사항")),
        "참조조문": item.get("참조조문"),
        "참조판례": item.get("참조판례"),
        "판결요지": clean_html(item.get("판결요지")),
        "판례전문": clean_html(item.get("판례내용")),
    }


# ================================
# 테스트 코드 (직접 실행 시)
# ================================
if __name__ == "__main__":
    print("LAW_OC_ID =", LAW_OC_ID)

    results = search_case_list("중대재해처벌법", count=2)
    print("\n[검색 결과]")
    for r in results:
        print(r)

    if results:
        detail = get_case_detail(results[0]["사건ID"])
        print("\n[본문 결과]")
        print(detail)

import os
import re
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
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
    search: int = 2,  # 기본: 본문 검색 (1=사건명/번호 검색)
    curt: Optional[str] = None,
    org: Optional[str] = None,
    nb: Optional[str] = None,
    datSrcNm: Optional[str] = None,
    sort: Optional[str] = None,
    page: int = 1,
    display: int = 20
) -> List[Dict]:
    """판례 목록 검색 (XML 기반)"""

    # ✅ 사건번호 패턴 자동 인식 → 사건번호 검색 모드로
    if re.match(r"\d{2,4}[가-힣]+\d+", query):
        search = 1

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
        return [resp]

    try:
        resp.encoding = "utf-8"
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        return [{"error": f"XML 파싱 실패: {e}"}]

    cases = []
    for item in root.findall("prec")[:count]:
        case_id = item.findtext("판례일련번호")
        사건명 = item.findtext("사건명")
        사건번호 = item.findtext("사건번호")
        선고일자 = item.findtext("선고일자")
        법원명 = item.findtext("법원명")

        # 출처 링크 (HTML 보기)
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


def get_case_detail(case_id: str) -> dict:
    """
    판례 상세 조회
    - 입력: 사건번호(예: 2023다238486) 또는 판례일련번호(예: 347830)
    - 처리: 사건번호면 search_case_list()로 판례일련번호를 먼저 조회
    - 출력: 판례 상세 JSON (판시사항, 판결요지, 판례전문 등)
    """
    # 사건번호(한글+숫자 조합) → 판례일련번호 변환
    if not case_id.isdigit():
        results = search_case_list(query="", nb=case_id, count=1, search=1)
        if results and "사건ID" in results[0]:
            case_id = results[0]["사건ID"]
        else:
            return {"error": f"사건번호 '{case_id}'에 해당하는 판례를 찾을 수 없습니다."}

    # 1. JSON 요청
    url = "http://www.law.go.kr/DRF/lawService.do"
    params = {"OC": LAW_OC_ID, "target": "prec", "ID": case_id, "type": "JSON"}
    resp = requests.get(url, params=params)

    try:
        data = resp.json()
        if "Prec" in data:
            item = data["Prec"]
            return {
                "판례명": item.get("사건명"),
                "사건번호": item.get("사건번호"),
                "선고일자": item.get("선고일자"),
                "법원명": item.get("법원명"),
                "판시사항": item.get("판시사항"),
                "판결요지": item.get("판결요지"),
                "판례전문": item.get("판례내용"),
                "출처링크": f"http://www.law.go.kr/DRF/lawService.do?OC={LAW_OC_ID}&target=prec&ID={case_id}&type=HTML"
            }
    except Exception:
        pass

    # 2. JSON 실패 시 HTML fallback
    html_url = f"http://www.law.go.kr/LSW/precInfoP.do?precSeq={case_id}&mode=0"
    iframe_url = f"http://www.law.go.kr/LSW/precInfoR.do?precSeq={case_id}&mode=0"
    iframe_resp = requests.get(iframe_url)
    iframe_resp.encoding = iframe_resp.apparent_encoding
    iframe_soup = BeautifulSoup(iframe_resp.text, "html.parser")
    text = iframe_soup.get_text("\n", strip=True).replace("\xa0", " ")

    return {
        "판례명": f"precSeq={case_id}",
        "판례전문": text,
        "출처링크": html_url,
    }




# ================================
# 테스트 코드
# ================================
if __name__ == "__main__":
    print("LAW_OC_ID =", LAW_OC_ID)

    results = search_case_list("94누5496", count=3)
    print("\n[검색 결과]")
    for r in results:
        print(r)

    if results:
        detail = get_case_detail(results[0]["사건ID"])
        print("\n[본문 결과]")
        print(detail)

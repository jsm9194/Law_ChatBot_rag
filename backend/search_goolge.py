import os
import requests
import dotenv

dotenv.load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")

def google_search(query: str, count: int = 5, time_range: str = "any"):
    """
    Google Custom Search API 호출
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
        "num": min(count, 10),  # Google API는 요청당 최대 10개
        "hl": "ko",             # 한국어 결과 우선
        "gl": "kr",             # 한국 지역
    }

    # 기간 제한 (dateRestrict)
    if time_range == "day":
        params["dateRestrict"] = "d1"
    elif time_range == "week":
        params["dateRestrict"] = "w1"
    elif time_range == "month":
        params["dateRestrict"] = "m1"
    elif time_range == "year":
        params["dateRestrict"] = "y1"

    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        return {"error": f"Google Search API 오류: {e}"}

    results = []
    for item in data.get("items", []):
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet", "")
        })

    return {"results": results}

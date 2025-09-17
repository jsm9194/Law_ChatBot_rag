# api 호출 예외 안전하게 처리
import requests
from requests.exceptions import RequestException, Timeout

def safe_request(url, params=None, timeout=5):
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()  # 4xx/5xx 발생 시 예외 발생
        return resp
    except Timeout:
        return {"error": "요청이 실패되었습니다. 잠시 후 다시 시도해주세요."}
    except RequestException as e:
        return {"error": f"API 요청 실패: {str(e)}"}

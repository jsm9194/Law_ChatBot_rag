# ⚖️ 법률 RAG 챗봇 (Law ChatBot RAG)

법제처 API와 판례 검색 API를 활용한 **법률 검색/상담 챗봇 서비스**입니다.  
ChatGPT 스타일 UI를 기반으로, 질문에 대한 답변과 함께 **출처(법령/판례 본문)** 를 우측 사이드바에서 확인할 수 있습니다.  

---

## 🚀 주요 기능

- GPT 스타일 UI (좌측 대화 목록 / 중앙 채팅 / 우측 출처 뷰어)
- **법제처 API 연동** → 최신 법령 검색
- **판례 검색 API 연동** → 관련 판례 목록 및 본문 확인
- **RAG (Retrieval-Augmented Generation)** → Qdrant + OpenAI 임베딩 기반 검색
- 출처 버튼 클릭 시, 우측 사이드바에서 법령/판례 원문 확인 (iframe)

---

## 🛠️ 기술 스택

### Frontend
- [React](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- [Vite](https://vitejs.dev/) → 빠른 개발 환경
- [TailwindCSS](https://tailwindcss.com/) v4 → UI 스타일링
- Custom Components (ChatGPT 스타일 채팅창, 사이드바, 출처 뷰어)

### Backend
- [FastAPI](https://fastapi.tiangolo.com/) → API 서버
- 법제처 OpenAPI, 판례 검색 API 연동

### RAG (검색/임베딩)
- [Qdrant](https://qdrant.tech/) → 벡터 DB
- [OpenAI Embedding API](https://platform.openai.com/docs/guides/embeddings)  

---

## 📂 프로젝트 구조

```plaintext
frontend/
 ├─ public/                 # 정적 파일
 ├─ src/
 │   ├─ components/          # UI 컴포넌트
 │   │   ├─ SidebarLeft.tsx  # 좌측 사이드바
 │   │   ├─ ChatMessage.tsx  # 메시지 버블
 │   │   ├─ ChatInput.tsx    # 입력창
 │   │   ├─ ChatArea.tsx     # 중앙 채팅 영역
 │   │   └─ SidebarRight.tsx # 우측 출처 뷰어
 │   ├─ pages/
 │   │   └─ ChatPage.tsx     # 전체 레이아웃 페이지
 │   ├─ App.tsx              # 진입 컴포넌트
 │   ├─ main.tsx             # ReactDOM 진입
 │   └─ index.css            # Tailwind import
 ├─ index.html               # HTML 템플릿
 ├─ package.json
 ├─ tailwind.config.js
 ├─ postcss.config.js
 └─ README.md
````

---

## ▶️ 실행 방법

### 1. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

👉 기본 실행 주소: [http://localhost:5173](http://localhost:5173)

### 2. 백엔드 (FastAPI)

```bash
cd backend
uvicorn main:app --reload
```

👉 기본 실행 주소: [http://localhost:8000](http://localhost:8000)

---

## 📌 향후 개발 계획

* ✅ UI 기본 레이아웃 (ChatGPT 스타일)
* ✅ TailwindCSS v4 세팅
* ⬜ FastAPI ↔ React API 연동
* ⬜ Qdrant 연동 (벡터 검색)
* ⬜ 판례 검색 API 적용
* ⬜ 법령/판례 하이라이트 표시 기능
---

## 👨‍💻 개발자 메모

* 윈도우 PowerShell 환경에서 Vite + Tailwind v4 설치시 `postcss` 설정 필요 → `@tailwindcss/postcss` 사용
* shadcn/ui 대신 **직접 커스텀 컴포넌트**로 구현 (Vite 호환 문제 방지)


## 📸 UI 미리보기

### 전체 레이아웃
![ChatPage Full](public/screenshot_full.png)

### 채팅 화면
![Chat Messages](public/screenshot_chat.png)

### 입력창
![Chat Input](public/screenshot_input.png)

### 출처 뷰어
![Source Sidebar](public/screenshot_source.png)

# 작업내역
<details>
<summary>0917(수)</summary>

## 1. Tool_calling <u>"case_detail"</u> 호출부분 정리
```
{
    "type": "function",
    "function": {
        "name": "case_detail",
        "description": (
            "판례 상세 조회 (사건 ID 기반). "
            "반드시 search_cases 결과에서 받은 사건ID(case_id)를 사용해 호출해야 한다. "
            "예시: 'case_id가 2023001234인 판례 상세 알려줘', "
            "'사건ID 2022005678 판결요지 보여줘', "
            "'case_id 2021009101 판례전문 읽어줘'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"}
            },
            "required": ["case_id"]
        }
    }
}
```

## 2. API 예외처리
**/backend/utils/safe_request.py** 생성 </br>
API 호출중 에러 발생시 표기

query_qdrant.py >> 예외처리 코드 추가
</details>

# 데이터 전처리
<details>
<summary>📂 DATA 폴더 (전처리 규칙)</summary>

### 기존 pdf 추출방식에서 법제처 open api 통해 공식 json 확보로 변경

## 1. 전체 구조 정리
- **원본 JSON 구조**
  - `법령` 키 아래에 `조문`, `부칙`, `별표`, `개정문`, `제개정이유` 등 다양한 메타데이터 존재
- **목표**
  - 최종적으로는 **조문만 남김**
  - `부칙`과 `별표`는 임베딩 대상에서 제외 (필요 시 `Tool Calling`으로 가져오기)

---

## 2. 조문 내 불필요한 키 제거
### ✅ 삭제 대상
`조문변경여부`
`조문이동이전`
`조문이동이후`
`호번호`
`목번호`

### ✅ 유지 대상
`조문번호`
 `조문제목`
 `조문내용`
 `항번호`
 `항내용`
 `호내용`
 `목내용`

---

## 3. 텍스트 정규화
- **항번호 변환**
  - ①②③ 같은 원형 숫자 → 아라비아 숫자 (1, 2, 3 …)
  ```
  <!-- before -->
    "항": [
            {
                "항번호": "①",
                "항내용": "① 사업주는 인체에 해로운 물질, 부패하기 쉬운 물질 또는 악취가 나는 물질 등에 의하여 오염될 우려가 있는 작업장의 바닥이나 벽을 수시로 세척하고 소독하여야 한다."
            },
            {
                "항번호": "②",
                "항내용": "② 사업주는 제1항에 따른 세척 및 소독을 하는 경우에 물이나 그 밖의 액체를 다량으로 사용함으로써 습기가 찰 우려가 있는 작업장의 바닥이나 벽은 불침투성(不浸透性) 재료로 칠하고 배수(排水)에 편리한 구조로 하여야 한다."
            }
         ]

    <!-- after -->
    "항": [
            {
              "항내용": "1 사업주는 인체에 해로운 물질, 부패하기 쉬운 물질 또는 악취가 나는 물질 등에 의하여 오염될 우려가 있는 작업장의 바닥이나 벽을 수시로 세척하고 소독하여야 한다."
            },
            {
              "항내용": "2 사업주는 제1항에 따른 세척 및 소독을 하는 경우에 물이나 그 밖의 액체를 다량으로 사용함으로써 습기가 찰 우려가 있는 작업장의 바닥이나 벽은 불침투성(不浸透性) 재료로 칠하고 배수(排水)에 편리한 구조로 하여야 한다."
            }
          ]
  ```
- **앞뒤 공백 제거**
  - `strip()` 적용
- **백슬래시(`\`) 처리?**
```
"1.  \"중대재해\"란 \"중대산업재해\"와 \"중대시민재해\"를 말한다."
```
  - JSON dump/load 과정에서 보이는 `\"`는 escape일 뿐 실제 텍스트에는 없음
  - 따라서 `text.replace("\\", "")`는 필요없음 → **백슬래시는 건드리지 않음**

---

## 4. 전문(全文) 처리
- `조문여부` 필드가 `"전문"`인 경우 → 장/절 제목  
  - **임베딩 제외** <br> 전문에는 상위 분류개념만 들어있고 내용은 없으며 조문은 숫자로 구분되기 때문에
  ```
        {
            "조문번호": "1",
            "조문시행일자": "20250901",
            "조문변경여부": "N",
            "조문이동이전": "",
            "조문키": "0001000",
            "조문내용": "          제1편 총칙",
            "조문이동이후": "",
            "조문여부": "전문"
        },
        {
            "조문번호": "1",
            "조문시행일자": "20250901",
            "조문변경여부": "N",
            "조문이동이전": "",
            "조문키": "0001000",
            "조문내용": "            제1장 통칙",
            "조문이동이후": "",
            "조문여부": "전문"
        },
  ```
  - 필요하다면 UI에서 트리 구조 표시용 메타데이터로만 사용
- `조문여부` 필드가 `"조문"`인 경우 → 실제 조문 텍스트  
  - **임베딩 포함**

---

## 5. 임베딩 단위 (chunking 전략)
- **항이 없는 조문**
  - `조문내용`만 하나의 chunk
- **항이 있는 조문**
  - `조문내용`은 별도 chunk
  - 각 `항내용`은 개별 chunk
  - 필요 시 `호내용`, `목내용`도 별도 chunk로 분리 가능

---

## ✅ 요약
- **조문만 남기고 임베딩**
- **불필요 키 삭제 + 항번호 숫자 정규화**
- **전문은 임베딩 제외 (원하면 메타로 보존)**
- **chunking은 항 단위까지 고려**

</details>

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
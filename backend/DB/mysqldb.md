# 📘 FastAPI + MySQL 챗봇 서비스 가이드

> 이 문서는 FastAPI 기반 챗봇 서비스를 Docker 환경에서 배포할 때
> 각 파일의 역할과 주요 함수들을 설명하는 **개발자용 구조 가이드**입니다.

---

## 📂 프로젝트 구조

```
📁 project_root/
├── main.py
├── DB/
│   ├── database.py
│   ├── models.py
│   └── crud.py
├── routers/
│   ├── conversations.py
│   └── messages.py

```

---

## ⚙️ `DB/database.py`

> ✅ **데이터베이스 연결 및 세션 관리**

### 역할

- MySQL 연결 URL 정의
- SQLAlchemy 엔진 생성
- 세션 관리(`SessionLocal`)
- 모델 베이스 클래스 생성

### 주요 코드

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "mysql+pymysql://lawChat_admin:3600@mysql:3306/lawdb"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

### 기능 요약

| 함수/변수        | 설명                                            |
| ---------------- | ----------------------------------------------- |
| `engine`         | MySQL과 연결되는 SQLAlchemy 엔진                |
| `SessionLocal()` | 각 요청마다 DB 세션 생성용 팩토리               |
| `Base`           | ORM 모델의 베이스 클래스 (`models.py`에서 상속) |

---

## 🧱 `DB/models.py`

> ✅ **DB 테이블 구조 정의 (ORM 모델)**

### 역할

- MySQL 테이블 매핑 클래스 정의
- Conversation(대화방), ChatLog(대화 내용) 모델 정의
- 관계 설정 (`relationship`)

### 주요 코드

```python
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(50))
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)
    chat_logs = relationship("ChatLog", back_populates="conversation", cascade="all, delete")
```

```python
class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"))
    user_id = Column(String(50))
    role = Column(String(50))
    content = Column(Text)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    conversation = relationship("Conversation", back_populates="chat_logs")
```

---

## 🧩 `DB/crud.py`

> ✅ **DB CRUD(Create, Read, Update, Delete) 함수 모음**

### 역할

FastAPI 라우터(`routers/`)에서 직접 SQL 쿼리를 쓰지 않고,
**모든 DB 조작을 이 파일의 함수로 통일**함.

### 주요 함수

| 함수명                                                      | 설명                         |
| ----------------------------------------------------------- | ---------------------------- |
| `create_conversation(db, user_id, title)`                   | 새 대화방 생성               |
| `get_conversations(db, user_id, limit)`                     | 특정 유저의 대화 목록 조회   |
| `get_conversation_logs(db, conversation_id, offset, limit)` | 특정 대화방의 채팅 로그 조회 |
| `save_message(db, conversation_id, user_id, role, content)` | 메시지 저장                  |
| `update_conversation(db, conversation_id, title)`           | 대화방 제목 수정             |
| `delete_conversation(db, conversation_id)`                  | 대화방 삭제                  |

---

## 🌐 `routers/conversations.py`

> ✅ `/conversation` 관련 REST API 라우터

### 역할

- FastAPI `APIRouter()`를 이용해 대화방 관련 REST API 정의
- CRUD 함수(`crud.py`)를 호출해 DB 조작 수행

### 엔드포인트 목록

| Method   | Endpoint                          | 설명                    |
| -------- | --------------------------------- | ----------------------- |
| `POST`   | `/conversation/new`               | 새 대화방 생성          |
| `GET`    | `/conversations/{user_id}`        | 유저의 대화방 목록 조회 |
| `PATCH`  | `/conversation/{conversation_id}` | 대화방 제목 수정        |
| `DELETE` | `/conversation/{conversation_id}` | 대화방 삭제             |

---

## 💬 `routers/messages.py`

> ✅ `/message` 및 `/conversation/{id}` 관련 라우터

### 역할

- 개별 메시지 저장 및 조회 기능 담당
- CRUD 함수 호출 후 JSON 응답 반환

### 엔드포인트 목록

| Method | Endpoint                          | 설명                         |
| ------ | --------------------------------- | ---------------------------- |
| `POST` | `/message`                        | 새 메시지 저장               |
| `GET`  | `/conversation/{conversation_id}` | 특정 대화방의 전체 로그 조회 |

---

## 🤖 `main.py`

> ✅ **FastAPI 앱의 중심 — 서버 실행 및 주요 엔드포인트 등록**

### 역할 요약

- FastAPI 앱 초기화 및 설정
- CORS 허용 (React 프론트엔드 연결용)
- DB 세션 관리 (`get_db()`)
- `routers/` 폴더의 라우터 등록
- `/ask` 엔드포인트: GPT 기반 대화 처리 (SSE 스트리밍)

### 주요 기능 구성

| 구분                 | 내용                                                               |
| -------------------- | ------------------------------------------------------------------ |
| **1️⃣ 라우터 등록**   | `app.include_router(conversations.router)` 등                      |
| **2️⃣ CORS 설정**     | 모든 Origin 허용 (`allow_origins=["*"]`)                           |
| **3️⃣ DB 세션 관리**  | 요청 단위 세션 생성/해제 (`Depends(get_db)`)                       |
| **4️⃣ GPT 호출 로직** | `client.chat.completions.create()`                                 |
| **5️⃣ 스트리밍 응답** | `StreamingResponse` + `event: chunk` 형식                          |
| **6️⃣ DB 로그 저장**  | `ChatLog`에 user / assistant 메시지 기록                           |
| **7️⃣ 도구 통합**     | `tools/query_qdrant`, `tools/case_api`, `tools/search_google` 활용 |

---

## 🔧 `tools/` 폴더

> ✅ GPT 답변 생성을 돕는 외부 검색 기능

| 파일               | 역할                                   |
| ------------------ | -------------------------------------- |
| `query_qdrant.py`  | Qdrant 벡터 DB를 이용한 법령 문서 검색 |
| `case_api.py`      | 판례 검색 및 상세 조회                 |
| `search_google.py` | 구글 커스텀 검색 API 호출              |
| `tools_config.py`  | 각 툴의 설정 및 설명 메시지 관리       |

---

## 🧠 `prompts/` 폴더

> ✅ GPT 모델에 주입되는 **시스템 프롬프트 템플릿**

| 파일                    | 설명                                   |
| ----------------------- | -------------------------------------- |
| `query_optimization.md` | 검색어를 최적화하는 프롬프트           |
| `search_reranking.md`   | 검색 결과 재정렬 프롬프트              |
| `tool_selection.md`     | 어떤 도구를 사용할지 결정하는 프롬프트 |

---

## ⚙️ 실행 방법 (Docker 기준)

### 1️⃣ `docker-compose.yml` 예시

```yaml
version: "3.9"
services:
  mysql:
    image: mysql:8
    restart: always
    container_name: mysql
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: lawdb
      MYSQL_USER: lawChat_admin
      MYSQL_PASSWORD: 3600
    ports:
      - "3306:3306"
    command: --default-authentication-plugin=mysql_native_password

  fastapi:
    build: .
    container_name: fastapi
    depends_on:
      - mysql
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🚀 실행 순서

```bash
# 1. Docker 빌드
docker-compose build

# 2. 서비스 실행
docker-compose up -d

# 3. FastAPI 문서 확인
http://127.0.0.1:8000/docs
```

---

## ✅ 주요 API 테스트 예시

| 기능           | Method | URL                    | Body 예시                                                                           |
| -------------- | ------ | ---------------------- | ----------------------------------------------------------------------------------- |
| 새 대화 생성   | POST   | `/conversation/new`    | `{"user_id": "user1", "title": "새 대화"}`                                          |
| 대화 목록 조회 | GET    | `/conversations/user1` | -                                                                                   |
| 메시지 저장    | POST   | `/message`             | `{"conversation_id": "abc", "user_id": "user1", "role": "user", "content": "안녕"}` |
| 대화 로그 조회 | GET    | `/conversation/abc`    | -                                                                                   |
| 챗봇 대화      | POST   | `/ask`                 | `{"conversation_id": "abc", "question": "형법상 사기죄 요건은?"}`                   |

---

## 🧾 요약

| 구성 요소     | 역할                              |
| ------------- | --------------------------------- |
| `database.py` | DB 연결 & 세션 관리               |
| `models.py`   | ORM 테이블 정의                   |
| `crud.py`     | DB 접근 함수 (CRUD)               |
| `routers/`    | REST API 라우터 (대화방/메시지)   |
| `main.py`     | FastAPI 앱 중심, `/ask` 핵심 로직 |
| `tools/`      | 외부 검색 / 법령 / 판례 연동      |
| `prompts/`    | GPT 프롬프트 관리                 |

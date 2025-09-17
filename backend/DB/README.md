# 📌 DB 폴더 파일 역할 정리

## 1. **`database.py`**

* **DB 연결 설정 담당**
* SQLAlchemy의 핵심 구성요소 정의

  * `engine` → PostgreSQL 연결 객체
  * `SessionLocal` → DB와 연결된 세션 (CRUD 할 때 사용)
  * `Base` → ORM 모델들이 상속받는 부모 클래스
* FastAPI에서 `Depends(get_db)` 같은 식으로 세션을 꺼낼 때 사용됨

👉 **한 줄 요약:** DB 연결/세션 관리의 중심

---

## 2. **`models.py`**

* **DB 테이블 구조 정의**
* SQLAlchemy ORM 클래스로 테이블 스키마 작성

  * `Conversation` → 대화방 정보 (id, user\_id, title, created\_at)
  * `ChatLog` → 메시지 기록 (id, conversation\_id, user\_id, role, content, created\_at)
* `Base`를 상속받아 테이블로 매핑됨

👉 **한 줄 요약:** DB의 “테이블 설계도”

---

## 3. **`crud.py`**

* **DB에 실제로 데이터를 넣고/빼는 함수 모음**
* 주요 기능:

  * `create_conversation` → 새 대화방 생성
  * `get_conversations` → 특정 유저의 대화방 목록 조회
  * `get_conversation_logs` → 대화방 안의 메시지 기록 조회
  * `save_message` → 메시지 저장
* FastAPI에서 직접 DB에 쿼리하지 않고, 이 CRUD 함수를 통해서만 DB 조작

👉 **한 줄 요약:** DB와 상호작용하는 비즈니스 로직

---

## 4. **`create_tables.py`**

* **테이블 생성 스크립트**
* `Base.metadata.create_all(bind=engine)` 실행 → DB에 `conversations`, `chat_logs` 테이블 생성
* 초기 세팅이나 스키마 바뀌었을 때 실행

👉 **한 줄 요약:** DB에 테이블을 실제로 만드는 파일

---

## 5. **`test_db.py`**

* **DB 연결 테스트용**
* 단순히 `engine.connect()` 해서 “연결 성공!” 메시지 확인
* PostgreSQL 연결 문제 디버깅할 때 사용

👉 **한 줄 요약:** DB 연결이 잘 되는지 확인

---

## 6. **`test_conversation.py`**

* **CRUD 테스트용**
* 흐름:

  1. 새 Conversation 생성
  2. 메시지 저장 (user/assistant)
  3. 대화 목록 불러오기
  4. 특정 대화 로그 불러오기
* DB 기능이 실제로 잘 동작하는지 검증

👉 **한 줄 요약:** Conversation/ChatLog CRUD 기능 검증

---

# ✅ 정리 그림

```
DB/
 ├── database.py        # DB 연결, 세션, Base
 ├── models.py          # ORM 모델 (테이블 정의)
 ├── crud.py            # DB 조작 함수 (CRUD)
 ├── create_tables.py   # 테이블 생성 실행
 ├── test_db.py         # DB 연결 확인
 └── test_conversation.py # CRUD 동작 확인
```

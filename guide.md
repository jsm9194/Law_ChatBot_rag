# Law\_ChatBot\_rag 프로젝트 환경설정 가이드

## 1. 필수 프로그램 설치

1. **Git**

   * [Git 다운로드](https://git-scm.com/downloads)
   * 설치 후 버전 확인:

     ```bash
     git --version
     ```

2. **Docker Desktop**

   * [Docker Desktop 다운로드](https://www.docker.com/products/docker-desktop/)
   * 설치 후 실행 → WSL2 활성화 필요 (Windows일 경우)
   * 버전 확인:

     ```bash
     docker --version
     docker compose version
     ```

3. **Node.js (프론트엔드용)**

   * [Node.js LTS 다운로드](https://nodejs.org/)
   * 설치 후 확인:

     ```bash
     node -v
     npm -v
     ```

4. **Python (백엔드용)**

   * [Python 3.10+ 다운로드](https://www.python.org/downloads/)
   * 확인:

     ```bash
     python --version
     pip --version
     ```

---

## 2. 깃 클론

```bash
git clone <레포지토리주소>
cd Law_ChatBot_rag
```

---

## 3. 환경 변수 설정

1. 프로젝트 루트에 `.env` 파일 만들기:

   ```ini
   OPENAI_API_KEY=sk-xxxxxx
   LAW_OC_ID=   # 법제처 API 키
   POSTGRES_USER=lawuser
   POSTGRES_PASSWORD=lawpass
   POSTGRES_DB=lawdb
   ```

2. `.gitignore`에 이미 `.env`가 들어가 있으므로 Git에는 올라가지 않습니다.

---

## 4. Docker로 DB 실행

> Qdrant + Postgres는 반드시 도커로 실행해야 FastAPI가 붙을 수 있습니다.

### (1) Qdrant 실행

```powershell
docker run -d `
  --name qdrant `
  -p 6333:6333 `
  -v "F:\Desktop\Law_ChatBot_rag\backend\DB\qdrant_storage:/qdrant/storage" `
  qdrant/qdrant
```

### (2) Postgres 실행

```powershell
docker run -d `
  --name pgdb-law `
  -e POSTGRES_USER=lawuser `
  -e POSTGRES_PASSWORD=lawpass `
  -e POSTGRES_DB=lawdb `
  -p 5432:5432 `
  -v "F:\Desktop\Law_ChatBot_rag\backend\DB\postgres_data:/var/lib/postgresql/data" `
  postgres
```

> ⚠️ 윈도우/맥/리눅스마다 경로(`-v`)는 자기 환경에 맞게 수정 필요

### (3) 정상 실행 확인

```bash
docker ps
```

→ `qdrant`, `pgdb-law`가 `STATUS Up`이면 OK

---

## 5. 백엔드 (FastAPI)

1. 가상환경 생성

   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate    # Windows
   source venv/bin/activate   # Mac/Linux
   ```

2. 패키지 설치

   ```bash
   pip install -r requirements.txt
   ```

3. 실행

   ```bash
   uvicorn main:app --reload
   ```

   → `http://localhost:8000` 접속 가능해야 함

---

## 6. 프론트엔드 (React)

1. 설치

   ```bash
   cd frontend
   npm install
   ```

2. 실행

   ```bash
   npm run dev
   ```

   → `http://localhost:5173` 접속 확인

---

## 7. 개발 순서 (매번 실행할 때)

1. Docker Desktop 실행
2. 터미널에서 DB 컨테이너 켜기:

   ```bash
   docker start qdrant pgdb-law
   ```
3. 백엔드 실행:

   ```bash
   cd backend
   uvicorn main:app --reload
   ```
4. 프론트엔드 실행:

   ```bash
   cd frontend
   npm run dev
   ```

---

## 8. 배포 단계 (옵션)

* `docker-compose.yml`을 만들어서 **Postgres + Qdrant + FastAPI + React**를 한 번에 띄울 수 있음
* `restart: always` 옵션을 주면 서버 재부팅 시 자동 실행됨

---

✅ 이렇게 하면 새 컴퓨터에서도 **깃 클론 → 도커 DB 실행 → 백엔드 실행 → 프론트 실행** 순서만 지키면 바로 개발 환경이 돌아갑니다.

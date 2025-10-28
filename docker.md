# 🧠 Law_ChatBot_RAG 배포 가이드 (for Docker)

> ✅ 이 문서는 다른 PC에서 동일한 환경으로 프로젝트를 재현하고 실행하기 위한 가이드입니다.
> Qdrant, MySQL, FastAPI가 Docker Compose로 자동 세팅됩니다.

---

## ⚙️ 1. 필수 설치

### Windows / Mac / Linux 공통

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python (3.11 이상, 선택)
- Git (선택)

---

## 🔑 2. 환경 변수 설정

### `.env` 파일 생성 (프로젝트 루트에)

```bash
# OpenAI / Google API
OPENAI_API_KEY=sk-*********************
LAW_OC_ID=law_oc_id_*************
GOOGLE_API_KEY=AIza********************
GOOGLE_CX=***************

# MySQL
MYSQL_USER=root
MYSQL_PASSWORD=3600
MYSQL_DB=lawdb

# Qdrant
QDRANT_URL=http://qdrant:6333
```

> ⚠️ 실제 발급받은 키와 비밀번호로 교체하세요.

---

## 🐳 3. Docker Compose 구성 (요약)

`docker-compose.yml` 주요 서비스 구성 요약 👇
Vector Loader 는 임베딩 벡터를 생성하는 부분 첫실행시에만 주석해제하고 실행

---

## 🚀 4. 실행 절차

### ✅ 1단계. 도커 빌드 및 실행

```bash
docker compose up --build
```

처음 실행 시 약 1~2분 소요됩니다.
정상적으로 실행되면 아래 메시지가 나타납니다 👇

```
✅ 모든 서비스 준비 완료. FastAPI 시작
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### ✅ 2단계. 백그라운드 실행 (추천)

```bash
docker compose up -d
```

상태 확인:

```bash
docker ps
```

종료:

```bash
docker compose down
```

---

## 🔍 5. 정상 작동 확인

### Qdrant 상태 확인

```bash
curl http://localhost:6333/readyz
```

→ `all shards are ready` 나오면 OK

### FastAPI 테스트

브라우저에서
👉 [http://localhost:8000/docs](http://localhost:8000/docs)
접속 후 API 확인 가능

---

## 🧩 6. (선택) 벡터 재임베딩

만약 새 법령 데이터를 추가하거나 초기화해야 한다면 👇

```bash
docker compose up vector_loader
```

`vector_loader` 컨테이너가 자동으로 Qdrant에 임베딩을 업로드합니다.

---

## 🧹 7. 캐시 / 볼륨 정리

Qdrant나 MySQL 데이터를 초기화하려면:

```bash
docker compose down -v
```

---

## 🧠 참고

| 서비스        | 포트 | 설명           |
| ------------- | ---- | -------------- |
| FastAPI       | 8000 | REST API       |
| Qdrant        | 6333 | 벡터 DB (REST) |
| Qdrant (gRPC) | 6334 | 내부 통신      |
| MySQL         | 3306 | 관계형 DB      |

---

## ✅ 예시 로그

```
qdrant | Access web UI at http://localhost:6333/dashboard
mysql  | [Entrypoint]: MySQL started
fastapi | ✅ 모든 서비스 준비 완료. FastAPI 시작
fastapi | INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## 🧾 요약

| 단계 | 명령어                       | 설명                |
| ---- | ---------------------------- | ------------------- |
| 1    | `git clone <repo>`           | 프로젝트 복제       |
| 2    | `.env` 생성                  | 환경변수 설정       |
| 3    | `docker compose up --build`  | 전체 빌드 & 실행    |
| 4    | `http://localhost:8000/docs` | API 확인            |
| 5    | `docker compose down -v`     | 전체 종료 및 초기화 |

---

## 🎯 Troubleshooting

| 증상                  | 원인                          | 해결법                                      |
| --------------------- | ----------------------------- | ------------------------------------------- |
| Qdrant 연결 실패      | FastAPI에서 localhost 참조 중 | `QDRANT_URL=http://qdrant:6333` 확인        |
| MySQL 연결 실패       | 환경 변수 누락                | `.env`에 MYSQL_HOST=mysql 설정              |
| “curl not found” 에러 | slim 이미지에 curl 미설치     | Dockerfile에 `apt-get install -y curl` 추가 |
| 포트 충돌             | 다른 MySQL 실행 중            | `docker ps`로 확인 후 중복 종료             |

---

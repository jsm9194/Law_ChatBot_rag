# 1️⃣ 기본 이미지
FROM python:3.11-slim

# 2️⃣ 작업 디렉토리
WORKDIR /app

# 3️⃣ 의존성 설치 전 필수 패키지 추가 (여기 추가!)
RUN apt-get update && apt-get install -y netcat-openbsd curl && rm -rf /var/lib/apt/lists/*

# 4️⃣ 의존성 파일 복사
COPY requirements.txt .

# 5️⃣ 파이썬 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 6️⃣ 코드 복사
COPY . .

# 7️⃣ FastAPI 실행 (docker-compose에서 override함)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

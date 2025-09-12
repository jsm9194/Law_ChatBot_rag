# 백엔스 api코드임
# qdrant에서 백터검색하고 gpt로 답변 생성

import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}

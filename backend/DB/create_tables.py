"""
테이블 생성 스크립트
Base.metadata.create_all(bind=engine) 실행 
→ DB에 conversations, chat_logs 테이블 생성
초기 세팅이나 스키마 바뀌었을 때 실행
"""

from database import Base, engine
from models import ChatLog

print("📌 ChatLog 테이블 생성 시도...")
Base.metadata.create_all(bind=engine)
print("✅ ChatLog 테이블 생성 완료!")
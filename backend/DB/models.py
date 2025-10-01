"""
DB 테이블 구조 정의
SQLAlchemy ORM 클래스로 테이블 스키마 작성
Conversation → 대화방 정보 (id, user_id, title, created_at)
ChatLog → 메시지 기록 (id, conversation_id, user_id, role, content, created_at)
Base를 상속받아 테이블로 매핑됨
"""


from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from .database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, index=True)   # UUID
    user_id = Column(String, index=True)                # 사용자 ID
    title = Column(String, nullable=True)               # 대화 제목 (첫 질문 요약 등)
    created_at = Column(DateTime, default=datetime.now)


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))  # 연결
    user_id = Column(String, index=True)
    role = Column(String)       # "user" or "assistant"
    content = Column(Text)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

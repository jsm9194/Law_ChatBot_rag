"""
DB 테이블 구조 정의
SQLAlchemy ORM 클래스로 테이블 스키마 작성
Conversation → 대화방 정보 (id, user_id, title, created_at)
ChatLog → 메시지 기록 (id, conversation_id, user_id, role, content, created_at)
Base를 상속받아 테이블로 매핑됨
"""


from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from DB.database import Base
import uuid


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), index=True, nullable=False)
    title = Column(String(255), default="새 대화")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat_logs = relationship(
        "ChatLog",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"))
    user_id = Column(String(50), index=True, nullable=False)
    role = Column(String(50))
    content = Column(Text)
    summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="chat_logs")

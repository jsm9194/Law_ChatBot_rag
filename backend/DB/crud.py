"""
DB에 실제로 데이터를 넣고/빼는 함수 모음
주요 기능:
create_conversation → 새 대화방 생성
get_conversations → 특정 유저의 대화방 목록 조회
get_conversation_logs → 대화방 안의 메시지 기록 조회
save_message → 메시지 저장
FastAPI에서 직접 DB에 쿼리하지 않고, 이 CRUD 함수를 통해서만 DB 조작
"""

from uuid import uuid4
from sqlalchemy.orm import Session
from models import Conversation, ChatLog

# 새 대화 시작
def create_conversation(db: Session, user_id: str, title: str = None):
    conv_id = str(uuid4())
    conv = Conversation(id=conv_id, user_id=user_id, title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

# 대화 목록 불러오기
def get_conversations(db: Session, user_id: str, limit: int = 20):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .all()
    )

# 특정 대화 메시지 불러오기
def get_conversation_logs(db: Session, conversation_id: str):
    return (
        db.query(ChatLog)
        .filter(ChatLog.conversation_id == conversation_id)
        .order_by(ChatLog.created_at.asc())
        .all()
    )

# 저장
def save_message(db: Session, conversation_id: str, user_id: str, role: str, content: str):
    log = ChatLog(
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        content=content
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
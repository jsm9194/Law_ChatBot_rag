from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from DB.database import SessionLocal
from DB import crud

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class MessageCreate(BaseModel):
    conversation_id: str
    user_id: str
    role: str
    content: str

@router.post("/message")
def save_message(req: MessageCreate, db: Session = Depends(get_db)):
    log = crud.save_message(db, req.conversation_id, req.user_id, req.role, req.content)
    return {"id": log.id, "role": log.role, "content": log.content}

@router.get("/conversation/{conversation_id}")
def get_conversation_logs(conversation_id: str, db: Session = Depends(get_db)):
    logs = crud.get_conversation_logs(db, conversation_id)
    return [{"role": l.role, "content": l.content, "created_at": l.created_at} for l in logs]

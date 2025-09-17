from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from DB.database import SessionLocal
from DB import crud

router = APIRouter()

# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ConversationCreate(BaseModel):
    user_id: str
    title: str | None = None

@router.post("/conversation/new")
def create_conversation(req: ConversationCreate, db: Session = Depends(get_db)):
    conv = crud.create_conversation(db, req.user_id, req.title)
    return {"conversation_id": conv.id, "title": conv.title}

@router.get("/conversations/{user_id}")
def get_conversations(user_id: str, db: Session = Depends(get_db)):
    convs = crud.get_conversations(db, user_id)
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in convs]

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

class ConversationUpdate(BaseModel):
    title: str | None = None

@router.post("/conversation/new")
def create_conversation(req: ConversationCreate, db: Session = Depends(get_db)):
    conv = crud.create_conversation(db, req.user_id, req.title)
    return {"conversation_id": conv.id, "title": conv.title}


@router.get("/conversation/{conversation_id}")
def get_logs(
    conversation_id: str,
    offset: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    logs = crud.get_conversation_logs(db, conversation_id, offset=offset, limit=limit)
    return logs



# ✅ 대화 제목 변경
@router.patch("/conversation/{conversation_id}")
def update_conversation(conversation_id: str, req: ConversationUpdate, db: Session = Depends(get_db)):
    conv = crud.update_conversation(db, conversation_id, req.title)
    return {"id": conv.id, "title": conv.title}


# ✅ 대화 삭제
@router.delete("/conversation/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    crud.delete_conversation(db, conversation_id)
    return {"message": "deleted"}
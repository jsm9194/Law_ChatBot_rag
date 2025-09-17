"""
CRUD 테스트용
흐름:
새 Conversation 생성
메시지 저장 (user/assistant)
대화 목록 불러오기
특정 대화 로그 불러오기
DB 기능이 실제로 잘 동작하는지 검증
"""

from database import SessionLocal
import crud

db = SessionLocal()

# 1. 새 대화 시작
conv = crud.create_conversation(db, user_id="user1", title="산업안전보건법 질문")
print("새 대화:", conv.id, conv.title)

# 2. 메시지 저장
crud.save_message(db, conv.id, "user1", "user", "산업안전보건법 제2조 알려줘")
crud.save_message(db, conv.id, "user1", "assistant", "제2조는 정의 규정입니다...")

# 3. 유저의 대화 목록 확인
convs = crud.get_conversations(db, "user1")
print("대화 목록:", [(c.id, c.title) for c in convs])

# 4. 특정 대화 로그 확인
logs = crud.get_conversation_logs(db, conv.id)
print("대화 로그:", [(l.role, l.content) for l in logs])

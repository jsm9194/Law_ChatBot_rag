"""
DB 연결 테스트용
단순히 engine.connect() 해서 “연결 성공!” 메시지 확인
PostgreSQL 연결 문제 디버깅할 때 사용
"""
from database import engine

try:
    conn = engine.connect()
    print("✅ PostgreSQL 연결 성공!")
    conn.close()
except Exception as e:
    print("❌ 연결 실패:", e)

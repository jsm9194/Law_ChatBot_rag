# DB 연결 설정
# SQLAlchemy 핵심 구성요소 정의 (엔진, 세션, 베이스) 

""" 
engine → PostgreSQL 연결 객체
SessionLocal → DB와 연결된 세션 (CRUD 할 때 사용)
Base → ORM 모델들이 상속받는 부모 클래스
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ⚠️ 본인 계정/비번/DB명 맞게 수정
DATABASE_URL = "postgresql://lawChat_admin:3600@localhost:5432/lawdb"

# DB 엔진 생성
engine = create_engine(DATABASE_URL, echo=True)

# 세션 팩토리 (DB 연결 세션)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 (모든 모델들이 이걸 상속받음)
Base = declarative_base()

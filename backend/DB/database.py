# DB 연결 설정
# SQLAlchemy 핵심 구성요소 정의 (엔진, 세션, 베이스) 

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 🔹 MySQL 연결 문자열로 변경
DATABASE_URL = "mysql+pymysql://lawChat_admin:3600@mysql:3306/lawdb"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
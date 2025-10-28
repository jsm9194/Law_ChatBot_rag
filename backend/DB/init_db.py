import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from DB.database import Base, engine
import DB.models  

def init_db():
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully!")


if __name__ == "__main__":
    init_db()


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Database se connection ka engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Session create karna
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Yeh hai wo 'Base' jise Alembic dhundh raha tha!
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
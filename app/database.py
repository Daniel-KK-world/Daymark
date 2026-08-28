from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Add pool settings to prevent connection exhaustion
engine = create_engine(
    settings.database_url,
    pool_size=5,           # Max connections in pool
    max_overflow=10,       # Extra connections when pool is full
    pool_timeout=30,       # Timeout for getting a connection
    pool_recycle=1800,     # Recycle connections after 30 mins
    pool_pre_ping=True     # Check connection before using
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
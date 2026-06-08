import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Database URL read from environment variable, with a fallback for local dev
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost/uzanet")

# Create the engine

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,        # Always test for connection liveness, best catch-all!
    pool_recycle=280,          # Force SQLA to reconnect after X seconds (well under MySQL's wait_timeout)
)
# Create a configured Session class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

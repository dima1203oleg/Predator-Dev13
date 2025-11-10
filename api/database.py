"""
PostgreSQL Database Configuration
Predator Analytics v13
"""
import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

# Database URLs
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://predator:predator_secret@localhost:5432/predator_analytics"
)
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# SQLAlchemy Engine
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    echo=False
)

# Async Engine
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    poolclass=NullPool,
    echo=False
)

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Base for ORM Models
Base = declarative_base()
metadata = MetaData()

# Dependency for FastAPI
def get_db():
    """Get database session for FastAPI dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db():
    """Get async database session"""
    async with AsyncSessionLocal() as session:
        yield session

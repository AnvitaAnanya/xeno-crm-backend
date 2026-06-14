from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

def get_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return create_async_engine(url, echo=False)

def get_session_factory():
    return sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False
    )

async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        yield session
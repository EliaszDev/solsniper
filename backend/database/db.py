"""SQLite engine + session factory."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = "sqlite+aiosqlite:///./solsniper.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def init_db():
    """Create tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

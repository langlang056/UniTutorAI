"""Database models and session management."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime
from app.config import get_settings

Base = declarative_base()


class PDFDocument(Base):
    """Stores metadata about uploaded PDFs."""

    __tablename__ = "pdf_documents"

    id = Column(String, primary_key=True)  # SHA256 hash of file content
    filename = Column(String, nullable=False)
    total_pages = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    # 处理状态
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    processed_pages = Column(Integer, default=0)  # 已处理的页数
    selected_pages_count = Column(Integer, default=0)  # 选定要处理的页数（用于进度计算）


class PageExplanationCache(Base):
    """Caches AI-generated explanations to avoid redundant API calls."""

    __tablename__ = "page_explanations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pdf_id = Column(String, nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    page_type = Column(String, default="CONTENT")
    explanation_json = Column(Text, nullable=False)  # Stored as JSON string (now Markdown)
    summary = Column(Text, nullable=True)  # 页面摘要，用于上下文传递
    created_at = Column(DateTime, default=datetime.utcnow)


# Async engine setup
settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

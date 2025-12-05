"""Caching service to avoid redundant LLM calls."""
import json
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import PageExplanationCache, PDFDocument
from app.models.schemas import PageExplanation, PageExplanationMarkdown


class CacheService:
    """Handles reading/writing explanation cache."""

    @staticmethod
    async def get_cached_explanation(
        db: AsyncSession, pdf_id: str, page_number: int
    ) -> PageExplanation | None:
        """
        Retrieve cached explanation for a specific page.

        Returns:
            PageExplanation if cache hit, None if cache miss
        """
        stmt = select(PageExplanationCache).where(
            PageExplanationCache.pdf_id == pdf_id,
            PageExplanationCache.page_number == page_number,
        )
        result = await db.execute(stmt)
        cache_entry = result.scalar_one_or_none()

        if cache_entry:
            # Deserialize JSON to Pydantic model
            explanation_dict = json.loads(cache_entry.explanation_json)
            return PageExplanation(**explanation_dict)

        return None

    @staticmethod
    async def get_cached_markdown_explanation(
        db: AsyncSession, pdf_id: str, page_number: int
    ) -> PageExplanationMarkdown | None:
        """
        Retrieve cached Markdown explanation for a specific page.
        """
        stmt = select(PageExplanationCache).where(
            PageExplanationCache.pdf_id == pdf_id,
            PageExplanationCache.page_number == page_number,
        )
        result = await db.execute(stmt)
        cache_entry = result.scalar_one_or_none()

        if cache_entry:
            return PageExplanationMarkdown(
                page_number=page_number,
                markdown_content=cache_entry.explanation_json,
                summary=cache_entry.summary or ""
            )

        return None

    @staticmethod
    async def save_explanation(
        db: AsyncSession, pdf_id: str, page_number: int, explanation: PageExplanation
    ):
        """Save explanation to cache."""
        # Serialize Pydantic model to JSON
        explanation_json = explanation.model_dump_json()

        cache_entry = PageExplanationCache(
            pdf_id=pdf_id,
            page_number=page_number,
            page_type=explanation.page_type,
            explanation_json=explanation_json,
        )

        db.add(cache_entry)
        await db.commit()

    @staticmethod
    async def save_markdown_explanation(
        db: AsyncSession, pdf_id: str, page_number: int, 
        markdown_content: str, summary: str
    ):
        """Save Markdown explanation to cache."""
        cache_entry = PageExplanationCache(
            pdf_id=pdf_id,
            page_number=page_number,
            page_type="CONTENT",
            explanation_json=markdown_content,
            summary=summary,
        )

        db.add(cache_entry)
        await db.commit()

    @staticmethod
    async def get_previous_summaries(
        db: AsyncSession, pdf_id: str, current_page: int, max_pages: int = 3
    ) -> List[str]:
        """
        Get summaries from previous pages for context.
        
        Args:
            db: Database session
            pdf_id: PDF identifier
            current_page: Current page number
            max_pages: Maximum number of previous pages to include
            
        Returns:
            List of summary strings
        """
        start_page = max(1, current_page - max_pages)
        
        stmt = select(PageExplanationCache).where(
            PageExplanationCache.pdf_id == pdf_id,
            PageExplanationCache.page_number >= start_page,
            PageExplanationCache.page_number < current_page,
        ).order_by(PageExplanationCache.page_number)
        
        result = await db.execute(stmt)
        cache_entries = result.scalars().all()
        
        summaries = []
        for entry in cache_entries:
            if entry.summary:
                summaries.append(entry.summary)
        
        return summaries

    @staticmethod
    async def get_all_explanations(
        db: AsyncSession, pdf_id: str
    ) -> List[PageExplanationCache]:
        """Get all explanations for a PDF."""
        stmt = select(PageExplanationCache).where(
            PageExplanationCache.pdf_id == pdf_id
        ).order_by(PageExplanationCache.page_number)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_pdf_metadata(db: AsyncSession, pdf_id: str) -> PDFDocument | None:
        """Get PDF document metadata."""
        stmt = select(PDFDocument).where(PDFDocument.id == pdf_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def save_pdf_metadata(
        db: AsyncSession,
        pdf_id: str,
        filename: str,
        total_pages: int,
        file_path: str,
    ):
        """Save uploaded PDF metadata (or update if exists)."""
        # 先检查是否存在
        existing = await CacheService.get_pdf_metadata(db, pdf_id)
        if existing:
            # 更新现有记录
            stmt = update(PDFDocument).where(PDFDocument.id == pdf_id).values(
                filename=filename,
                total_pages=total_pages,
                file_path=file_path,
                processing_status="pending",
                processed_pages=0,
                selected_pages_count=0,
            )
            await db.execute(stmt)
        else:
            # 创建新记录
            pdf_doc = PDFDocument(
                id=pdf_id,
                filename=filename,
                total_pages=total_pages,
                file_path=file_path,
                processing_status="pending",
                processed_pages=0,
                selected_pages_count=0,
            )
            db.add(pdf_doc)
        await db.commit()

    @staticmethod
    async def update_processing_status(
        db: AsyncSession, pdf_id: str, status: str, processed_pages: int
    ):
        """Update PDF processing status."""
        stmt = update(PDFDocument).where(PDFDocument.id == pdf_id).values(
            processing_status=status,
            processed_pages=processed_pages
        )
        await db.execute(stmt)
        await db.commit()

    @staticmethod
    async def check_pdf_exists(db: AsyncSession, pdf_id: str) -> bool:
        """Check if PDF has been processed before."""
        stmt = select(PDFDocument).where(PDFDocument.id == pdf_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


cache_service = CacheService()

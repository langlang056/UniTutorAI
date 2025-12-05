"""FastAPI application entry point."""
import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from app.config import get_settings
from app.models.database import init_db, get_db
from app.models.schemas import (
    UploadResponse,
    PageExplanation,
    ErrorResponse,
)
from app.services.pdf_parser import pdf_parser
from app.services.cache_service import cache_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup/shutdown events."""
    # Startup: Initialize database and create upload directories
    await init_db()
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.temp_dir).mkdir(exist_ok=True)
    print(f"✅ Database initialized")
    print(f"✅ Upload directory: {settings.upload_dir}")
    yield
    # Shutdown: cleanup if needed
    print("👋 Shutting down UniTutor AI")


app = FastAPI(
    title="UniTutor AI Backend",
    description="Multi-Agent Courseware Explainer API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "UniTutor AI Backend is running",
        "version": "1.0.0",
        "status": "healthy",
    }


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and parse a PDF file.

    Steps:
    1. Validate file format and size
    2. Calculate PDF hash to check for duplicates
    3. Save file to upload directory
    4. Parse with LlamaParse
    5. Store metadata in database

    Returns:
        UploadResponse with pdf_id and total_pages
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read file content
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)

    if file_size_mb > settings.max_file_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.max_file_size_mb}MB",
        )

    # Save file temporarily to calculate hash
    temp_path = Path(settings.temp_dir) / file.filename
    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        # Generate PDF ID (hash)
        pdf_id = pdf_parser._generate_pdf_id(str(temp_path))

        # Check if already processed
        if await cache_service.check_pdf_exists(db, pdf_id):
            # Return existing metadata
            pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
            return UploadResponse(
                pdf_id=pdf_id,
                total_pages=pdf_doc.total_pages,
                filename=file.filename,
                message="PDF already exists in cache",
            )

        # Move to permanent storage
        final_path = Path(settings.upload_dir) / f"{pdf_id}.pdf"
        temp_path.rename(final_path)

        # Get page count (quick method without full parsing)
        total_pages = pdf_parser.get_page_count(str(final_path))

        # Save metadata
        await cache_service.save_pdf_metadata(
            db,
            pdf_id=pdf_id,
            filename=file.filename,
            total_pages=total_pages,
            file_path=str(final_path),
        )

        return UploadResponse(
            pdf_id=pdf_id,
            total_pages=total_pages,
            filename=file.filename,
        )

    except Exception as e:
        # Cleanup on error
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/explain/{pdf_id}/{page_number}", response_model=PageExplanation)
async def get_explanation(
    pdf_id: str,
    page_number: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-generated explanation for a specific page.

    Steps:
    1. Check cache first
    2. If cache miss, parse the page with LlamaParse
    3. Return raw text (Phase 2 will add LangGraph processing)

    Args:
        pdf_id: Unique PDF identifier
        page_number: 1-indexed page number

    Returns:
        PageExplanation with structured content
    """
    # Verify PDF exists
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(status_code=404, detail="PDF not found")

    if page_number < 1 or page_number > pdf_doc.total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid page number. Must be between 1 and {pdf_doc.total_pages}",
        )

    # 禁用缓存 - 每次都重新生成
    # cached = await cache_service.get_cached_explanation(db, pdf_id, page_number)
    # if cached:
    #     return cached

    # Parse the page
    try:
        page_text = await pdf_parser.parse_single_page(pdf_doc.file_path, page_number)

        # Use LLM to generate explanation
        from app.services.llm_service import llm_service
        from app.models.schemas import PageContent, KeyPoint
        import json

        # Create prompt for LLM
        system_message = """你是一个优秀的大学课程讲解助手。你的任务是将复杂的学术内容转化为通俗易懂的中文解释。

请分析提供的课件页面内容,并按以下 JSON 格式返回:
{
  "page_type": "TITLE 或 CONTENT 或 END",
  "summary": "页面内容的简洁中文摘要(2-3句话)",
  "key_points": [
    {
      "concept": "核心概念名称",
      "explanation": "用通俗语言解释这个概念",
      "is_important": true 或 false
    }
  ],
  "analogy": "用日常生活中的类比来解释核心内容",
  "example": "一个具体的例子来说明概念",
  "original_language": "en 或 fr 或 zh 或 mixed"
}

注意:
1. 如果是标题页/封面,page_type 为 "TITLE"
2. 如果是结束页/参考文献,page_type 为 "END"
3. 类比要贴近生活,容易理解
4. 关键概念要抓住最重要的 2-3 个"""

        user_prompt = f"""请分析以下课件第 {page_number} 页的内容,并生成中文讲解:

{page_text}

请严格按照 JSON 格式返回结果。"""

        # Generate explanation with LLM
        llm_response = await llm_service.generate_text(
            prompt=user_prompt,
            system_message=system_message,
            temperature=0.3,
        )

        # Parse LLM response
        try:
            # Try to extract JSON from response
            # LLM might wrap JSON in markdown code blocks
            response_text = llm_response.strip()

            # Log raw response for debugging
            print(f"🔍 Raw LLM response preview: {response_text[:200]}...")

            # Remove markdown code blocks if present
            if "```json" in response_text:
                # Extract content between ```json and ```
                parts = response_text.split("```json")
                if len(parts) > 1:
                    json_part = parts[1].split("```")[0].strip()
                    response_text = json_part
                    print(f"✅ Extracted JSON from ```json block")
            elif "```" in response_text:
                # Extract content between ``` and ```
                parts = response_text.split("```")
                if len(parts) >= 3:
                    response_text = parts[1].strip()
                    print(f"✅ Extracted JSON from ``` block")

            # Try to find JSON object if response has extra text
            if not response_text.startswith("{"):
                # Find first { and last }
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    response_text = response_text[start_idx:end_idx+1]
                    print(f"✅ Extracted JSON object from text")

            print(f"📝 Parsing JSON (length: {len(response_text)})")
            llm_data = json.loads(response_text)
            print(f"✅ Successfully parsed JSON response")

            # Build explanation from LLM response
            key_points = [
                KeyPoint(
                    concept=kp.get("concept", ""),
                    explanation=kp.get("explanation", ""),
                    is_important=kp.get("is_important", False),
                )
                for kp in llm_data.get("key_points", [])
            ]

            explanation = PageExplanation(
                page_number=page_number,
                page_type=llm_data.get("page_type", "CONTENT"),
                content=PageContent(
                    summary=llm_data.get("summary", ""),
                    key_points=key_points,
                    analogy=llm_data.get("analogy", ""),
                    example=llm_data.get("example", ""),
                ),
                original_language=llm_data.get("original_language", "mixed"),
            )

        except json.JSONDecodeError as e:
            # Fallback: use raw LLM response
            print(f"❌ Failed to parse LLM JSON: {str(e)}")
            print(f"❌ Response text that failed: {response_text[:500]}...")
            explanation = PageExplanation(
                page_number=page_number,
                page_type="CONTENT",
                content=PageContent(
                    summary=llm_response[:500],
                    key_points=[
                        KeyPoint(
                            concept="AI 生成的解释",
                            explanation=llm_response,
                            is_important=True,
                        )
                    ],
                    analogy="",
                    example="",
                ),
                original_language="mixed",
            )
        except Exception as e:
            print(f"❌ Unexpected error parsing LLM response: {str(e)}")
            raise

        # 禁用缓存 - 不保存到数据库
        # await cache_service.save_explanation(db, pdf_id, page_number, explanation)

        return explanation

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process page: {str(e)}"
        )


@app.get("/api/pdf/{pdf_id}/info")
async def get_pdf_info(pdf_id: str, db: AsyncSession = Depends(get_db)):
    """Get PDF metadata."""
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(status_code=404, detail="PDF not found")

    return {
        "pdf_id": pdf_doc.id,
        "filename": pdf_doc.filename,
        "total_pages": pdf_doc.total_pages,
        "uploaded_at": pdf_doc.uploaded_at.isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

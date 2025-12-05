"""PPT Helper - FastAPI 后端"""
import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import json

from app.config import get_settings
from app.models.database import init_db, get_db
from app.models.schemas import UploadResponse, PageExplanation, PageContent, KeyPoint
from app.services.pdf_parser import pdf_parser
from app.services.cache_service import cache_service
from app.services.llm_service import llm_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭生命周期"""
    await init_db()
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.temp_dir).mkdir(exist_ok=True)
    print(f"✅ 数据库已初始化")
    print(f"✅ 上传目录: {settings.upload_dir}")
    yield
    print("👋 关闭服务")


app = FastAPI(title="PPT Helper API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "PPT Helper API", "version": "0.3.0", "status": "running"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """上传并解析 PDF"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    content = await file.read()
    if len(content) / (1024 * 1024) > settings.max_file_size_mb:
        raise HTTPException(400, f"文件过大，最大 {settings.max_file_size_mb}MB")

    temp_path = Path(settings.temp_dir) / file.filename
    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        pdf_id = pdf_parser._generate_pdf_id(str(temp_path))

        # 检查是否已存在
        if await cache_service.check_pdf_exists(db, pdf_id):
            pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
            return UploadResponse(
                pdf_id=pdf_id,
                total_pages=pdf_doc.total_pages,
                filename=file.filename,
                message="PDF 已存在缓存中",
            )

        # 移动到永久存储
        final_path = Path(settings.upload_dir) / f"{pdf_id}.pdf"
        temp_path.rename(final_path)

        total_pages = pdf_parser.get_page_count(str(final_path))

        await cache_service.save_pdf_metadata(
            db, pdf_id, file.filename, total_pages, str(final_path)
        )

        return UploadResponse(pdf_id=pdf_id, total_pages=total_pages, filename=file.filename)

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(500, f"上传失败: {str(e)}")


@app.get("/api/explain/{pdf_id}/{page_number}", response_model=PageExplanation)
async def get_explanation(pdf_id: str, page_number: int, db: AsyncSession = Depends(get_db)):
    """获取页面 AI 解释"""
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")

    if not (1 <= page_number <= pdf_doc.total_pages):
        raise HTTPException(400, f"页码无效，范围: 1-{pdf_doc.total_pages}")

    try:
        # 提取页面图像
        page_image = await pdf_parser.parse_single_page(pdf_doc.file_path, page_number)

        # 构建 prompt
        system_message = """你是大学课程讲解助手。分析PPT图像，用中文通俗解释。

返回JSON格式:
{
  "page_type": "TITLE/CONTENT/END",
  "summary": "简洁摘要(2-3句)",
  "key_points": [{"concept": "概念", "explanation": "通俗解释", "is_important": true}],
  "analogy": "生活类比(可选)",
  "example": "具体例子(可选)",
  "original_language": "en/zh/mixed"
}

要求: 抓住2-3个关键概念，解释简洁清晰。"""

        user_prompt = f"""分析第{page_number}页，返回完整JSON，不要截断。"""

        # 调用 Gemini Vision
        llm_response = await llm_service.analyze_image(
            image=page_image,
            prompt=user_prompt,
            system_message=system_message,
            temperature=0.3,
            max_tokens=8000,
        )

        # 解析 JSON
        try:
            response_text = llm_response.strip()
            print(f"🔍 响应预览: {response_text[:200]}...")

            # 提取 JSON（处理 markdown 代码块）
            if "```json" in response_text:
                parts = response_text.split("```json")
                if len(parts) > 1:
                    response_text = parts[1].split("```")[0].strip()
                    print("✅ 已提取 JSON")
            elif "```" in response_text:
                parts = response_text.split("```")
                if len(parts) >= 3:
                    response_text = parts[1].strip()
                    print("✅ 已提取 JSON")

            # 查找 JSON 对象边界
            if not response_text.startswith("{"):
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    response_text = response_text[start:end+1]
                    print("✅ 已提取 JSON 对象")

            # 修复不完整的 JSON
            if response_text.startswith("{") and not response_text.rstrip().endswith("}"):
                print("⚠️ JSON 被截断，尝试修复...")
                response_text = response_text.rstrip()
                if response_text.endswith(","):
                    response_text = response_text[:-1]
                if response_text.count('"') % 2 != 0:
                    response_text += '"'
                response_text += "}" * (response_text.count("{") - response_text.count("}"))
                response_text += "]" * (response_text.count("[") - response_text.count("]"))
                print(f"✅ 修复完成")

            print(f"📝 解析 JSON ({len(response_text)} 字符)")
            llm_data = json.loads(response_text)
            print("✅ JSON 解析成功")

            # 构建响应
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
            print(f"❌ JSON 解析失败: {str(e)}")
            print(f"❌ 失败文本: {response_text[:500]}...")
            # 降级方案：使用原始响应
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

        return explanation

    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")


@app.get("/api/pdf/{pdf_id}/info")
async def get_pdf_info(pdf_id: str, db: AsyncSession = Depends(get_db)):
    """获取 PDF 元数据"""
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")

    return {
        "pdf_id": pdf_doc.id,
        "filename": pdf_doc.filename,
        "total_pages": pdf_doc.total_pages,
        "uploaded_at": pdf_doc.uploaded_at.isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)

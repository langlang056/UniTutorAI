"""PPT Helper - FastAPI 后端"""
import os
import asyncio
import base64
import io
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import json

from app.config import get_settings
from app.models.database import init_db, get_db, AsyncSessionLocal
from app.models.schemas import (
    UploadResponse, PageExplanation, PageContent, KeyPoint,
    PageExplanationMarkdown, ProcessingProgress
)
from app.services.pdf_parser import pdf_parser
from app.services.cache_service import cache_service
from app.services.llm_service import llm_service

settings = get_settings()

# 存储正在处理的任务
processing_tasks = {}


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


app = FastAPI(title="PPT Helper API", version="0.4.0", lifespan=lifespan)

# CORS 配置：支持开发环境和生产环境
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        # 生产环境需要添加你的服务器地址，如:
        # "http://192.168.1.100",
        # "http://yourdomain.com",
        "*"  # 开发时使用，生产环境建议指定具体域名
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "PPT Helper API", "version": "0.4.0", "status": "running"}


async def process_pdf_background(pdf_id: str, file_path: str, page_numbers: list[int]):
    """后台任务：按顺序处理指定页面"""
    total_pages_to_process = len(page_numbers)
    print(f"🚀 开始后台处理 PDF: {pdf_id}, 处理 {total_pages_to_process} 页: {page_numbers}")
    
    try:
        async with AsyncSessionLocal() as db:
            # 更新状态为处理中
            await cache_service.update_processing_status(db, pdf_id, "processing", 0)
        
        processed_count = 0
        for page_number in page_numbers:
            print(f"📄 处理第 {page_number} 页 ({processed_count + 1}/{total_pages_to_process})...")
            
            try:
                async with AsyncSessionLocal() as db:
                    # 检查是否已有缓存
                    cached = await cache_service.get_cached_markdown_explanation(db, pdf_id, page_number)
                    if cached:
                        print(f"✅ 第 {page_number} 页已有缓存，跳过")
                        processed_count += 1
                        await cache_service.update_processing_status(db, pdf_id, "processing", processed_count)
                        continue
                
                # 提取页面图像
                print(f"  📸 提取页面图像...")
                page_image = await pdf_parser.parse_single_page(file_path, page_number)
                
                async with AsyncSessionLocal() as db:
                    # 获取前面页面的摘要作为上下文
                    previous_summaries = await cache_service.get_previous_summaries(
                        db, pdf_id, page_number, max_pages=3
                    )
                
                # 调用 LLM 生成解释
                print(f"  🤖 调用 LLM 分析...")
                markdown_content = await llm_service.analyze_image(
                    image=page_image,
                    page_num=page_number,
                    previous_summaries=previous_summaries,
                    temperature=0.7,
                    max_tokens=4000,
                )
                
                # 提取摘要
                summary = llm_service.extract_summary(markdown_content, page_number)
                
                async with AsyncSessionLocal() as db:
                    # 保存到缓存
                    await cache_service.save_markdown_explanation(
                        db, pdf_id, page_number, markdown_content, summary
                    )
                    
                    # 更新进度
                    processed_count += 1
                    await cache_service.update_processing_status(db, pdf_id, "processing", processed_count)
                
                print(f"✅ 第 {page_number} 页处理完成")
                
                # 小延迟避免 API 限流
                await asyncio.sleep(1)
                
            except Exception as e:
                import traceback
                print(f"❌ 处理第 {page_number} 页失败: {str(e)}")
                print(f"  详细错误: {traceback.format_exc()}")
                # 继续处理下一页
                continue
        
        # 处理完成
        async with AsyncSessionLocal() as db:
            await cache_service.update_processing_status(db, pdf_id, "completed", processed_count)
        print(f"🎉 PDF {pdf_id} 选定页面全部处理完成 ({processed_count}/{total_pages_to_process})")
        
    except Exception as e:
        import traceback
        print(f"❌ 后台处理失败: {str(e)}")
        print(f"  详细错误: {traceback.format_exc()}")
        try:
            async with AsyncSessionLocal() as db:
                await cache_service.update_processing_status(db, pdf_id, "failed", 0)
        except:
            pass
    finally:
        # 清理任务记录
        if pdf_id in processing_tasks:
            del processing_tasks[pdf_id]


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    """上传并解析 PDF，启动后台处理"""
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
            if temp_path.exists():
                temp_path.unlink()
            if pdf_doc:
                return UploadResponse(
                    pdf_id=pdf_id,
                    total_pages=pdf_doc.total_pages,
                    filename=file.filename,
                    message="PDF 已存在缓存中",
                )
            else:
                # PDF 存在但元数据丢失，重新处理
                pass

        # 移动到永久存储
        final_path = Path(settings.upload_dir) / f"{pdf_id}.pdf"
        if final_path.exists():
            # 如果目标文件已存在，删除临时文件
            if temp_path.exists():
                temp_path.unlink()
        else:
            temp_path.rename(final_path)

        total_pages = pdf_parser.get_page_count(str(final_path))

        await cache_service.save_pdf_metadata(
            db, pdf_id, file.filename, total_pages, str(final_path)
        )

        # 不再自动启动后台处理，等待用户手动触发
        return UploadResponse(
            pdf_id=pdf_id, 
            total_pages=total_pages, 
            filename=file.filename,
            message="PDF 已上传，请选择页码后开始分析"
        )

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(500, f"上传失败: {str(e)}")


@app.post("/api/process/{pdf_id}")
async def start_processing(
    pdf_id: str, 
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """启动处理指定页码"""
    # 获取 PDF 元数据
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")
    
    # 检查是否已经在处理中（且任务仍在运行）
    if pdf_id in processing_tasks:
        task = processing_tasks[pdf_id]
        if not task.done():
            raise HTTPException(400, "该 PDF 正在处理中")
        else:
            # 任务已完成，清理记录
            del processing_tasks[pdf_id]
    
    # 获取要处理的页码列表
    page_numbers = request.get("page_numbers", [])
    if not page_numbers:
        raise HTTPException(400, "请提供要处理的页码列表")
    
    # 验证页码
    total_pages = pdf_doc.total_pages
    invalid_pages = [p for p in page_numbers if p < 1 or p > total_pages]
    if invalid_pages:
        raise HTTPException(400, f"页码无效: {invalid_pages}，有效范围: 1-{total_pages}")
    
    # 更新选定页数
    async with AsyncSessionLocal() as update_db:
        from sqlalchemy import update
        from app.models.database import PDFDocument
        stmt = update(PDFDocument).where(PDFDocument.id == pdf_id).values(
            selected_pages_count=len(page_numbers),
            processed_pages=0,
            processing_status="pending"
        )
        await update_db.execute(stmt)
        await update_db.commit()
    
    # 启动后台处理任务
    task = asyncio.create_task(
        process_pdf_background(pdf_id, pdf_doc.file_path, page_numbers)
    )
    processing_tasks[pdf_id] = task
    
    return {
        "message": f"已启动处理 {len(page_numbers)} 页",
        "page_numbers": page_numbers
    }


@app.get("/api/progress/{pdf_id}", response_model=ProcessingProgress)
async def get_progress(pdf_id: str, db: AsyncSession = Depends(get_db)):
    """获取 PDF 处理进度"""
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")

    # 使用选定页数计算进度，如果没有选定则使用总页数
    total_for_progress = pdf_doc.selected_pages_count if pdf_doc.selected_pages_count > 0 else pdf_doc.total_pages
    progress_percentage = (pdf_doc.processed_pages / total_for_progress * 100) if total_for_progress > 0 else 0

    return ProcessingProgress(
        pdf_id=pdf_id,
        total_pages=total_for_progress,  # 返回选定的页数
        processed_pages=pdf_doc.processed_pages,
        status=pdf_doc.processing_status or "pending",
        progress_percentage=round(progress_percentage, 1)
    )


@app.get("/api/explain/{pdf_id}/{page_number}", response_model=PageExplanationMarkdown)
async def get_explanation(pdf_id: str, page_number: int, db: AsyncSession = Depends(get_db)):
    """获取页面 AI 解释（Markdown 格式）"""
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")

    if not (1 <= page_number <= pdf_doc.total_pages):
        raise HTTPException(400, f"页码无效，范围: 1-{pdf_doc.total_pages}")

    # 尝试从缓存获取
    cached = await cache_service.get_cached_markdown_explanation(db, pdf_id, page_number)
    if cached:
        return cached

    # 如果没有缓存，说明后台任务还没处理到这一页
    # 返回一个处理中的提示
    return PageExplanationMarkdown(
        page_number=page_number,
        markdown_content="⏳ **正在生成中...**\n\n该页面正在后台处理中，请稍候刷新。",
        summary=""
    )


@app.get("/api/download/{pdf_id}")
async def download_markdown(pdf_id: str, db: AsyncSession = Depends(get_db)):
    """下载完整的 Markdown 文件（包含页面截图）"""
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")

    if pdf_doc.processing_status != "completed":
        raise HTTPException(400, f"PDF 尚未处理完成，当前状态: {pdf_doc.processing_status}")

    # 获取所有解释
    explanations = await cache_service.get_all_explanations(db, pdf_id)
    
    if not explanations:
        raise HTTPException(404, "未找到任何解释内容")

    # 生成 Markdown 内容
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    md_content = f"""# 课件讲解: {pdf_doc.filename}

> 生成时间: {timestamp}
> 总页数: {pdf_doc.total_pages}

---

"""
    
    for explanation in explanations:
        page_num = explanation.page_number
        
        # 获取页面图像并转为 base64
        try:
            page_image = await pdf_parser.parse_single_page(pdf_doc.file_path, page_num)
            
            # 转换为 base64
            img_buffer = io.BytesIO()
            page_image.save(img_buffer, format='PNG')
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            md_content += f"""## 第 {page_num} 页

![第{page_num}页](data:image/png;base64,{img_base64})

{explanation.explanation_json}

---

"""
        except Exception as e:
            print(f"⚠️ 获取第 {page_num} 页图像失败: {str(e)}")
            md_content += f"""## 第 {page_num} 页

{explanation.explanation_json}

---

"""
    
    # 添加页脚
    md_content += f"""
## 文档说明

- 本文档由 PDF 课件自动讲解系统生成
- 每页内容包含课件截图和 AI 详细讲解
- 建议结合原始课件一起学习

---
*Generated by PPT Helper*
"""
    
    # 生成文件名
    filename = f"{Path(pdf_doc.filename).stem}_explained.md"
    
    # 返回文件流
    return StreamingResponse(
        io.BytesIO(md_content.encode('utf-8')),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


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
        "processing_status": pdf_doc.processing_status,
        "processed_pages": pdf_doc.processed_pages,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)

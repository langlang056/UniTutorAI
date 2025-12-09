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
from app.services.llm_service import llm_service, create_llm_service

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
# 从环境变量读取允许的源，如果没有则使用默认值
import os
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://localhost:3000",
    "https://localhost:3001",
    "*"  # 允许所有来源
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "PPT Helper API", "version": "0.4.0", "status": "running"}


async def process_pdf_background(
    pdf_id: str,
    file_path: str,
    page_numbers: list[int],
    llm_config: dict = None
):
    """后台任务：按顺序处理指定页面

    Args:
        pdf_id: PDF 文档 ID
        file_path: PDF 文件路径
        page_numbers: 要处理的页码列表
        llm_config: LLM 配置 {"api_key": "...", "model": "..."}
    """
    total_pages_to_process = len(page_numbers)
    print(f"🚀 开始后台处理 PDF: {pdf_id}, 处理 {total_pages_to_process} 页: {page_numbers}")

    # 创建 LLM 服务实例
    current_model_name = "unknown"  # 用于日志记录
    if llm_config and llm_config.get("api_key"):
        current_model_name = llm_config.get("model", "gemini-2.5-flash")
        current_llm = create_llm_service(
            api_key=llm_config["api_key"],
            model=current_model_name
        )
        print(f"  📡 使用客户端 API Key，模型: {current_model_name}")
    else:
        # 向后兼容：使用全局配置
        current_llm = llm_service
        current_model_name = settings.google_model
        print(f"  📡 使用服务器默认配置，模型: {current_model_name}")

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
                print(f"  🤖 正在由 {current_model_name} 模型分析第 {page_number} 页...")
                markdown_content = await current_llm.analyze_image(
                    image=page_image,
                    page_num=page_number,
                    previous_summaries=previous_summaries,
                    temperature=settings.temperature,
                    max_tokens=settings.max_tokens,
                )

                # 提取摘要
                summary = current_llm.extract_summary(markdown_content, page_number)
                
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

    # 获取 LLM 配置（可选）
    llm_config = request.get("llm_config", None)
    
    if not llm_config or not llm_config.get("api_key"):
        # 用户未提供 API Key,使用默认配置
        if not settings.default_api_key:
            raise HTTPException(500, "系统未配置默认 API Key,请联系管理员或提供您的 API Key")
        
        llm_config = {
            "api_key": settings.default_api_key,
            "model": settings.default_model,  # 固定使用 Flash 模型
        }
        print(f"🎁 使用默认 API Key (模型: {settings.default_model})")
    else:
        # 用户提供了自己的 API Key,验证配置
        if not llm_config.get("api_key"):
            raise HTTPException(400, "请提供有效的 API Key")
        model = llm_config.get("model", "gemini-2.5-flash")
        if model not in ["gemini-2.5-flash", "gemini-2.5-pro"]:
            raise HTTPException(400, f"不支持的模型: {model}")
        print(f"🔑 使用用户 API Key (模型: {model})")

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

    # 启动后台处理任务（传递 LLM 配置）
    task = asyncio.create_task(
        process_pdf_background(pdf_id, pdf_doc.file_path, page_numbers, llm_config)
    )
    processing_tasks[pdf_id] = task

    return {
        "message": f"已启动处理 {len(page_numbers)} 页",
        "page_numbers": page_numbers,
        "model": llm_config.get("model", "default") if llm_config else "server_default"
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


@app.delete("/api/cache/{pdf_id}")
async def delete_page_cache(pdf_id: str, request: dict, db: AsyncSession = Depends(get_db)):
    """
    删除指定页面的缓存，以便重新分析

    Request Body:
    {
        "page_numbers": [1, 2, 3]
    }
    """
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")

    page_numbers = request.get("page_numbers", [])
    if not page_numbers:
        raise HTTPException(400, "请提供要清除缓存的页码列表")

    # 验证页码
    invalid_pages = [p for p in page_numbers if p < 1 or p > pdf_doc.total_pages]
    if invalid_pages:
        raise HTTPException(400, f"页码无效: {invalid_pages}，有效范围: 1-{pdf_doc.total_pages}")

    # 删除缓存
    deleted_count = await cache_service.delete_page_cache(db, pdf_id, page_numbers)

    return {
        "message": f"已清除 {deleted_count} 页缓存",
        "deleted_pages": page_numbers,
        "deleted_count": deleted_count
    }


@app.post("/api/chat/{pdf_id}")
async def chat_with_ai(pdf_id: str, request: dict, db: AsyncSession = Depends(get_db)):
    """
    与 AI 进行对话（流式响应）

    Request Body:
    {
        "question": "用户的问题",
        "page_number": 1,
        "context": "当前页面的解释内容",
        "history": [{"role": "user", "content": "..."}, ...],
        "llm_config": {"api_key": "...", "model": "..."}
    }
    """
    # 验证 PDF 存在
    pdf_doc = await cache_service.get_pdf_metadata(db, pdf_id)
    if not pdf_doc:
        raise HTTPException(404, "PDF 未找到")

    # 获取请求参数
    question = request.get("question", "").strip()
    if not question:
        raise HTTPException(400, "请提供问题")

    page_number = request.get("page_number", 1)
    context = request.get("context", "")
    history = request.get("history", [])
    llm_config = request.get("llm_config", None)

    # 验证 LLM 配置
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(400, "请提供有效的 API Key")

    model = llm_config.get("model", "gemini-2.5-flash")
    if model not in ["gemini-2.5-flash", "gemini-2.5-pro"]:
        raise HTTPException(400, f"不支持的模型: {model}")

    # 创建 LLM 服务实例
    current_llm = create_llm_service(
        api_key=llm_config["api_key"],
        model=model
    )

    async def generate_stream():
        """生成 SSE 流"""
        try:
            async for chunk in current_llm.chat_stream(
                question=question,
                context=context,
                history=history,
                page_number=page_number,
            ):
                # SSE 格式
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            # 发送完成信号
            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"❌ 聊天流生成错误: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)

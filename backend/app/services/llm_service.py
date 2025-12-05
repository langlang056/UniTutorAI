"""Gemini LLM 服务"""
import google.generativeai as genai
from app.config import get_settings
from PIL import Image
from typing import List, Optional

settings = get_settings()

# 安全设置：禁用所有过滤器（学术内容）
SAFETY_SETTINGS = [
    {"category": cat, "threshold": "BLOCK_NONE"}
    for cat in [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    ]
]

# 改进的提示词模板（参考老项目）
DEFAULT_PROMPT_TEMPLATE = """请作为一名专业的教师,详细分析这一页课件的内容。

请包括以下内容:
1. **主题概述**: 这一页的主要主题是什么?
2. **核心概念**: 列出并解释页面上的关键概念、定义或术语
3. **公式和图表**: 如果有数学公式、图表或图示,请详细解释它们的含义
4. **重点难点**: 指出这一页中学生可能难以理解的部分
5. **知识点总结**: 用简洁的语言总结这一页的要点
6. **与前文联系**: 如果提供了前面页面的信息,请说明这一页如何承接或深化前面的内容

请用清晰、易懂的中文回答,就像在给学生讲解一样。使用Markdown格式输出。"""


class GeminiService:
    """Gemini Vision 服务"""

    def __init__(self):
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY 未配置")

        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.google_model)
        self.prompt_template = DEFAULT_PROMPT_TEMPLATE
        print(f"✅ Gemini 已初始化: {settings.google_model}")

    def extract_summary(self, analysis_text: str, page_num: int) -> str:
        """
        从分析结果中提取关键摘要
        
        Args:
            analysis_text: 完整的分析文本
            page_num: 页码
            
        Returns:
            摘要文本
        """
        # 提取前200个字符作为摘要
        lines = analysis_text.split('\n')
        summary_lines = []
        char_count = 0
        
        for line in lines:
            if char_count > 200:
                break
            if line.strip() and not line.startswith('#'):
                summary_lines.append(line.strip())
                char_count += len(line)
        
        summary = ' '.join(summary_lines)[:200]
        return f"[第{page_num}页摘要] {summary}"

    def build_context_string(self, previous_summaries: List[str]) -> str:
        """构建上下文字符串"""
        if not previous_summaries:
            return ""
        
        context = "\n".join(previous_summaries)
        return f"\n\n📚 前面页面的内容概要:\n{context}\n"

    async def analyze_image(
        self,
        image: Image.Image,
        page_num: int,
        previous_summaries: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 50000,
    ) -> str:
        """分析图像并生成Markdown格式解释"""
        
        # 构建提示词
        prompt = f"【第 {page_num} 页】\n\n{self.prompt_template}"
        
        # 添加前面页面的上下文
        if previous_summaries:
            context_str = self.build_context_string(previous_summaries)
            prompt += context_str

        # 生成配置 - 增加 max_output_tokens
        config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    [prompt, image],
                    generation_config=config,
                    safety_settings=SAFETY_SETTINGS,
                )

                # 检查是否有候选响应
                if not response.candidates:
                    print(f"⚠️ 第 {page_num} 页：无候选响应，重试 {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        continue
                    return f"## 第 {page_num} 页\n\n⚠️ 无法生成内容，请稍后重试。"

                candidate = response.candidates[0]

                # 记录安全标记
                if candidate.finish_reason == 2:
                    print(f"⚠️ 第 {page_num} 页：SAFETY 标记")
                elif candidate.finish_reason == 3:
                    print(f"⚠️ 第 {page_num} 页：RECITATION 标记")

                # 尝试多种方式提取文本
                extracted_text = None
                
                # 方式1: 直接从 response.text 获取
                try:
                    if hasattr(response, "text") and response.text:
                        extracted_text = response.text
                except ValueError as e:
                    # response.text 可能因为安全原因抛出异常
                    print(f"⚠️ 第 {page_num} 页：response.text 异常: {str(e)[:100]}")

                # 方式2: 从 candidate.content.parts 提取
                if not extracted_text and candidate.content and candidate.content.parts:
                    texts = []
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            texts.append(part.text)
                    if texts:
                        extracted_text = "\n".join(texts)

                # 方式3: 尝试从 candidate 的其他属性提取
                if not extracted_text:
                    try:
                        if hasattr(candidate, 'text') and candidate.text:
                            extracted_text = candidate.text
                    except:
                        pass

                if extracted_text and len(extracted_text.strip()) > 50:
                    return extracted_text
                elif extracted_text:
                    print(f"⚠️ 第 {page_num} 页：内容过短 ({len(extracted_text)} 字符)，重试")
                    if attempt < max_retries - 1:
                        continue
                    return extracted_text if extracted_text else f"## 第 {page_num} 页\n\n⚠️ 内容生成不完整。"
                else:
                    print(f"⚠️ 第 {page_num} 页：无法提取内容，重试 {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        continue
                    return f"## 第 {page_num} 页\n\n⚠️ 无法提取内容，可能是安全过滤导致。"

            except Exception as e:
                print(f"⚠️ 第 {page_num} 页：Gemini API 错误: {str(e)}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2)  # 等待2秒后重试
                    continue
                return f"## 第 {page_num} 页\n\n⚠️ 生成失败: {str(e)[:200]}"
        
        return f"## 第 {page_num} 页\n\n⚠️ 多次尝试后仍无法生成内容。"


# 全局单例
llm_service = GeminiService()

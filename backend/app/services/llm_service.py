"""Gemini LLM 服务"""
import google.generativeai as genai
from app.config import get_settings
from PIL import Image
from typing import List, Optional, AsyncGenerator
from dataclasses import dataclass
import asyncio

settings = get_settings()

# 支持的模型列表
SUPPORTED_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

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

**重要格式要求**:
- 使用 Markdown 格式输出
- 所有数学公式必须使用 LaTeX 语法:
  - 行内公式使用单个美元符号包裹,如 $E = mc^2$
  - 块级公式(独立成行的公式)必须使用双美元符号包裹,如:
    $$F(x) = \\int_{-\\infty}^{\\infty} f(t) dt$$
  - 多行公式也必须用双美元符号包裹,如:
    $$
    \\begin{aligned}
    a &= b + c \\\\
    d &= e + f
    \\end{aligned}
    $$
- 绝对不要直接写 \\begin{align*} 或 \\begin{equation} 而不用 $$ 包裹
- 不要使用 Unicode 数学符号(如 Σ、∫、√),必须使用 LaTeX 命令(如 \\sum、\\int、\\sqrt)
- 上下标必须用 LaTeX 语法,如 $x_i$、$x^2$,而不是 xᵢ、x²

请用清晰、易懂的中文回答,就像在给学生讲解一样。"""


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str
    model: str = "gemini-2.5-flash"


class GeminiService:
    """Gemini Vision 服务 - 支持动态配置"""

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 Gemini 服务

        Args:
            config: LLM 配置，如果为 None 则使用环境变量配置（向后兼容）
        """
        self.prompt_template = DEFAULT_PROMPT_TEMPLATE
        self._model = None
        self._api_key = None
        self._model_name = None

        if config:
            self._init_with_config(config)
        elif settings.google_api_key:
            # 向后兼容：使用环境变量配置
            self._init_with_config(LLMConfig(
                api_key=settings.google_api_key,
                model=settings.google_model
            ))
            print(f"✅ Gemini 使用环境变量配置: {settings.google_model}")
        else:
            print("⚠️ Gemini 未配置，等待客户端提供 API Key")

    def _init_with_config(self, config: LLMConfig):
        """使用配置初始化"""
        if not config.api_key:
            raise ValueError("API Key 未提供")

        # 验证模型
        if config.model not in SUPPORTED_MODELS:
            raise ValueError(f"不支持的模型: {config.model}，支持: {SUPPORTED_MODELS}")

        genai.configure(api_key=config.api_key)
        self._model = genai.GenerativeModel(config.model)
        self._api_key = config.api_key
        self._model_name = config.model

    def configure(self, config: LLMConfig):
        """动态更新配置"""
        self._init_with_config(config)
        print(f"✅ Gemini 配置已更新: {config.model}")

    @property
    def model(self):
        if self._model is None:
            raise ValueError("Gemini 未配置，请先提供 API Key")
        return self._model

    @property
    def is_configured(self) -> bool:
        return self._model is not None

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


    async def chat_stream(
        self,
        question: str,
        context: str,
        history: List[dict],
        page_number: int,
        temperature: float = 0.7,
        max_tokens: int = 50000,
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天响应

        Args:
            question: 用户问题
            context: 当前页面的解释内容（作为上下文）
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            page_number: 当前页码
            temperature: 温度参数
            max_tokens: 最大 token 数

        Yields:
            流式响应的文本片段
        """
        # 构建系统提示
        system_prompt = f"""你是一个专业的课件讲解助手。用户正在阅读第 {page_number} 页的课件内容，下面是该页的详细讲解：

---
{context if context else "（该页暂无讲解内容）"}
---

请基于以上内容回答用户的问题。如果问题与当前页面内容相关，请结合上下文给出详细解答。
如果问题超出当前页面范围，可以根据你的知识进行补充，但请说明这是额外补充的内容。

**重要格式要求**:
- 使用 Markdown 格式回答
- **数学符号使用 Unicode 字符，不要使用 LaTeX 语法（不要用 $ 符号）**
- 常用数学符号示例：
  * 希腊字母：α β γ δ ε θ λ μ π σ ω Σ Ω
  * 运算符：× ÷ ± ≈ ≠ ≤ ≥ ∝ ∞
  * 上下标：x₁ x₂ x³ x² xⁿ
  * 分数：用 / 表示，如 1/2, a/b
  * 积分求和：∫ ∑ ∏
  * 逻辑符号：∈ ∉ ⊂ ⊆ ∪ ∩ ∧ ∨ ¬
- 例如写 "p(a|t) ∝ p(t|a) × p(t)" 而不是 "$p(a|t) \\propto p(t|a) \\times p(t)$"
- 用反引号包裹重要的数学表达式和变量名，如 `r(x)`, `θ₁`, `P(6|θ₂)`
- 请用清晰、易懂的中文回答"""

        # 构建消息历史
        messages = []

        # 添加历史消息
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            messages.append({"role": role, "parts": [msg["content"]]})

        # 添加当前问题
        messages.append({"role": "user", "parts": [question]})

        # 生成配置
        config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            # 使用 chat 模式
            chat = self.model.start_chat(history=messages[:-1] if messages[:-1] else [])

            # 流式生成
            response = chat.send_message(
                f"{system_prompt}\n\n用户问题：{question}",
                generation_config=config,
                safety_settings=SAFETY_SETTINGS,
                stream=True,
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    await asyncio.sleep(0)  # 让出控制权

        except Exception as e:
            print(f"❌ 聊天流式响应错误: {str(e)}")
            yield f"\n\n抱歉，发生错误：{str(e)}"


# 全局单例（可选，向后兼容）
# 如果环境变量配置了 API Key，则创建默认实例
# 否则创建未配置的实例，等待客户端提供配置
llm_service = GeminiService()


def create_llm_service(api_key: str, model: str = "gemini-2.5-flash") -> GeminiService:
    """
    创建新的 LLM 服务实例（使用客户端配置）

    Args:
        api_key: Google API Key
        model: 模型名称

    Returns:
        配置好的 GeminiService 实例
    """
    config = LLMConfig(api_key=api_key, model=model)
    return GeminiService(config)

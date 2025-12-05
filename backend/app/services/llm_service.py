"""Gemini LLM 服务"""
import google.generativeai as genai
from app.config import get_settings
from PIL import Image

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


class GeminiService:
    """Gemini Vision 服务"""

    def __init__(self):
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY 未配置")

        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.google_model)
        print(f"✅ Gemini 已初始化: {settings.google_model}")

    async def analyze_image(
        self,
        image: Image.Image,
        prompt: str,
        system_message: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """分析图像并生成解释"""
        # 合并 system message 和 prompt
        full_prompt = f"{system_message}\n\n{prompt}" if system_message else prompt

        # 生成配置
        config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            response = self.model.generate_content(
                [full_prompt, image],
                generation_config=config,
                safety_settings=SAFETY_SETTINGS,
            )

            # 强制提取内容（忽略安全过滤）
            if not response.candidates:
                print("⚠️ 无候选响应")
                return "无法生成解释"

            candidate = response.candidates[0]

            # 记录但忽略安全标记
            if candidate.finish_reason == 2:
                print(f"⚠️ SAFETY 标记（已忽略）")
            elif candidate.finish_reason == 3:
                print(f"⚠️ RECITATION 标记（已忽略）")

            # 提取文本
            try:
                if hasattr(response, "text") and response.text:
                    return response.text
            except:
                pass

            # 从 candidate 提取
            if candidate.content and candidate.content.parts:
                texts = [p.text for p in candidate.content.parts if hasattr(p, "text") and p.text]
                if texts:
                    return "\n".join(texts)

            return "无法提取内容"

        except Exception as e:
            print(f"⚠️ Gemini API 错误: {str(e)}")
            return f"生成失败: {str(e)[:200]}"


# 全局单例
llm_service = GeminiService()

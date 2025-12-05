"""LLM服务 - 使用 Google Gemini (与老项目相同的逻辑)"""
import google.generativeai as genai
from app.config import get_settings

settings = get_settings()


class GeminiService:
    """Google Gemini LLM服务 - 参考老项目的 GeminiHandler"""

    def __init__(self):
        """初始化 Gemini,使用 GOOGLE_API_KEY"""
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY 未配置,请在 .env 文件中设置")

        # 配置 Gemini API (与老项目逻辑相同)
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.google_model)
        print(f"✅ Gemini 已初始化: {settings.google_model}")

    async def generate_text(
        self,
        prompt: str,
        system_message: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        使用 Gemini 生成文本 (与老项目 analyze_image 逻辑相同,但用于文本)

        Args:
            prompt: 用户提示词
            system_message: 系统消息(将合并到提示词中)
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            生成的文本
        """
        # Gemini 不支持单独的 system message,合并到 prompt (与老项目相同)
        full_prompt = prompt
        if system_message:
            full_prompt = f"{system_message}\n\n{prompt}"

        # 配置生成参数
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # 生成响应 (与老项目相同的调用方式)
        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )

            # 检查响应是否被阻止
            if not response.candidates:
                return "此页面内容无法生成解释(可能包含敏感内容或格式问题)"

            # 检查 finish_reason
            candidate = response.candidates[0]
            if candidate.finish_reason == 2:  # SAFETY
                return "此页面内容因安全原因无法生成解释"
            elif candidate.finish_reason == 3:  # RECITATION
                return "此页面内容因版权原因无法生成解释"

            # 尝试获取文本
            try:
                return response.text
            except:
                # 如果 response.text 失败,尝试直接访问内容
                if candidate.content and candidate.content.parts:
                    return candidate.content.parts[0].text
                return "无法提取此页面的解释内容"

        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Gemini API 错误: {error_msg}")
            return f"生成解释时出错: {error_msg[:200]}"

    def get_provider_info(self) -> dict:
        """获取提供商信息"""
        return {
            "provider": "gemini",
            "model": settings.google_model,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }


# 全局单例
llm_service = GeminiService()

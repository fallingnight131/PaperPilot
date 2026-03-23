from .base_tool import BaseTool
from ..services.doubao_client import DoubaoClient


class TranslateTool(BaseTool):
    """翻译工具 —— 将文本翻译为指定语言，支持中英互译及多语言翻译"""

    name = "translate"
    description = "将文本翻译为指定语言，支持中英互译及多语言翻译"

    def run(self, input_data: dict) -> dict:
        """
        input_data: {text, target_language, source_language(可选)}
        返回: {translated_text, source_language, target_language}
        """
        text = input_data.get("text", "")
        target_language = input_data.get("target_language", "中文")
        source_language = input_data.get("source_language", "")

        if not text.strip():
            return {
                "translated_text": "",
                "source_language": source_language,
                "target_language": target_language,
            }

        source_hint = f"（原文语言：{source_language}）" if source_language else ""
        prompt = f"""请将以下文本翻译为{target_language}{source_hint}。

要求：
- 翻译要准确、流畅、自然
- 专业术语保留原文并在括号中给出翻译
- 保持原文的段落格式
- 仅输出翻译结果，不要添加任何解释

原文：
{text}
"""
        try:
            client = DoubaoClient()
            translated = client.generate(prompt, temperature=0.2)
            return {
                "translated_text": translated.strip(),
                "source_language": source_language or "auto",
                "target_language": target_language,
            }
        except Exception as e:
            return {
                "translated_text": f"翻译失败: {str(e)}",
                "source_language": source_language,
                "target_language": target_language,
            }

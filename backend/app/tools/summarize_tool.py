from .base_tool import BaseTool
from ..services.doubao_client import DoubaoClient
from ..extensions import db
from ..models.document import Document
from ..models.chunk import DocumentChunk


class SummarizeTool(BaseTool):
    """摘要解读工具 —— 对单篇文献生成结构化解读"""

    name = "summarize"
    description = "对单篇文献生成结构化解读，包含研究问题、方法、结论等"

    def run(self, input_data: dict) -> dict:
        """
        input_data: {document_id} 或 {text}
        返回: {summary: {background, methods, findings, innovation, limitations}}
        """
        text = input_data.get("text", "")
        document_id = input_data.get("document_id")

        # 如果提供了 document_id，从数据库读取分块内容
        if document_id and not text:
            try:
                chunks = DocumentChunk.query.filter_by(document_id=document_id) \
                    .order_by(DocumentChunk.chunk_index).all()
                if chunks:
                    text = "\n\n".join([c.content for c in chunks[:30]])  # 取前30个分块
                else:
                    return {"summary": None, "error": "该文献尚未完成解析，无分块数据"}
            except Exception as e:
                return {"summary": None, "error": f"读取文献数据失败: {str(e)}"}

        if not text.strip():
            return {"summary": None, "error": "未提供文本内容"}

        # 截断过长文本
        text = text[:15000]

        prompt = f"""请对以下学术文献内容进行结构化解读。要求以 JSON 格式输出，包含以下字段：

1. background: 研究背景与问题（2-3句话概括）
2. methods: 研究方法（列出主要方法和技术手段）
3. findings: 主要发现与结论（3-5个要点）
4. innovation: 创新点（1-3个）
5. limitations: 局限性（如果文中有提及）

请使用中文回答，专业术语保留英文。仅输出 JSON 内容，不要添加其他说明。

文献内容：
{text}
"""
        try:
            client = DoubaoClient()
            result = client.generate(prompt, temperature=0.3)

            # 尝试解析 JSON
            import json
            import re
            # 去掉可能的 markdown 代码块标记
            clean = re.sub(r"```(?:json)?\s*", "", result).strip()
            clean = re.sub(r"```\s*$", "", clean).strip()

            try:
                summary = json.loads(clean)
            except json.JSONDecodeError:
                # 如果 JSON 解析失败，返回原始文本
                summary = {
                    "background": result,
                    "methods": "",
                    "findings": "",
                    "innovation": "",
                    "limitations": "",
                }

            return {"summary": summary}
        except Exception as e:
            return {"summary": None, "error": f"生成摘要失败: {str(e)}"}

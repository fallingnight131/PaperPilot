import re
from typing import List, Optional, Dict

from ..services.doubao_client import DoubaoClient
from ..services.vector_store import VectorStoreService
from ..models.conversation import Conversation, Message
from ..models.document import Document
from ..extensions import db


class RAGService:
    """RAG 检索与问答生成核心服务"""

    def __init__(self):
        self.llm_client = DoubaoClient()
        self.vector_store = VectorStoreService()

    def answer_question(
        self,
        question: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        doc_ids: Optional[List[int]] = None,
    ) -> dict:
        """
        RAG 问答核心流程：
        1. 获取问题向量
        2. 向量检索 Top-5 相关分块
        3. 构建 RAG Prompt
        4. 调用 Gemini 生成答案
        5. 解析引用编号
        6. 保存消息并返回结果
        """
        # 1. 获取问题向量
        query_embedding = self.llm_client.get_query_embedding(question)

        # 2. 向量检索
        retrieved_chunks = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=5,
            filter_doc_ids=doc_ids,
        )

        # 如果没有检索到内容，仍然尝试回答
        if not retrieved_chunks:
            answer = "抱歉，在已上传的文献中未找到与您问题相关的内容。请尝试上传更多相关文献，或调整您的问题表述。"
            sources = []
        else:
            # 3. 构建 RAG Prompt
            rag_prompt = self.build_rag_prompt(question, retrieved_chunks)

            # 4. 调用豆包生成答案
            system_prompt = "你是一位电化学储能材料领域的专业研究助理，擅长基于文献内容回答科研问题。"
            answer = self.llm_client.generate(rag_prompt, system_prompt=system_prompt)

            # 5. 解析引用编号
            sources = self.parse_citations(answer, retrieved_chunks)

        # 6. 保存会话和消息
        if conversation_id is None:
            # 创建新会话
            title = question[:50] + ("..." if len(question) > 50 else "")
            conversation = Conversation(user_id=user_id, title=title)
            db.session.add(conversation)
            db.session.flush()
            conversation_id = conversation.id

        # 保存用户消息
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        db.session.add(user_msg)

        # 保存 AI 回复消息
        ai_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
        )
        ai_msg.sources = [
            {
                "doc_title": s.get("title", ""),
                "doc_id": s.get("document_id", 0),
                "chunk_index": s.get("chunk_index", 0),
                "page_number": s.get("page_number", 0),
                "content_preview": s.get("content", "")[:200],
                "score": s.get("score", 0),
            }
            for s in sources
        ]
        db.session.add(ai_msg)

        # 更新会话的 updated_at
        conv = Conversation.query.get(conversation_id)
        if conv:
            from datetime import datetime
            conv.updated_at = datetime.utcnow()

        db.session.commit()

        return {
            "answer": answer,
            "conversation_id": conversation_id,
            "sources": ai_msg.sources,
        }

    def build_rag_prompt(self, question: str, retrieved_chunks: List[dict]) -> str:
        """构建 RAG Prompt"""
        chunks_text = ""
        for i, chunk in enumerate(retrieved_chunks, 1):
            title = chunk.get("title", "未知文献")
            page = chunk.get("page_number", "?")
            content = chunk.get("content", "")
            score = chunk.get("score", 0)
            chunks_text += f"\n[{i}] 来源：{title}（第{page}页，相似度：{score}）\n{content}\n"

        prompt = f"""你是一位电化学储能材料领域的专业研究助理。请根据以下检索到的文献片段回答用户问题。

## 检索到的文献片段
{chunks_text}

## 用户问题
{question}

## 回答要求
- 基于上述文献内容进行回答，不要凭空捏造
- 在答案中使用 [数字] 标注引用来源，如"锂离子电池的SEI膜主要由...组成[1][3]"
- 如果检索到的文献不足以回答问题，请明确指出
- 使用中文回答，专业术语保留英文
- 回答要准确、简洁、有条理
"""
        return prompt

    def parse_citations(self, answer: str, chunks: List[dict]) -> List[dict]:
        """
        解析答案中的 [1][2] 等引用标记，
        将编号映射到对应的检索片段，构建 sources 列表。
        """
        cited_indices = set()
        for m in re.findall(r"\[(\d+)\]", answer):
            idx = int(m) - 1  # 转为 0-based
            if 0 <= idx < len(chunks):
                cited_indices.add(idx)

        # 如果没有找到引用，返回所有检索结果
        if not cited_indices:
            return chunks

        return [chunks[i] for i in sorted(cited_indices)]

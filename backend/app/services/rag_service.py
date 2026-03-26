import re
from typing import List, Optional, Dict

from ..services.doubao_client import DoubaoClient
from ..services.vector_store import VectorStoreService
from ..models.conversation import Conversation, Message
from ..models.document import Document
from ..extensions import db

# ---- 系统提示词 ----

SYSTEM_PROMPT_RAG = """你是 PaperPilot 文献库问答助手。
你的唯一职责是根据用户上传的文献库内容回答问题。
你没有独立的知识储备——你的所有回答必须严格来自用户提供的文献片段。
如果文献库中没有相关信息，你必须明确告知用户，而不是用自己的训练知识补充。"""

SYSTEM_PROMPT_CASUAL = """你是 PaperPilot 智能文献助手，一位电化学储能材料领域的专业研究助理。
你的性格温和、专业且乐于助人。你正在一个文献问答平台上与科研人员交流。

你的核心能力：
1. 基于用户上传的 PDF 文献进行智能问答（RAG 检索增强生成）
2. 中英文论文翻译
3. 文献摘要与结构化解读

请注意：
- 用亲切友好的语气回复用户
- 如果用户打招呼或闲聊，热情回应并简要介绍你能做什么
- 引导用户提出与文献相关的具体问题，但不要生硬地拒绝
- 如果用户问了一个专业问题但还没上传文献，温馨提醒他先上传
- 回答要简洁自然，不要像机器人一样列清单"""


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
        # 0. 先判断问题类型
        is_casual = self._is_casual_query(question)
        is_library_query = self._is_library_query(question)

        if is_casual:
            answer = self._generate_casual_reply(question)
            sources = []
            retrieved_chunks = []
        elif is_library_query:
            # 文献库查询：直接查数据库，避免 LLM 编造文献
            answer, sources = self._answer_library_query(question, user_id, doc_ids)
            retrieved_chunks = []
        else:
            # 1. 获取问题向量
            query_embedding = self.llm_client.get_query_embedding(question)

            # 2. 向量检索
            retrieved_chunks = self.vector_store.search(
                query_embedding=query_embedding,
                n_results=5,
                filter_doc_ids=doc_ids,
            )

            if not retrieved_chunks:
                # 专业问题但没有检索到文献 → 友好提示并给出建议
                answer = self._generate_no_docs_reply(question)
                sources = []
            else:
                # 3. 过滤低相关度片段
                MIN_SCORE_THRESHOLD = 0.4
                relevant_chunks = [c for c in retrieved_chunks if c.get("score", 0) >= MIN_SCORE_THRESHOLD]

                if not relevant_chunks:
                    answer = self._generate_no_docs_reply(question)
                    sources = []
                else:
                    # 4. 构建 RAG Prompt
                    rag_prompt = self.build_rag_prompt(question, relevant_chunks)

                    # 5. 调用豆包生成答案（temperature 调低以减少创造性发挥）
                    answer = self.llm_client.generate(rag_prompt, system_prompt=SYSTEM_PROMPT_RAG, temperature=0.1)

                    # 6. 解析引用编号
                    sources = self.parse_citations(answer, relevant_chunks)

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

    def _is_library_query(self, question: str) -> bool:
        """判断是否为「查询文献库」类问题（询问库里有没有某方向/某类文献）"""
        q = question.strip()
        library_patterns = [
            r'(有没有|有无|是否有|有哪些|列出|查找|找找|搜索|搜一下).{0,20}(文献|论文|paper|文章)',
            r'(文献|论文|paper|文章).{0,10}(有没有|有无|是否有|有哪些|列出)',
            r'(库里|知识库|文献库|上传).{0,15}(有|包含|收录)',
            r'(哪些|什么).{0,10}(方向|领域|主题|关于).{0,10}(文献|论文)',
        ]
        for pattern in library_patterns:
            if re.search(pattern, q):
                return True
        return False

    def _answer_library_query(self, question: str, user_id: int,
                              doc_ids: Optional[List[int]] = None):
        """
        文献库查询：从数据库中取出用户真实上传的文献列表，
        交给 LLM 做自然语言过滤/匹配，确保只返回真实存在的文献。
        返回 (answer_text, sources_list)
        """
        query = Document.query.filter_by(user_id=user_id, status="ready")
        if doc_ids:
            query = query.filter(Document.id.in_(doc_ids))
        documents = query.order_by(Document.upload_time.desc()).all()

        if not documents:
            return "您的文献库目前还没有上传任何文献。请前往「文献管理」页面上传 PDF 文件。", []

        # 构建真实文献列表（只含数据库中真实存在的文献）
        doc_list_text = ""
        for i, doc in enumerate(documents, 1):
            authors = doc.authors or "作者未知"
            abstract_preview = (doc.abstract or "")[:100]
            doc_list_text += f"[{i}] 标题：{doc.title}\n    作者：{authors}\n    摘要摘录：{abstract_preview}\n\n"

        prompt = f"""以下是用户文献库中真实存在的所有文献（共 {len(documents)} 篇）：

{doc_list_text}

用户问题：{question}

请根据上方文献列表回答用户，用自然语言组织回答。要求：
1. 开头先直接回答有无相关文献，例如"有，以下是xxx方向的文献："或"当前文献库中暂无该方向的文献"
2. 如果有相关文献，逐条列出，每条格式为：[序号] 文献标题（作者）
3. 只能从上方列表中选取，绝对不能提及列表之外的任何文献
4. 不要补充任何列表外的文献信息
"""
        answer = self.llm_client.generate(
            prompt,
            system_prompt="你是文献库查询助手，只能返回用户提供的真实文献列表中的内容，不得添加任何额外信息。",
            temperature=0.1,
        )

        # 确保每个 [N] 条目前有换行，避免 LLM 输出粘连
        answer = re.sub(r'\n*(\[\d+\])', r'\n\n\1', answer)

        # 解析答案中引用的 [N] 编号，提取对应文献作为来源
        cited_indices = set()
        for m in re.findall(r"\[(\d+)\]", answer):
            idx = int(m) - 1
            if 0 <= idx < len(documents):
                cited_indices.add(idx)

        sources = [
            {
                "document_id": documents[i].id,
                "title": documents[i].title,
                "authors": documents[i].authors or "",
                "chunk_index": 0,
                "page_number": 0,
                "content": documents[i].abstract or "",
                "score": 1.0,
            }
            for i in sorted(cited_indices)
        ]

        return answer, sources

    def _is_casual_query(self, question: str) -> bool:
        """判断是否为闲聊/问候/通用问题（非需要文献检索的专业问题）"""
        q = question.strip().lower()
        # 短问候
        casual_patterns = [
            r'^(你好|您好|hi|hello|hey|嗨|哈喽|在吗|在不在)',
            r'^(谢谢|感谢|thanks|thank you|thx)',
            r'^(再见|拜拜|bye|see you|晚安|早安|早上好|下午好|晚上好)',
            r'^(你是谁|你叫什么|你能做什么|你会什么|介绍一下你自己|help|帮助)',
            r'^(测试|test|ping)',
            r'^(好的|ok|嗯|哦|明白了|知道了|收到)',
        ]
        for pattern in casual_patterns:
            if re.search(pattern, q):
                return True
        # 过短且无专业关键词
        if len(q) <= 4 and not any(kw in q for kw in ['电池', '锂', '电极', '电解', '材料', '储能', 'battery', 'lithium', 'electrode']):
            return True
        return False

    def _generate_casual_reply(self, question: str) -> str:
        """对闲聊/问候类问题生成友好回复"""
        prompt = f"""用户说："{question}"

请友好地回应用户，并自然地引导他使用平台的功能。你可以：
- 如果是问候，热情回应并简要介绍自己能做什么
- 如果用户问你是谁/能做什么，介绍你的核心能力
- 如果是感谢，谦虚回应并询问是否还有其他需要帮助的
- 保持简短自然（2-4句话），不要长篇大论"""
        return self.llm_client.generate(prompt, system_prompt=SYSTEM_PROMPT_CASUAL)

    def _generate_no_docs_reply(self, question: str) -> str:
        """当没有检索到文献时，生成友好的引导回复"""
        prompt = f"""用户问了一个问题："{question}"

但目前文献库中没有与该问题相关的内容。请你：
1. 先肯定用户的问题是个好问题
2. 温馨提醒用户可能还没有上传相关文献，建议去「文献管理」页面上传 PDF
3. 如果能简要判断这个问题属于什么方向，可以建议上传哪类文献
4. 保持简短友好（3-5句话）"""
        return self.llm_client.generate(prompt, system_prompt=SYSTEM_PROMPT_CASUAL)

    def build_rag_prompt(self, question: str, retrieved_chunks: List[dict]) -> str:
        """构建 RAG Prompt"""
        chunks_text = ""
        for i, chunk in enumerate(retrieved_chunks, 1):
            title = chunk.get("title", "未知文献")
            page = chunk.get("page_number", "?")
            content = chunk.get("content", "")
            score = chunk.get("score", 0)
            chunks_text += f"\n[{i}] 来源：{title}（第{page}页，相似度：{score}）\n{content}\n"

        prompt = f"""你是一个严格基于文献库的问答系统。你只能使用下面提供的文献片段回答问题，不得使用任何其他来源的知识。

## 文献库片段（这是你唯一可以使用的信息来源）
{chunks_text}

## 用户问题
{question}

## 严格规则（必须遵守）
1. 只能引用上方文献片段中明确出现的内容，禁止使用你自身训练数据中的知识
2. 禁止提及任何未在上述片段中出现的文献、作者、研究结论或数据
3. 若上方片段不足以完整回答问题，必须明确说明："根据当前文献库，没有找到关于...的相关内容，建议上传相关文献"
4. 引用时使用 [数字] 标注来源编号，如"...组成[1][3]"
5. 不得推断、补充或扩展片段未提到的内容
6. 使用中文回答，专业术语保留英文
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

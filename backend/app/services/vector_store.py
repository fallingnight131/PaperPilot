import os
from typing import List, Dict, Optional

import chromadb
from ..config import Config


class VectorStoreService:
    """ChromaDB 向量存储操作服务"""

    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        chroma_path = Config.CHROMA_DB_PATH
        os.makedirs(chroma_path, exist_ok=True)

        self._client = chromadb.PersistentClient(path=chroma_path)
        self._collection = self._client.get_or_create_collection(
            name="literature_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        print(f"[VectorStore] ChromaDB 已初始化, 路径: {chroma_path}")

    def add_chunks(
        self, document_id: int, chunks: List[dict], embeddings: List[List[float]]
    ) -> List[str]:
        """
        将分块内容和向量批量写入 ChromaDB。
        metadata 包含：document_id, chunk_index, page_number, title, authors
        返回 chroma_id 列表。
        """
        ids = []
        documents = []
        metadatas = []
        embedding_list = []

        for i, chunk in enumerate(chunks):
            chroma_id = f"doc_{document_id}_chunk_{chunk['chunk_index']}"
            ids.append(chroma_id)
            documents.append(chunk["content"])
            metadatas.append({
                "document_id": str(document_id),
                "chunk_index": chunk["chunk_index"],
                "page_number": chunk.get("page_number", 0),
                "title": chunk.get("title", ""),
                "authors": chunk.get("authors", ""),
            })
            embedding_list.append(embeddings[i])

        if ids:
            # 分批写入，每批 100 条
            batch_size = 100
            for start in range(0, len(ids), batch_size):
                end = start + batch_size
                self._collection.add(
                    ids=ids[start:end],
                    documents=documents[start:end],
                    metadatas=metadatas[start:end],
                    embeddings=embedding_list[start:end],
                )

        return ids

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        filter_doc_ids: Optional[List[int]] = None,
    ) -> List[dict]:
        """
        基于余弦相似度检索最相关的分块。
        支持按 document_id 列表过滤。
        返回：content, score, document_id, chunk_index, page_number, title
        """
        where_filter = None
        if filter_doc_ids:
            str_ids = [str(did) for did in filter_doc_ids]
            if len(str_ids) == 1:
                where_filter = {"document_id": str_ids[0]}
            else:
                where_filter = {"document_id": {"$in": str_ids}}

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            print(f"[VectorStore] 检索错误: {e}")
            return []

        search_results = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0
                # ChromaDB 余弦距离越小越相似，转换为相似度分数
                score = 1 - distance

                search_results.append({
                    "chroma_id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "score": round(score, 4),
                    "document_id": int(meta.get("document_id", 0)),
                    "chunk_index": meta.get("chunk_index", 0),
                    "page_number": meta.get("page_number", 0),
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", ""),
                })

        return search_results

    def delete_document(self, document_id: int):
        """删除指定文献的所有向量"""
        try:
            self._collection.delete(
                where={"document_id": str(document_id)}
            )
            print(f"[VectorStore] 已删除文献 {document_id} 的所有向量")
        except Exception as e:
            print(f"[VectorStore] 删除文献向量错误: {e}")

    def get_chunks_with_embeddings(self, document_ids: List[int]) -> dict:
        """
        获取指定文献的所有 chunk 内容、元数据和向量，用于知识库可视化。
        返回 ChromaDB get() 的原始结果：ids, embeddings, documents, metadatas
        """
        if not document_ids:
            return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
        str_ids = [str(did) for did in document_ids]
        where_filter = (
            {"document_id": str_ids[0]}
            if len(str_ids) == 1
            else {"document_id": {"$in": str_ids}}
        )
        try:
            return self._collection.get(
                where=where_filter,
                include=["embeddings", "documents", "metadatas"],
            )
        except Exception as e:
            print(f"[VectorStore] 获取 embeddings 失败: {e}")
            return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}

    def get_collection_count(self) -> int:
        """获取集合中的总文档数"""
        return self._collection.count()

import os

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..models.document import Document
from ..services.vector_store import VectorStoreService

knowledge_bp = Blueprint("knowledge", __name__)


def success_response(data=None, message="success"):
    return jsonify({"code": 0, "data": data or {}, "message": message})


def error_response(message="error", code=1, status_code=400):
    return jsonify({"code": code, "message": message}), status_code


@knowledge_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    """返回当前用户的知识库统计信息"""
    user_id = int(get_jwt_identity())
    docs = Document.query.filter_by(user_id=user_id, status="ready").all()
    total_chunks = sum(d.chunk_count or 0 for d in docs)
    return success_response({
        "doc_count": len(docs),
        "chunk_count": total_chunks,
    })


@knowledge_bp.route("/map-data", methods=["GET"])
@jwt_required()
def get_map_data():
    """
    从 ChromaDB 取出用户所有文献的向量，用 UMAP 降到 2D，
    返回散点坐标 + 元数据供前端直接渲染。
    """
    user_id = int(get_jwt_identity())
    docs = Document.query.filter_by(user_id=user_id, status="ready").all()
    if not docs:
        return error_response("暂无已就绪的文献，请先上传并等待处理完成", status_code=400)

    doc_ids = [d.id for d in docs]
    doc_map = {d.id: d for d in docs}

    vector_store = VectorStoreService()
    result = vector_store.get_chunks_with_embeddings(doc_ids)

    embeddings = result.get("embeddings") or []
    metadatas = result.get("metadatas") or []
    documents = result.get("documents") or []

    if not embeddings:
        return error_response("未找到任何向量数据，请确认文献已完成处理", status_code=400)

    import numpy as np

    X = np.array(embeddings, dtype=np.float32)
    n_samples = X.shape[0]

    # UMAP 降维到 2D（样本数较少时退回 PCA）
    try:
        if n_samples >= 10:
            from umap import UMAP
            n_neighbors = min(15, n_samples - 1)
            reducer = UMAP(n_components=2, n_neighbors=n_neighbors,
                           min_dist=0.1, random_state=42, verbose=False)
            coords = reducer.fit_transform(X)
        else:
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2)
            coords = pca.fit_transform(X)
    except Exception as e:
        print(f"[Knowledge] 降维失败: {e}")
        return error_response(f"降维计算失败: {str(e)}", status_code=500)

    # 为每篇文献分配颜色索引
    unique_doc_ids = list(dict.fromkeys(
        int(m.get("document_id", 0)) for m in metadatas
    ))
    doc_color_idx = {did: i for i, did in enumerate(unique_doc_ids)}

    points = []
    for i, meta in enumerate(metadatas):
        doc_id = int(meta.get("document_id", 0))
        doc = doc_map.get(doc_id)
        points.append({
            "x": float(coords[i, 0]),
            "y": float(coords[i, 1]),
            "doc_id": doc_id,
            "color_idx": doc_color_idx.get(doc_id, 0),
            "title": meta.get("title") or (doc.title if doc else "未知文献"),
            "authors": meta.get("authors", ""),
            "page": int(meta.get("page_number", 0)),
            "chunk_index": int(meta.get("chunk_index", 0)),
            "preview": (documents[i] or "")[:150],
        })

    return success_response({
        "points": points,
        "doc_count": len(docs),
        "chunk_count": n_samples,
        "doc_names": {str(did): (doc_map[did].title if did in doc_map else str(did))
                      for did in unique_doc_ids},
    })

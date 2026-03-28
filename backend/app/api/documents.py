import os
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models.document import Document
from ..models.chunk import DocumentChunk
from ..services.pdf_parser import PDFParser
from ..services.doubao_client import DoubaoClient
from ..services.vector_store import VectorStoreService

documents_bp = Blueprint("documents", __name__)


def success_response(data=None, message="success"):
    return jsonify({"code": 0, "data": data or {}, "message": message})


def error_response(message="error", code=1, status_code=400):
    return jsonify({"code": code, "message": message}), status_code


ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def process_document_async(app, document_id):
    """异步处理文献：解析 PDF、生成 embedding、写入向量库"""
    with app.app_context():
        doc = Document.query.get(document_id)
        if not doc:
            return

        try:
            # 1. 更新状态为 processing
            doc.status = "processing"
            db.session.commit()

            # 2. 解析 PDF
            parser = PDFParser()
            metadata = parser.extract_metadata(doc.file_path)

            # 更新元数据
            if metadata.get("title") and not doc.title:
                doc.title = metadata["title"]
            if metadata.get("authors") and not doc.authors:
                doc.authors = metadata["authors"]
            if metadata.get("abstract"):
                doc.abstract = metadata["abstract"]
            if metadata.get("language"):
                doc.language = metadata["language"]
            db.session.commit()

            # 3. 分块
            chunks = parser.parse_and_chunk(doc.file_path)
            if not chunks:
                doc.status = "failed"
                doc.error_message = "PDF 未提取到有效文本"
                db.session.commit()
                return

            # 为每个 chunk 添加文献标题和作者信息
            for chunk in chunks:
                chunk["title"] = doc.title
                chunk["authors"] = doc.authors

            # 4. 批量获取 embedding
            llm_client = DoubaoClient()
            texts = [c["content"] for c in chunks]
            embeddings = llm_client.batch_embed(texts, batch_size=20)

            # 5. 写入 ChromaDB
            vector_store = VectorStoreService()
            chroma_ids = vector_store.add_chunks(document_id, chunks, embeddings)

            # 6. 写入 DocumentChunk 记录
            for i, chunk in enumerate(chunks):
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    page_number=chunk.get("page_number", 0),
                    char_start=chunk.get("char_start", 0),
                    char_end=chunk.get("char_end", 0),
                    chroma_id=chroma_ids[i] if i < len(chroma_ids) else "",
                )
                db.session.add(db_chunk)

            # 7. 更新文献状态
            doc.status = "ready"
            doc.chunk_count = len(chunks)
            db.session.commit()
            print(f"[DocumentProcessor] 文献 {document_id} 处理完成，共 {len(chunks)} 个分块")

        except Exception as e:
            print(f"[DocumentProcessor] 文献 {document_id} 处理失败: {e}")
            try:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                db.session.commit()
            except Exception:
                db.session.rollback()


@documents_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_document():
    """上传 PDF 文献"""
    user_id = int(get_jwt_identity())

    if "file" not in request.files:
        return error_response("未选择文件")

    file = request.files["file"]
    if file.filename == "":
        return error_response("文件名为空")

    if not allowed_file(file.filename):
        return error_response("仅支持 PDF 格式文件")

    try:
        # 保存文件：safe_filename 用于磁盘存储，raw_filename 用于展示
        raw_filename = file.filename
        safe_filename_part = secure_filename(raw_filename) or "document.pdf"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{safe_filename_part}"

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "./uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, safe_filename)
        file.save(file_path)

        file_size = os.path.getsize(file_path)

        # 获取用户提供的标题和作者，默认用原始文件名（含中文）去掉扩展名
        display_name = os.path.splitext(raw_filename)[0] if raw_filename else "document"
        title = request.form.get("title", "").strip() or display_name
        authors = request.form.get("authors", "").strip()

        # 创建 Document 记录
        doc = Document(
            user_id=user_id,
            title=title,
            authors=authors,
            filename=raw_filename,
            file_path=file_path,
            file_size=file_size,
            status="pending",
        )
        db.session.add(doc)
        db.session.commit()

        # 异步触发解析任务
        app = current_app._get_current_object()
        thread = threading.Thread(target=process_document_async, args=(app, doc.id))
        thread.daemon = True
        thread.start()

        return success_response({"document_id": doc.id}, "文献上传成功，正在处理中"), 201

    except Exception as e:
        db.session.rollback()
        return error_response(f"上传失败: {str(e)}", status_code=500)


@documents_bp.route("", methods=["GET"])
@jwt_required()
def list_documents():
    """获取文献列表"""
    user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    search = request.args.get("search", "").strip()

    query = Document.query.filter_by(user_id=user_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Document.title.ilike(search_pattern),
                Document.authors.ilike(search_pattern),
            )
        )

    query = query.order_by(Document.upload_time.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response({
        "documents": [doc.to_dict() for doc in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@documents_bp.route("/<int:doc_id>", methods=["GET"])
@jwt_required()
def get_document(doc_id):
    """获取文献详情"""
    user_id = int(get_jwt_identity())
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return error_response("文献不存在", status_code=404)
    return success_response(doc.to_dict())


@documents_bp.route("/<int:doc_id>", methods=["DELETE"])
@jwt_required()
def delete_document(doc_id):
    """删除文献"""
    user_id = int(get_jwt_identity())
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return error_response("文献不存在", status_code=404)

    try:
        # 删除文件
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        # 删除向量库数据
        try:
            vector_store = VectorStoreService()
            vector_store.delete_document(doc_id)
        except Exception as e:
            print(f"删除向量数据失败: {e}")

        # 删除数据库记录（级联删除 chunks）
        db.session.delete(doc)
        db.session.commit()

        return success_response(message="文献已删除")
    except Exception as e:
        db.session.rollback()
        return error_response(f"删除失败: {str(e)}", status_code=500)


@documents_bp.route("/<int:doc_id>/status", methods=["GET"])
@jwt_required()
def get_document_status(doc_id):
    """获取文献处理状态"""
    user_id = int(get_jwt_identity())
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return error_response("文献不存在", status_code=404)
    return success_response({
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "message": doc.error_message if doc.status == "failed" else "",
    })


@documents_bp.route("/<int:doc_id>/preview", methods=["GET"])
@jwt_required(locations=["headers", "query_string"])
def preview_document(doc_id):
    """在线预览 PDF 文件，支持 header 或 ?token=xxx 传递 JWT"""
    user_id = int(get_jwt_identity())
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return error_response("文献不存在", status_code=404)

    file_path = os.path.abspath(doc.file_path)
    if not doc.file_path or not os.path.exists(file_path):
        return error_response("文件不存在", status_code=404)

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=doc.filename or "document.pdf",
    )

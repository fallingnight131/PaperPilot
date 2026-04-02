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
from ..models.user import User
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


def _set_progress(doc, progress: int, message: str):
    """更新文献处理进度并立即提交"""
    doc.progress = progress
    doc.status_message = message
    db.session.commit()


def process_document_async(app, document_id):
    """异步处理文献：解析 PDF、生成 embedding、写入向量库"""
    with app.app_context():
        doc = Document.query.get(document_id)
        if not doc:
            return

        # 已在处理中或已完成，跳过（防止 Flask reloader 双进程重复触发）
        if doc.status in ("processing", "ready"):
            return

        try:
            # 1. 开始处理
            doc.status = "processing"
            _set_progress(doc, 5, "正在解析 PDF 元数据…")

            # 2. 解析元数据
            parser = PDFParser()

            # 记录用户上传时填写的信息（优先级最高）
            user_title = doc.title if doc.title != os.path.splitext(doc.filename)[0] else ""
            user_authors = doc.authors
            user_doi = doc.doi

            # 从 PDF 中提取元数据（DOI、摘要、语言）
            metadata = parser.extract_metadata(doc.file_path)

            # DOI：用户填写 > PDF 提取
            doi = user_doi or metadata.get("doi") or ""
            doc.doi = doi

            if metadata.get("abstract"):
                doc.abstract = metadata["abstract"]
            if metadata.get("language"):
                doc.language = metadata["language"]

            # 若标题或作者缺失，通过 DOI 查询
            need_title = not user_title
            need_authors = not user_authors
            doi_meta = {}
            if doi and (need_title or need_authors):
                doi_meta = parser._query_doi_metadata(doi)

            # 标题：用户填写 > DOI 查询 > 文件名
            if user_title:
                doc.title = user_title
            elif doi_meta.get("title"):
                doc.title = doi_meta["title"]
            # else: 保持上传时设置的文件名

            # 作者：用户填写 > DOI 查询 > 未知
            if user_authors:
                doc.authors = user_authors
            elif doi_meta.get("authors"):
                doc.authors = doi_meta["authors"]
            else:
                doc.authors = "未知"

            _set_progress(doc, 20, "正在分析文本并分块…")

            # 3. 分块
            chunks = parser.parse_and_chunk(doc.file_path)
            if not chunks:
                doc.status = "failed"
                doc.error_message = "PDF 未提取到有效文本"
                doc.status_message = ""
                db.session.commit()
                return

            for chunk in chunks:
                chunk["title"] = doc.title
                chunk["authors"] = doc.authors

            n_chunks = len(chunks)
            _set_progress(doc, 40, f"正在生成向量嵌入（共 {n_chunks} 个分块）…")

            # 4. 批量获取 embedding，每批更新进度
            llm_client = DoubaoClient()
            texts = [c["content"] for c in chunks]

            def on_batch(done, total):
                pct = 40 + int(done / total * 45)  # 40% → 85%
                _set_progress(doc, pct, f"正在生成向量嵌入（{done}/{total} 批）…")

            embeddings = llm_client.batch_embed(texts, batch_size=20,
                                                progress_callback=on_batch)

            # 5. 写入 ChromaDB
            _set_progress(doc, 90, "正在写入向量数据库…")
            vector_store = VectorStoreService()
            chroma_ids = vector_store.add_chunks(document_id, chunks, embeddings)

            # 6. 写入 DocumentChunk 记录
            _set_progress(doc, 95, "正在保存分块信息…")
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

            # 7. 完成
            doc.status = "ready"
            doc.chunk_count = n_chunks
            doc.progress = 100
            doc.status_message = ""
            db.session.commit()
            print(f"[DocumentProcessor] 文献 {document_id} 处理完成，共 {n_chunks} 个分块")

        except Exception as e:
            print(f"[DocumentProcessor] 文献 {document_id} 处理失败: {e}")
            try:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                doc.status_message = ""
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

        # 文件名去扩展名作为默认标题
        display_name = os.path.splitext(raw_filename)[0] if raw_filename else "document"
        user_title = request.form.get("title", "").strip()
        user_authors = request.form.get("authors", "").strip()
        user_doi = request.form.get("doi", "").strip()

        # 创建 Document 记录（标题暂用文件名，处理时按优先级覆盖）
        doc = Document(
            user_id=user_id,
            title=user_title or display_name,
            authors=user_authors,
            doi=user_doi,
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
                Document.doi.ilike(search_pattern),
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


@documents_bp.route("/<int:doc_id>", methods=["PUT"])
@jwt_required()
def update_document(doc_id):
    """更新文献信息（标题、作者、DOI）"""
    user_id = int(get_jwt_identity())
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return error_response("文献不存在", status_code=404)

    data = request.get_json() or {}

    try:
        # 仅允许更新这三个字段
        if "title" in data:
            title = data["title"].strip()
            if not title:
                return error_response("标题不能为空")
            doc.title = title

        if "authors" in data:
            # 作者可以为空，格式：用分号分隔的 "Author1; Author2; Author3"
            authors = data["authors"].strip()
            doc.authors = authors

        if "doi" in data:
            # DOI 可以为空
            doi = data["doi"].strip()
            doc.doi = doi

        db.session.commit()

        # 同步更新向量库中的 metadata
        if doc.status == "ready" and ("title" in data or "authors" in data):
            vector_store = VectorStoreService()
            vector_store.update_document_metadata(
                doc_id,
                title=doc.title if "title" in data else None,
                authors=doc.authors if "authors" in data else None,
            )

        return success_response(doc.to_dict(), "文献信息已更新")

    except Exception as e:
        db.session.rollback()
        return error_response(f"更新失败: {str(e)}", status_code=500)


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
        "progress": doc.progress or 0,
        "status_message": doc.status_message or "",
        "chunk_count": doc.chunk_count,
        "message": doc.error_message if doc.status == "failed" else "",
    })


@documents_bp.route("/library", methods=["GET"])
@jwt_required()
def list_library():
    """获取所有用户的已就绪文献（文献库）"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "").strip()
    uploader = request.args.get("uploader", "").strip()

    query = Document.query.filter_by(status="ready")

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Document.title.ilike(search_pattern),
                Document.authors.ilike(search_pattern),
                Document.doi.ilike(search_pattern),
            )
        )

    if uploader:
        query = query.join(User, Document.user_id == User.id).filter(
            User.username.ilike(f"%{uploader}%")
        )

    query = query.order_by(Document.upload_time.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response({
        "documents": [doc.to_dict() for doc in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@documents_bp.route("/<int:doc_id>/preview", methods=["GET"])
@jwt_required(locations=["headers", "query_string"])
def preview_document(doc_id):
    """在线预览 PDF 文件，支持 header 或 ?token=xxx 传递 JWT。任意登录用户均可访问。"""
    doc = Document.query.get(doc_id)
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

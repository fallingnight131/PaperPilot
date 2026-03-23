from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models.conversation import Conversation, Message
from ..services.rag_service import RAGService

chat_bp = Blueprint("chat", __name__)


def success_response(data=None, message="success"):
    return jsonify({"code": 0, "data": data or {}, "message": message})


def error_response(message="error", code=1, status_code=400):
    return jsonify({"code": code, "message": message}), status_code


@chat_bp.route("/conversations", methods=["POST"])
@jwt_required()
def create_conversation():
    """创建新会话"""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    title = data.get("title", "新会话").strip() or "新会话"

    try:
        conv = Conversation(user_id=user_id, title=title)
        db.session.add(conv)
        db.session.commit()
        return success_response(conv.to_dict(), "会话创建成功"), 201
    except Exception as e:
        db.session.rollback()
        return error_response(f"创建会话失败: {str(e)}", status_code=500)


@chat_bp.route("/conversations", methods=["GET"])
@jwt_required()
def list_conversations():
    """获取会话列表"""
    user_id = int(get_jwt_identity())
    conversations = Conversation.query.filter_by(user_id=user_id) \
        .order_by(Conversation.updated_at.desc()).all()
    return success_response({
        "conversations": [c.to_dict() for c in conversations]
    })


@chat_bp.route("/conversations/<int:conv_id>/messages", methods=["GET"])
@jwt_required()
def get_messages(conv_id):
    """获取会话消息列表"""
    user_id = int(get_jwt_identity())
    conv = Conversation.query.filter_by(id=conv_id, user_id=user_id).first()
    if not conv:
        return error_response("会话不存在", status_code=404)

    messages = Message.query.filter_by(conversation_id=conv_id) \
        .order_by(Message.created_at.asc()).all()
    return success_response({
        "messages": [m.to_dict() for m in messages]
    })


@chat_bp.route("/ask", methods=["POST"])
@jwt_required()
def ask_question():
    """RAG 智能问答"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data:
        return error_response("请求数据为空")

    question = data.get("question", "").strip()
    conversation_id = data.get("conversation_id")
    doc_ids = data.get("doc_ids")  # 可选，限定检索范围

    if not question:
        return error_response("问题不能为空")

    # 验证会话归属
    if conversation_id:
        conv = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
        if not conv:
            return error_response("会话不存在", status_code=404)

    try:
        rag_service = RAGService()
        result = rag_service.answer_question(
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            doc_ids=doc_ids,
        )
        return success_response(result)
    except Exception as e:
        return error_response(f"问答失败: {str(e)}", status_code=500)


@chat_bp.route("/conversations/<int:conv_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conv_id):
    """删除会话"""
    user_id = int(get_jwt_identity())
    conv = Conversation.query.filter_by(id=conv_id, user_id=user_id).first()
    if not conv:
        return error_response("会话不存在", status_code=404)

    try:
        db.session.delete(conv)
        db.session.commit()
        return success_response(message="会话已删除")
    except Exception as e:
        db.session.rollback()
        return error_response(f"删除会话失败: {str(e)}", status_code=500)

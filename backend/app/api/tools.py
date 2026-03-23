from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..services.tool_registry import tool_registry

tools_bp = Blueprint("tools", __name__)


def success_response(data=None, message="success"):
    return jsonify({"code": 0, "data": data or {}, "message": message})


def error_response(message="error", code=1, status_code=400):
    return jsonify({"code": code, "message": message}), status_code


@tools_bp.route("/translate", methods=["POST"])
@jwt_required()
def translate():
    """翻译工具"""
    data = request.get_json()
    if not data:
        return error_response("请求数据为空")

    text = data.get("text", "").strip()
    if not text:
        return error_response("翻译文本不能为空")

    target_language = data.get("target_language", "中文")
    source_language = data.get("source_language", "")

    try:
        result = tool_registry.run_tool("translate", {
            "text": text,
            "target_language": target_language,
            "source_language": source_language,
        })
        return success_response(result)
    except Exception as e:
        return error_response(f"翻译失败: {str(e)}", status_code=500)


@tools_bp.route("/summarize", methods=["POST"])
@jwt_required()
def summarize():
    """摘要解读工具"""
    data = request.get_json()
    if not data:
        return error_response("请求数据为空")

    document_id = data.get("document_id")
    text = data.get("text", "").strip()

    if not document_id and not text:
        return error_response("请提供 document_id 或 text")

    try:
        result = tool_registry.run_tool("summarize", {
            "document_id": document_id,
            "text": text,
        })
        if result.get("error"):
            return error_response(result["error"], status_code=500)
        return success_response(result)
    except Exception as e:
        return error_response(f"生成摘要失败: {str(e)}", status_code=500)


@tools_bp.route("/list", methods=["GET"])
@jwt_required()
def list_tools():
    """获取工具列表"""
    tools = tool_registry.list_tools()
    return success_response({"tools": tools})

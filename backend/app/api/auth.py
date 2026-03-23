from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..extensions import db
from ..models.user import User

auth_bp = Blueprint("auth", __name__)


def success_response(data=None, message="success"):
    return jsonify({"code": 0, "data": data or {}, "message": message})


def error_response(message="error", code=1, status_code=400):
    return jsonify({"code": code, "message": message}), status_code


@auth_bp.route("/register", methods=["POST"])
def register():
    """用户注册"""
    data = request.get_json()
    if not data:
        return error_response("请求数据为空")

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    # 参数验证
    if not username or not email or not password:
        return error_response("用户名、邮箱和密码不能为空")

    if len(username) < 2 or len(username) > 80:
        return error_response("用户名长度应为 2-80 个字符")

    if len(password) < 6:
        return error_response("密码长度不能少于 6 个字符")

    # 检查用户名和邮箱是否已存在
    if User.query.filter_by(username=username).first():
        return error_response("用户名已存在")

    if User.query.filter_by(email=email).first():
        return error_response("邮箱已被注册")

    # 创建用户
    try:
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return success_response({"user_id": user.id}, "注册成功"), 201
    except Exception as e:
        db.session.rollback()
        return error_response(f"注册失败: {str(e)}", status_code=500)


@auth_bp.route("/login", methods=["POST"])
def login():
    """用户登录"""
    data = request.get_json()
    if not data:
        return error_response("请求数据为空")

    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return error_response("邮箱和密码不能为空")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return error_response("邮箱或密码错误", status_code=401)

    # 生成 JWT token
    access_token = create_access_token(identity=str(user.id))
    return success_response({
        "access_token": access_token,
        "user": user.to_dict(),
    }, "登录成功")


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    """获取当前用户信息"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return error_response("用户不存在", status_code=404)
    return success_response(user.to_dict())


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """用户登出（客户端删除 token 即可）"""
    return success_response(message="登出成功")

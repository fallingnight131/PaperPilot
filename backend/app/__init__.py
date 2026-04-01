import os
from flask import Flask
from .config import Config
from .extensions import db, jwt, cors


def create_app(config_class=Config):
    """Flask 应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 确保上传目录存在
    upload_folder = app.config.get("UPLOAD_FOLDER", "./uploads")
    os.makedirs(upload_folder, exist_ok=True)

    # 确保 ChromaDB 目录存在
    chroma_path = app.config.get("CHROMA_DB_PATH", "./chroma_db")
    os.makedirs(chroma_path, exist_ok=True)

    # 初始化扩展
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # 注册蓝图
    from .api.auth import auth_bp
    from .api.documents import documents_bp
    from .api.chat import chat_bp
    from .api.tools import tools_bp
    from .api.knowledge import knowledge_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(documents_bp, url_prefix="/api/documents")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(tools_bp, url_prefix="/api/tools")
    app.register_blueprint(knowledge_bp, url_prefix="/api/knowledge")

    # 初始化工具注册表
    from .services.tool_registry import tool_registry
    from .tools.translate_tool import TranslateTool
    from .tools.summarize_tool import SummarizeTool

    tool_registry.register(TranslateTool())
    tool_registry.register(SummarizeTool())

    # 创建数据库表
    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()
        # 迁移：为旧数据库补充 doi 字段
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE documents ADD COLUMN doi VARCHAR(255) DEFAULT ''"))
                conn.commit()
        except Exception:
            pass  # 字段已存在，忽略

    return app

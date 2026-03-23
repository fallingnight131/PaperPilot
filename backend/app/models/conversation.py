import json
from datetime import datetime
from ..extensions import db


class Conversation(db.Model):
    """会话模型"""
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), default="新会话")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    messages = db.relationship("Message", backref="conversation", lazy="dynamic",
                               cascade="all, delete-orphan", order_by="Message.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.messages.count(),
        }

    def __repr__(self):
        return f"<Conversation {self.title}>"


class Message(db.Model):
    """消息模型"""
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user / assistant
    content = db.Column(db.Text, nullable=False)
    sources_json = db.Column(db.Text, default="[]")  # JSON 存储引用来源列表
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def sources(self):
        """获取引用来源列表"""
        try:
            return json.loads(self.sources_json) if self.sources_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @sources.setter
    def sources(self, value):
        """设置引用来源列表"""
        self.sources_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Message {self.role} in conv={self.conversation_id}>"

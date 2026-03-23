from datetime import datetime
from ..extensions import db


class Document(db.Model):
    """文献文档模型"""
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False, default="未命名文献")
    authors = db.Column(db.String(1000), default="")
    abstract = db.Column(db.Text, default="")
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending", index=True)  # pending/processing/ready/failed
    chunk_count = db.Column(db.Integer, default=0)
    language = db.Column(db.String(20), default="unknown")
    error_message = db.Column(db.Text, default="")

    # 关系
    chunks = db.relationship("DocumentChunk", backref="document", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "filename": self.filename,
            "file_size": self.file_size,
            "upload_time": self.upload_time.isoformat() if self.upload_time else None,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "language": self.language,
        }

    def __repr__(self):
        return f"<Document {self.title}>"

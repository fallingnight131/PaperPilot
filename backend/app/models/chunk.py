from datetime import datetime
from ..extensions import db


class DocumentChunk(db.Model):
    """文献分块模型"""
    __tablename__ = "document_chunks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    page_number = db.Column(db.Integer, default=0)
    char_start = db.Column(db.Integer, default=0)
    char_end = db.Column(db.Integer, default=0)
    chroma_id = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "page_number": self.page_number,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "chroma_id": self.chroma_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<DocumentChunk doc={self.document_id} index={self.chunk_index}>"

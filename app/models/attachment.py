from app.extensions import db
from datetime import datetime, timezone


class RequestAttachment(db.Model):
    __tablename__ = "request_attachment"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("test_request.id"), nullable=False)
    filename = db.Column(db.String(512), nullable=False)           # stored filename on disk
    original_filename = db.Column(db.String(256), nullable=False)  # original upload name
    file_size = db.Column(db.Integer, nullable=True)               # bytes
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<RequestAttachment {self.original_filename} req={self.request_id}>"

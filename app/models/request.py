from app.extensions import db
from datetime import datetime, timezone
import random
import string


def generate_tr_number():
    """Generate a unique provisional TR# like TR-12345. The engineer renames it on accept."""
    suffix = "".join(random.choices(string.digits, k=5))
    return f"TR-{suffix}"


class TestRequest(db.Model):
    __tablename__ = "test_request"

    id = db.Column(db.Integer, primary_key=True)
    tr_number = db.Column(db.String(20), unique=True, nullable=False, default=generate_tr_number)

    # Status: submitted | returned | awaiting_parts | parts_shipped | in_progress | closed
    status = db.Column(db.String(20), nullable=False, default="submitted")

    # Foreign keys
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assigned_engineer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey("test_service.id"), nullable=False)

    # --- Test INFO fields ---
    priority = db.Column(db.String(10), nullable=False)
    need_by_date = db.Column(db.Date, nullable=True)
    test_type = db.Column(db.String(64), nullable=False, default="Checkvalve Performance")

    # Location & identification
    location = db.Column(db.String(32), nullable=True)
    department = db.Column(db.String(128), nullable=True)
    project = db.Column(db.String(128), nullable=True)
    part_number = db.Column(db.String(64), nullable=True)

    # Valve type
    valve_type = db.Column(db.String(128), nullable=True)
    valve_type_other = db.Column(db.String(256), nullable=True)

    # Report type
    report_type = db.Column(db.String(20), nullable=True)   # 'data_only' or 'custom'
    report_notes = db.Column(db.Text, nullable=True)

    # Checkvalve Performance sub-fields
    max_forward_pressure = db.Column(db.String(64), nullable=True)
    fluid = db.Column(db.String(10), nullable=True)
    previously_tested = db.Column(db.Boolean, default=False, nullable=False)
    previous_tr_numbers = db.Column(db.String(256), nullable=True)
    test_purpose = db.Column(db.Text, nullable=True)
    additional_instructions = db.Column(db.Text, nullable=True)

    total_groups = db.Column(db.Integer, nullable=False, default=1)

    # Result file (uploaded by engineer to close request)
    result_file_path = db.Column(db.String(512), nullable=True)
    result_original_filename = db.Column(db.String(256), nullable=True)

    # Estimated delivery (set by engineer when parts received)
    estimated_delivery = db.Column(db.Date, nullable=True)

    # Timestamps
    date_submitted = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    date_shipped = db.Column(db.DateTime, nullable=True)
    date_parts_received = db.Column(db.DateTime, nullable=True)
    date_closed = db.Column(db.DateTime, nullable=True)

    # Relationships
    part_groups = db.relationship(
        "PartGroup", backref="request", lazy="dynamic", cascade="all, delete-orphan", order_by="PartGroup.group_letter"
    )
    comments = db.relationship(
        "Comment", backref="request", lazy="dynamic", cascade="all, delete-orphan", order_by="Comment.timestamp"
    )
    attachments = db.relationship(
        "RequestAttachment", backref="request", lazy="dynamic", cascade="all, delete-orphan"
    )

    STATUS_LABELS = {
        "submitted": "Submitted",
        "returned": "Returned for Changes",
        "awaiting_parts": "Awaiting Parts",
        "parts_shipped": "Parts Shipped",
        "in_progress": "In Progress",
        "closed": "Closed",
    }

    PRIORITY_LABELS = {
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def priority_label(self):
        return self.PRIORITY_LABELS.get(self.priority, self.priority)

    @property
    def valve_type_display(self):
        if self.valve_type == "other":
            return self.valve_type_other or "Other"
        return self.valve_type or ""

    @property
    def can_be_downloaded(self):
        """Closed requests are available for 90 days."""
        if self.status != "closed" or not self.date_closed:
            return False
        delta = datetime.now(timezone.utc) - self.date_closed.replace(tzinfo=timezone.utc)
        return delta.days <= 90

    def __repr__(self):
        return f"<TestRequest {self.tr_number} [{self.status}]>"

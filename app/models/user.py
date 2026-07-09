import secrets
from datetime import datetime, timedelta, timezone
from app.extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

RESET_TOKEN_VALIDITY = timedelta(hours=1)


# Association: which test services an engineer handles
engineer_services = db.Table(
    "engineer_services",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("service_id", db.Integer, db.ForeignKey("test_service.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    # role: 'client' or 'engineer'
    role = db.Column(db.String(16), nullable=False, default="client")

    # Email verification
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(128), nullable=True)

    # Password reset
    reset_token = db.Column(db.String(128), nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)

    # Forces password change on first login (used for engineer accounts)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)

    # Engineer-only: which test services this engineer handles
    services = db.relationship("TestService", secondary=engineer_services, backref="engineers")

    # Relationships
    submitted_requests = db.relationship(
        "TestRequest", foreign_keys="TestRequest.requester_id", backref="requester", lazy="dynamic"
    )
    assigned_requests = db.relationship(
        "TestRequest", foreign_keys="TestRequest.assigned_engineer_id", backref="assigned_engineer", lazy="dynamic"
    )
    comments = db.relationship("Comment", backref="author", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_verification_token(self):
        self.verification_token = secrets.token_urlsafe(32)

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.now(timezone.utc) + RESET_TOKEN_VALIDITY

    @property
    def reset_token_valid(self):
        if not self.reset_token or not self.reset_token_expires:
            return False
        return datetime.now(timezone.utc) < self.reset_token_expires.replace(tzinfo=timezone.utc)

    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expires = None

    @property
    def display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    @property
    def is_engineer(self):
        return self.role == "engineer"

    @property
    def is_client(self):
        return self.role == "client"

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class TestService(db.Model):
    """A type of test that can be requested (e.g. Air Flow, Water Flow)."""
    __tablename__ = "test_service"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    requests = db.relationship("TestRequest", backref="service", lazy="dynamic")

    def __repr__(self):
        return f"<TestService {self.name}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

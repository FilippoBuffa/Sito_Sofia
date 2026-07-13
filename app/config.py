import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = 28800  # 8 hours — long request form can stay open a full workday
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ATTACHMENT_FOLDER = os.path.join(BASE_DIR, "uploads", "attachments")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB per file
    MAX_ATTACHMENTS = 3

    # Flask-Mail (Gmail SMTP)
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = ("Vernay TestLab", os.environ.get("MAIL_USERNAME"))

    # Base URL for links in emails
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5001")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db")


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db"))


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

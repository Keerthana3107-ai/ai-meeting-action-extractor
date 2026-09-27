import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load environment variables if .env exists
load_dotenv(BASE_DIR / ".env")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-action-extractor-secret-key-987654321")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", f"sqlite:///{BASE_DIR / 'meeting_actions.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload and Export configuration
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    EXPORT_FOLDER = BASE_DIR / "exports"
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16 MB max
    ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}
    
    # NLP / Feature settings
    DUPLICATE_SIMILARITY_THRESHOLD = 0.75
    MIN_CONFIDENCE_THRESHOLD = 0.35

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    DEBUG = False

config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}

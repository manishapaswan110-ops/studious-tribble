import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "student-backend-dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'backend' / 'data' / 'student_backend.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False

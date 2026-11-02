from datetime import datetime

from flask_login import UserMixin

from ..extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    courses = db.relationship("Course", back_populates="user", cascade="all, delete-orphan")
    subjects = db.relationship("Subject", back_populates="user", cascade="all, delete-orphan")
    topics = db.relationship("Topic", back_populates="user", cascade="all, delete-orphan")
    tests = db.relationship("Test", back_populates="user", cascade="all, delete-orphan")
    test_attempts = db.relationship("TestAttempt", back_populates="user", cascade="all, delete-orphan")
    flashcards = db.relationship("Flashcard", back_populates="user", cascade="all, delete-orphan")
    flashcard_reviews = db.relationship("FlashcardReview", back_populates="user", cascade="all, delete-orphan")
    weekly_reports = db.relationship("WeeklyReport", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

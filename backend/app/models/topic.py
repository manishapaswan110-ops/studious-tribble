from datetime import datetime

from ..extensions import db


class Topic(db.Model):
    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True)
    topic_name = db.Column(db.String(120), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    subject = db.relationship("Subject", back_populates="topics")
    user = db.relationship("User", back_populates="topics")
    questions = db.relationship("Question", back_populates="topic", cascade="all, delete-orphan")
    flashcards = db.relationship("Flashcard", back_populates="topic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "topic_name": self.topic_name,
            "subject_id": self.subject_id,
            "description": self.description,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

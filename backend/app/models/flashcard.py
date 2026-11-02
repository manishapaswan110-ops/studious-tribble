from datetime import datetime

from ..extensions import db


class Flashcard(db.Model):
    __tablename__ = "flashcards"

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    topic = db.relationship("Topic", back_populates="flashcards")
    user = db.relationship("User", back_populates="flashcards")
    reviews = db.relationship("FlashcardReview", back_populates="flashcard", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "topic_id": self.topic_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FlashcardReview(db.Model):
    __tablename__ = "flashcard_reviews"

    id = db.Column(db.Integer, primary_key=True)
    flashcard_id = db.Column(db.Integer, db.ForeignKey("flashcards.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    review_status = db.Column(db.String(30), default="pending")
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    flashcard = db.relationship("Flashcard", back_populates="reviews")
    user = db.relationship("User", back_populates="flashcard_reviews")

    def to_dict(self):
        return {
            "id": self.id,
            "flashcard_id": self.flashcard_id,
            "user_id": self.user_id,
            "review_status": self.review_status,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

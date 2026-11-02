from datetime import datetime

from ..extensions import db


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(120), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    course = db.relationship("Course", back_populates="subjects")
    user = db.relationship("User", back_populates="subjects")
    topics = db.relationship("Topic", back_populates="subject", cascade="all, delete-orphan")
    tests = db.relationship("Test", back_populates="subject", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_name": self.subject_name,
            "course_id": self.course_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

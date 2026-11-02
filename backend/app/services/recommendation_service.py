from sqlalchemy import func

from ..models import Question, TestAttempt


def generate_recommendations(user_id):
    weak_topics = []
    results = (
        TestAttempt.query.filter_by(user_id=user_id)
        .with_entities(
            TestAttempt.id,
            TestAttempt.accuracy_percentage,
        )
        .all()
    )

    if not results:
        return [{"topic": "General revision", "reason": "Create a first assessment to identify weak areas."}]

    average_accuracy = sum(r[1] for r in results) / len(results)
    if average_accuracy < 70:
        weak_topics.append({
            "topic": "Practice accuracy improvement",
            "reason": "Your recent attempts are below target. Focus on quick review and short drills.",
        })

    total_questions = Question.query.count()
    if total_questions:
        weak_topics.append({
            "topic": "Concept refresh",
            "reason": "Review the foundational questions for each topic and retake a short test.",
        })

    return weak_topics

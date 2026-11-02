from flask import Blueprint, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Flashcard, FlashcardReview, Topic
from ..utils.helpers import error_response, success_response
from ..utils.validators import validate_record_ownership

flashcards_bp = Blueprint("flashcards", __name__)


@flashcards_bp.route("/flashcards", methods=["GET"])
@login_required
def list_flashcards():
    topic_id = request.args.get("topic_id", type=int)
    query = Flashcard.query.filter_by(user_id=current_user.id)
    if topic_id is not None:
        topic = Topic.query.get(topic_id)
        if topic is None or topic.user_id != current_user.id:
            return error_response("Topic not found for this user.", 404)
        query = query.filter_by(topic_id=topic_id)
    cards = query.order_by(Flashcard.created_at.desc()).all()
    return success_response({"flashcards": [card.to_dict() for card in cards]}, 200)


@flashcards_bp.route("/flashcards", methods=["POST"])
@login_required
def create_flashcard():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    answer = (payload.get("answer") or "").strip()
    topic_id = payload.get("topic_id")

    if not question or not answer or not topic_id:
        return error_response("question, answer and topic_id are required.", 400)

    topic = Topic.query.get(topic_id)
    if topic is None or topic.user_id != current_user.id:
        return error_response("Topic not found for this user.", 404)

    card = Flashcard(question=question, answer=answer, topic_id=topic.id, user_id=current_user.id)
    db.session.add(card)
    db.session.commit()
    return success_response({"flashcard": card.to_dict()}, 201)


@flashcards_bp.route("/flashcards/<int:flashcard_id>/review", methods=["POST"])
@login_required
def review_flashcard(flashcard_id):
    card = validate_record_ownership(Flashcard.query.get(flashcard_id), current_user.id)
    payload = request.get_json(silent=True) or {}
    status = (payload.get("review_status") or "pending").strip()
    review = FlashcardReview(
        flashcard_id=card.id,
        user_id=current_user.id,
        review_status=status,
    )
    db.session.add(review)
    db.session.commit()
    return success_response({"review": review.to_dict()}, 201)

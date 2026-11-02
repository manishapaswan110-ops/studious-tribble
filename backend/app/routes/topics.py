from flask import Blueprint, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Subject, Topic
from ..utils.helpers import error_response, success_response
from ..utils.validators import validate_record_ownership

topics_bp = Blueprint("topics", __name__)


@topics_bp.route("/topics", methods=["GET"])
@login_required
def list_topics():
    subject_id = request.args.get("subject_id", type=int)
    query = Topic.query.filter_by(user_id=current_user.id)
    if subject_id is not None:
        subject = Subject.query.get(subject_id)
        if subject is None or subject.user_id != current_user.id:
            return error_response("Subject not found for this user.", 404)
        query = query.filter_by(subject_id=subject_id)

    topics = query.order_by(Topic.topic_name.asc()).all()
    return success_response({"topics": [topic.to_dict() for topic in topics]}, 200)


@topics_bp.route("/topics", methods=["POST"])
@login_required
def create_topic():
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    topic_name = (payload.get("topic_name") or "").strip()
    description = (payload.get("description") or "").strip()

    if not subject_id or not topic_name:
        return error_response("subject_id and topic_name are required.", 400)

    subject = Subject.query.get(subject_id)
    if subject is None or subject.user_id != current_user.id:
        return error_response("Subject not found for this user.", 404)

    topic = Topic(topic_name=topic_name, subject_id=subject.id, description=description, user_id=current_user.id)
    db.session.add(topic)
    db.session.commit()
    return success_response({"topic": topic.to_dict()}, 201)


@topics_bp.route("/topics/<int:topic_id>", methods=["PUT"])
@login_required
def update_topic(topic_id):
    topic = validate_record_ownership(Topic.query.get(topic_id), current_user.id)
    payload = request.get_json(silent=True) or {}
    topic.topic_name = (payload.get("topic_name") or topic.topic_name).strip()
    topic.description = (payload.get("description") or topic.description or "").strip()
    if not topic.topic_name:
        return error_response("topic_name cannot be empty.", 400)
    db.session.commit()
    return success_response({"topic": topic.to_dict()}, 200)


@topics_bp.route("/topics/<int:topic_id>", methods=["DELETE"])
@login_required
def delete_topic(topic_id):
    topic = validate_record_ownership(Topic.query.get(topic_id), current_user.id)
    db.session.delete(topic)
    db.session.commit()
    return success_response({"message": "Topic deleted successfully."}, 200)

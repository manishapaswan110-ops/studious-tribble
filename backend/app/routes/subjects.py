from flask import Blueprint, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Course, Subject
from ..utils.helpers import error_response, success_response
from ..utils.validators import validate_record_ownership

subjects_bp = Blueprint("subjects", __name__)


@subjects_bp.route("/subjects", methods=["GET"])
@login_required
def list_subjects():
    course_id = request.args.get("course_id", type=int)
    query = Subject.query.filter_by(user_id=current_user.id)
    if course_id is not None:
        course = Course.query.get(course_id)
        if course is None or course.user_id != current_user.id:
            return error_response("Course not found for this user.", 404)
        query = query.filter_by(course_id=course_id)
    subjects = query.order_by(Subject.subject_name.asc()).all()
    return success_response({"subjects": [subject.to_dict() for subject in subjects]}, 200)


@subjects_bp.route("/subjects", methods=["POST"])
@login_required
def create_subject():
    payload = request.get_json(silent=True) or {}
    course_id = payload.get("course_id")
    subject_name = (payload.get("subject_name") or "").strip()
    if not course_id or not subject_name:
        return error_response("course_id and subject_name are required.", 400)

    course = Course.query.get(course_id)
    if course is None or course.user_id != current_user.id:
        return error_response("Course not found for this user.", 404)

    subject = Subject(subject_name=subject_name, course_id=course.id, user_id=current_user.id)
    db.session.add(subject)
    db.session.commit()
    return success_response({"subject": subject.to_dict()}, 201)


@subjects_bp.route("/subjects/<int:subject_id>", methods=["PUT"])
@login_required
def update_subject(subject_id):
    subject = validate_record_ownership(Subject.query.get(subject_id), current_user.id)
    payload = request.get_json(silent=True) or {}
    subject.subject_name = (payload.get("subject_name") or subject.subject_name).strip()
    if not subject.subject_name:
        return error_response("subject_name cannot be empty.", 400)
    db.session.commit()
    return success_response({"subject": subject.to_dict()}, 200)


@subjects_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
@login_required
def delete_subject(subject_id):
    subject = validate_record_ownership(Subject.query.get(subject_id), current_user.id)
    db.session.delete(subject)
    db.session.commit()
    return success_response({"message": "Subject deleted successfully."}, 200)

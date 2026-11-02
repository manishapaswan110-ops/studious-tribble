from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from ..utils.helpers import error_response, success_response
from ..utils.validators import is_valid_email, is_valid_password

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    payload = request.get_json(silent=True) or {}
    full_name = (payload.get("full_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not full_name or not email or not password:
        return error_response("Full name, email and password are required.", 400)
    if not is_valid_email(email):
        return error_response("A valid email address is required.", 400)
    if not is_valid_password(password):
        return error_response("Password must be at least 8 characters long.", 400)
    if User.query.filter_by(email=email).first():
        return error_response("An account with this email already exists.", 409)

    user = User(full_name=full_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return success_response({"user": user.to_dict()}, 201)


@auth_bp.route("/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return error_response("Email and password are required.", 400)

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return error_response("Invalid login credentials.", 401)

    login_user(user)
    return success_response({"user": user.to_dict()}, 200)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return success_response({"message": "Logged out successfully."}, 200)


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return success_response({"user": current_user.to_dict()}, 200)

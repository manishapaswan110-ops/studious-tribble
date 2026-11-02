import re


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value):
    return bool(value) and bool(EMAIL_RE.match(value.strip()))


def is_valid_password(value):
    return bool(value) and len(value) >= 8


def validate_record_ownership(record, user_id):
    if record is None:
        raise ValueError("Record not found.")
    if getattr(record, "user_id", None) != user_id:
        raise ValueError("You do not have permission to access this record.")
    return record

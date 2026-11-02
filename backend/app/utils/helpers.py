from flask import jsonify


def error_response(message, status_code=400):
    response = jsonify({"error": message})
    response.status_code = status_code
    return response


def success_response(payload, status_code=200):
    response = jsonify(payload)
    response.status_code = status_code
    return response

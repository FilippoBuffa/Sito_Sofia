from flask import Blueprint

bp = Blueprint("engineer", __name__, url_prefix="/engineer")

from . import routes  # noqa: E402, F401

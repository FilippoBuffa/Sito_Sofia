from flask import Blueprint

bp = Blueprint("client", __name__, url_prefix="/client")

from . import routes  # noqa: E402, F401

# routes/debug.py
from flask import Blueprint, jsonify

debug_bp = Blueprint("debug_bp", __name__, url_prefix="/api/debug")

# -------------------------
# Health check
# -------------------------
@debug_bp.route("/health")
def health():
    return "API is running", 200

# -------------------------
# List all routes
# -------------------------
@debug_bp.route("/routes")
def list_routes():
    from app import app  # careful with circular imports; import here
    routes = [str(r) for r in app.url_map.iter_rules()]
    return jsonify(routes)
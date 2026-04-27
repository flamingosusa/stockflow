from flask import Blueprint, render_template

floor_dashboard_bp = Blueprint("floor_dashboard_bp", __name__)

# -------------------------
# FLOOR DASHBOARD PAGE
# -------------------------
@floor_dashboard_bp.route("/floor", methods=["GET"])
def floor_dashboard():
    return render_template("floor_dashboard.html")


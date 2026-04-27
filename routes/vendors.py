# routes/vendors.py
from flask import Blueprint, jsonify, request, render_template
from db import get_db_connection

vendors_bp = Blueprint("vendors_bp", __name__, url_prefix="/api/vendors")


# -------------------------
# VENDOR FORM PAGE
# -------------------------
@vendors_bp.route("/form", methods=["GET"])
def vendor_form():
    return render_template("add_vendor.html")


# -------------------------
# GET ALL VENDORS
# -------------------------
@vendors_bp.route("/", methods=["GET"])
def get_vendors():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT code, name FROM vendors ORDER BY name")
        rows = cur.fetchall()

        # Tuple-safe mapping (works in production)
        result = [
            {
                "code": r["code"],
                "name": r["name"]
            }
            for r in rows
        ]

        return jsonify(result)

    except Exception as e:
        print("[get_vendors] DB error:", e)
        return jsonify({"error": "Failed to fetch vendors"}), 500

    finally:
        cur.close()
        conn.close()


# -------------------------
# GET DISTINCT VENDORS (from products table)
# -------------------------
@vendors_bp.route("/distinct", methods=["GET"])
def fetch_distinct_vendors():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT DISTINCT vendor FROM products ORDER BY vendor")
        rows = cur.fetchall()

        vendors = [
            {"vendor": r[0]}
            for r in rows
        ]

        return jsonify(vendors)

    except Exception as e:
        print("[fetch_distinct_vendors] DB error:", e)
        return jsonify({"error": "Failed to fetch distinct vendors"}), 500

    finally:
        cur.close()
        conn.close()


# -------------------------
# ADD NEW VENDOR
# -------------------------
@vendors_bp.route("/add", methods=["POST"])
def add_vendor():
    data = request.get_json()

    code = data.get("code")
    name = data.get("name")

    if not code or not name:
        return jsonify({"error": "Vendor code and name required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO vendors (code, name) VALUES (%s, %s)",
            (code.upper(), name)
        )

        conn.commit()
        return jsonify({"message": "Vendor added successfully"})

    except Exception as e:
        print("[add_vendor] DB error:", e)
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
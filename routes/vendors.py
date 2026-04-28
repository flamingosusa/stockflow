# routes/vendors.py
from flask import Blueprint, jsonify, request, render_template
from db import get_db_connection

vendors_bp = Blueprint("vendors_bp", __name__, url_prefix="/api/vendors")


# -------------------------
# Helper: tuple + dict rows
# -------------------------
def row_to_vendor(r):
    if isinstance(r, dict):
        return {
            "code": r["code"],
            "name": r["name"]
        }

    return {
        "code": r[0],
        "name": r[1]
    }


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

        result = [row_to_vendor(r) for r in rows]

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

        vendors = []

        for r in rows:
            if isinstance(r, dict):
                vendors.append({"vendor": r["vendor"]})
            else:
                vendors.append({"vendor": r[0]})

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
            (code.upper(), name.upper())
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
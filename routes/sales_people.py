# routes/sales_people.py
from flask import Blueprint, render_template, request, jsonify
from db import get_db_connection

sales_people_bp = Blueprint("sales_people", __name__)

# =========================
# FORM PAGE
# =========================
@sales_people_bp.route("/api/sales-people/form", methods=["GET"])
def sales_people_form():
    return render_template("sales_people.html")


# =========================
# GET ALL
# =========================
@sales_people_bp.route("/api/sales-people", methods=["GET"])
def get_sales_people():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT sales_person_id, name
            FROM sales_people
            ORDER BY name
        """)

        rows = cur.fetchall()

        return jsonify([
            {
                "sales_person_id": r["sales_person_id"],
                "name": r["name"]
            }
            for r in rows
        ])

    except Exception as e:
        print("[sales_people GET ERROR]:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# =========================
# ADD NEW
# =========================
@sales_people_bp.route("/api/sales-people", methods=["POST"])
def add_sales_person():
    data = request.get_json()

    sales_person_id = data.get("sales_person_id")
    name = (data.get("name") or "").strip()

    if not sales_person_id:
        return jsonify({"error": "Sales Person ID required"}), 400

    if not name:
        return jsonify({"error": "Name required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO sales_people (sales_person_id, name)
            VALUES (%s, %s)
        """, (sales_person_id, name))

        conn.commit()

        return jsonify({
            "message": "Sales person added successfully"
        })

    except Exception as e:
        conn.rollback()
        print("[sales_people POST ERROR]:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
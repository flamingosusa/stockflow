# routes/movements.py
from flask import Blueprint, jsonify, request
from db import get_db_connection
from datetime import datetime

movements_bp = Blueprint("movements", __name__)

# -------------------------------
# GET stock by item
# -------------------------------
@movements_bp.route("/api/stock/item", methods=["GET"])
def get_stock_by_item():
    product_id = request.args.get("q", type=int)
    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    # Total stock
    cur.execute("""
        SELECT COALESCE(SUM(
            CASE 
                WHEN movement_type = 'IN' THEN quantity
                WHEN movement_type = 'OUT' THEN -quantity
                ELSE 0
            END
        ), 0)
        FROM inventory_movements
        WHERE product_id = %s
    """, (product_id,))
    total = cur.fetchone()[0]

    # Transactions - newest first
    cur.execute("""
        SELECT id, movement_type, quantity, created_at, notes
        FROM inventory_movements
        WHERE product_id = %s
        ORDER BY created_at DESC
    """, (product_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    transactions = []
    for r in rows:
        transactions.append({
            "id": r[0],
            "type": r[1],
            "qty": r[2],
            "date": r[3].isoformat() if isinstance(r[3], datetime) else r[3],
            "notes": r[4] or ""
        })

    return jsonify({"total": int(total), "transactions": transactions})

# -------------------------
# Create a stock movement
# -------------------------
@movements_bp.route("", methods=["POST"])
def create_movement():
    data = request.get_json()
    required = ["product_id", "movement_type", "quantity"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    product_id = data["product_id"]
    movement_type = data["movement_type"]
    quantity = data["quantity"]
    notes = data.get("notes", "")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO inventory_movements (product_id, movement_type, quantity, notes)
            VALUES (%s, %s, %s, %s)
        """, (product_id, movement_type, quantity, notes))
        conn.commit()
        return jsonify({"status": "movement recorded"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

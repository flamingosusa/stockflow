# routes/stock.py
from flask import Blueprint, jsonify, request
from db import get_db_connection
from datetime import datetime

stock_bp = Blueprint("stock_bp", __name__, url_prefix="/api/stock")


# -------------------------
# Get available stock for a product
# -------------------------
@stock_bp.route("/item", methods=["GET"])
def get_stock_by_item():
    product_id = request.args.get("q", type=int)

    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Total stock
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN movement_type = 'IN' THEN quantity
                    WHEN movement_type = 'OUT' THEN -quantity
                    WHEN movement_type = 'ADJUST' THEN quantity
                    ELSE 0
                END
            ), 0) AS total
            FROM inventory_movements
            WHERE product_id = %s
        """, (product_id,))

        total_row = cur.fetchone()
        total = total_row[0] if total_row else 0

        # Transactions
        cur.execute("""
            SELECT id, movement_type, quantity, created_at, notes, invoice_number
            FROM inventory_movements
            WHERE product_id = %s
            ORDER BY created_at DESC
        """, (product_id,))

        rows = cur.fetchall()

        transactions = []
        for r in rows:
            transactions.append({
                "id": r[0],
                "type": r[1],
                "qty": r[2],
                "date": r[3].isoformat() if isinstance(r[3], datetime) else r[3],
                "notes": r[4] or "",
                "invoice_number": r[5] or ""
            })

        return jsonify({
            "total": max(int(total), 0),
            "transactions": transactions
        })

    except Exception as e:
        print("[stock/item] DB error:", e)
        return jsonify({"error": "Stock fetch failed"}), 500

    finally:
        cur.close()
        conn.close()


# -------------------------
# Update stock movement
# -------------------------
@stock_bp.route("/update", methods=["POST"])
def update_stock():
    data = request.get_json()

    product_id = data.get("product_id")
    qty_change = int(data.get("qty_change", 0))
    movement_type = data.get("movement_type")
    related_id = data.get("related_id")
    notes = data.get("notes", "")

    if not product_id or not movement_type:
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Current stock
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN movement_type = 'IN' THEN quantity
                    WHEN movement_type = 'OUT' THEN -quantity
                    WHEN movement_type = 'ADJUST' THEN quantity
                    ELSE 0
                END
            ), 0) AS current_qty
            FROM inventory_movements
            WHERE product_id = %s
        """, (product_id,))

        row = cur.fetchone()
        current_qty = row[0] if row else 0

        # Calculate new stock
        new_qty = current_qty + (qty_change if movement_type != "OUT" else -qty_change)

        if new_qty < 0:
            return jsonify({"error": "Stock cannot go negative"}), 400

        # Insert movement
        cur.execute("""
            INSERT INTO inventory_movements
            (product_id, movement_type, quantity, created_at, notes, related_id)
            VALUES (%s, %s, %s, NOW(), %s, %s)
        """, (product_id, movement_type, qty_change, notes, related_id))

        conn.commit()

        return jsonify({
            "message": "Stock updated successfully",
            "new_qty": new_qty
        })

    except Exception as e:
        conn.rollback()
        print("[stock/update] DB error:", e)
        return jsonify({"error": "Stock update failed"}), 500

    finally:
        cur.close()
        conn.close()


# -------------------------
# Get item options for dropdowns
# -------------------------
@stock_bp.route("/options/item", methods=["GET"])
def stock_options_item():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, item, description, color
            FROM products
            ORDER BY item
        """)

        rows = cur.fetchall()

        options = [
            {
                "value": r[0],
                "item": r[1],
                "description": r[2] or "",
                "color": r[3] or ""
            }
            for r in rows
        ]

        return jsonify(options)

    except Exception as e:
        print("[stock/options/item] DB error:", e)
        return jsonify({"error": "Failed to load items"}), 500

    finally:
        cur.close()
        conn.close()
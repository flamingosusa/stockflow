# routes/stock.py
from flask import Blueprint, jsonify, request
from db import get_db_connection
from datetime import datetime

stock_bp = Blueprint("stock_bp", __name__, url_prefix="/api/stock")

# -------------------------
# Get available stock for a product (with invoice numbers for sales)
# -------------------------
@stock_bp.route("/item", methods=["GET"])
def get_stock_by_item():
    product_id = request.args.get("q", type=int)
    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
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
        total = total_row["total"] if total_row and "total" in total_row else 0

        # Transactions - newest first
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
                "id": r["id"],
                "type": r["movement_type"],
                "qty": r["quantity"],
                "date": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else r["created_at"],
                "notes": r["notes"] or "",
                "invoice_number": r["invoice_number"] or ""
            })

        return jsonify({
            "total": max(int(total), 0),
            "transactions": transactions
        })
    finally:
        cur.close()
        conn.close()

# -------------------------
# Update stock movement (lock negative stock)
# -------------------------
@stock_bp.route("/update", methods=["POST"])
def update_stock():
    data = request.get_json()
    product_id = data.get("product_id")
    qty_change = int(data.get("qty_change", 0))
    movement_type = data.get("movement_type")  # 'IN', 'OUT', 'ADJUST'
    related_id = data.get("related_id")  # optional
    notes = data.get("notes", "")

    if not product_id or not movement_type:
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
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
        current_qty = row["current_qty"] if row and "current_qty" in row else 0

        # Calculate new stock
        new_qty = current_qty + (qty_change if movement_type != 'OUT' else -qty_change)
        if new_qty < 0:
            return jsonify({"error": "Stock cannot go negative"}), 400

        # Insert movement
        cur.execute("""
            INSERT INTO inventory_movements
            (product_id, movement_type, quantity, created_at, notes, related_id)
            VALUES (%s, %s, %s, NOW(), %s, %s)
        """, (product_id, movement_type, qty_change, notes, related_id))

        conn.commit()
        return jsonify({"message": "Stock updated successfully", "new_qty": new_qty})

    finally:
        cur.close()
        conn.close()


# -------------------------
# Get item options for dropdowns
# -------------------------
@stock_bp.route("/options/item", methods=["GET"])
def stock_options_item():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, item, description, color FROM products ORDER BY item")
        rows = cur.fetchall()
        options = [
            {
                "value": r["id"],         # product ID
                "item": r["item"],        # keep 'item' key for frontend
                "description": r["description"] or "",
                "color": r["color"] or ""
            }
            for r in rows
        ]
        return jsonify(options)
    finally:
        cur.close()
        conn.close()
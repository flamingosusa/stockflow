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
    cur = conn.cursor()
    try:
        # Total stock (all movements)
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN movement_type = 'IN' THEN quantity
                    WHEN movement_type = 'OUT' THEN -quantity
                    WHEN movement_type = 'ADJUST' THEN quantity
                    ELSE 0
                END
            ), 0)
            FROM inventory_movements
            WHERE product_id = %s
        """, (product_id,))
        total = cur.fetchone()[0]

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
                "id": r[0],
                "type": r[1],
                "qty": r[2],
                "date": r[3].isoformat() if isinstance(r[3], datetime) else r[3],
                "notes": r[4] or "",
                "invoice_number": r[5] or ""   # <-- directly from inventory_movements
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
    related_id = data.get("related_id")  # optional, e.g., sale ID
    notes = data.get("notes", "")

    if not product_id or not movement_type:
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get current stock
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN movement_type = 'IN' THEN quantity
                    WHEN movement_type = 'OUT' THEN -quantity
                    WHEN movement_type = 'ADJUST' THEN quantity
                    ELSE 0
                END
            ), 0)
            FROM inventory_movements
            WHERE product_id = %s
        """, (product_id,))
        current_qty = cur.fetchone()[0]

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
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, item, description, color FROM products ORDER BY item")
        rows = cur.fetchall()
        options = [
            {
                "value": r[0],       # product ID
                "item": r[1],        # keep 'item' for compatibility
                "description": r[2] or "",
                "color": r[3] or ""
            }
            for r in rows
        ]
        return jsonify(options)
    finally:
        cur.close()
        conn.close()
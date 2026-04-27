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

    from psycopg2.extras import RealDictCursor
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # =========================
        # TOTAL STOCK
        # =========================
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
        AND (location IS NULL OR location = 'WAREHOUSE')
    """, (product_id,))

        row = cur.fetchone()
        total = float(row["total"] if row else 0)

        # =========================
        # TRANSACTIONS
        # =========================
        cur.execute("""
            SELECT 
                id,
                movement_type,
                quantity,
                created_at,
                notes,
                invoice_number
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
                "date": r["created_at"].isoformat() if r["created_at"] else None,
                "notes": r["notes"] or "",
                "invoice_number": r["invoice_number"] or ""
            })

        return jsonify({
            "total": max(int(total), 0),
            "transactions": transactions
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()

# -------------------------
# Update stock movement (SAFE)
# -------------------------
@stock_bp.route("/update", methods=["POST"])
def update_stock():
    data = request.get_json()

    product_id = data.get("product_id")
    qty_change = int(data.get("qty_change", 0))
    movement_type = data.get("movement_type")
    related_id = data.get("related_id")
    notes = data.get("notes", "")
    location = data.get("location", None)

    if not product_id or not movement_type:
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
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

        row = cur.fetchone()
        current_qty = float(row["movement_type"] or 0) if row else 0

        new_qty = current_qty + (qty_change if movement_type != "OUT" else -qty_change)

        if new_qty < 0:
            return jsonify({"error": "Stock cannot go negative"}), 400

        try:
            cur.execute("""
                INSERT INTO inventory_movements
                (product_id, movement_type, quantity, created_at, notes, related_id, location)
                VALUES (%s, %s, %s, NOW(), %s, %s, %s)
            """, (product_id, movement_type, qty_change, notes, related_id, location))
        except Exception:
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
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# -------------------------
# 🔥 MOVE TO FLOOR (NEW)
# -------------------------
@stock_bp.route("/move-to-floor", methods=["POST"])
def move_to_floor():
    data = request.get_json()

    print("MOVE TO FLOOR RAW:", data)

    product_id = data.get("product_id")
    qty = 1  # force rule

    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # STEP 1: check stock exists
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
        
        row = cur.fetchone()
        stock = list(row.values())[0] if row else 0
        
        if stock < 1:
            return jsonify({"error": "No stock available"}), 400

        # =========================
        # MOVE TO FLOOR (CORRECT)
        # =========================

        # 1. REMOVE from warehouse
        cur.execute("""
            INSERT INTO inventory_movements
            (product_id, movement_type, quantity, created_at, notes, location)
            VALUES (%s, 'OUT', 1, NOW(), 'Moved to FLOOR', 'WAREHOUSE')
        """, (product_id,))

        # 2. ADD to floor
        cur.execute("""
            INSERT INTO inventory_movements
            (product_id, movement_type, quantity, created_at, notes, location)
            VALUES (%s, 'IN', 1, NOW(), 'Moved to FLOOR', 'FLOOR')
        """, (product_id,))

        conn.commit()

        return jsonify({"message": "Moved to floor"}), 200

    except Exception as e:
        conn.rollback()
        print("🔥 MOVE TO FLOOR ERROR:", repr(e))
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
# -------------------------
# 🔁 RETURN FROM FLOOR (NEW)
# -------------------------
@stock_bp.route("/revert-floor-sale", methods=["POST"])
def revert_floor_sale():
    data = request.get_json()
    product_id = data.get("product_id")

    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO inventory_movements
            (product_id, movement_type, quantity, created_at, notes, location)
            VALUES (%s, 'IN', 1, NOW(), 'Reverted FLOOR sale', 'FLOOR')
        """, (product_id,))

        conn.commit()
        return jsonify({"message": "Item available on floor again"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
# -------------------------
# FLOOR DASHBOARD
# -------------------------
@stock_bp.route("/floor", methods=["GET"], endpoint="floor_stock")
def get_floor_stock():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
        SELECT 
            p.id,
            p.item,
            p.sku,
            p.vendor,
            p.color,
            p.description,
            p.lot_type,
            p.cost,
            p.sale_price,

            CASE 
                WHEN (
                    SELECT m.movement_type
                    FROM inventory_movements m
                    WHERE m.product_id = p.id
                      AND m.location = 'FLOOR'
                    ORDER BY m.created_at DESC
                    LIMIT 1
                ) = 'IN'
                THEN 1
                ELSE 0
            END AS on_floor

        FROM products p
        ORDER BY p.item
        """)

        rows = cur.fetchall()

        return jsonify([
            {
                "id": r["id"],
                "item": r["item"],
                "sku": r["sku"],
                "vendor": r["vendor"],
                "color": r["color"],
                "description": r["description"],
                "lot_type": r["lot_type"],
                "cost": float(r["cost"] or 0),
                "sale_price": float(r["sale_price"] or 0),
                "on_floor": bool(r["on_floor"])
            }
            for r in rows
        ])

    except Exception as e:
        print("[floor ERROR]:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
# --------------------------
# SELL OFF FLOOR
# --------------------------
@stock_bp.route("/sell-from-floor", methods=["POST"])
def sell_from_floor():
    data = request.get_json()

    product_id = data.get("product_id")

    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # ✅ CHECK LAST FLOOR STATE (FIXED)
        cur.execute("""
            SELECT m.movement_type
            FROM inventory_movements m
            WHERE m.product_id = %s
              AND m.location = 'FLOOR'
            ORDER BY m.created_at DESC
            LIMIT 1
        """, (product_id,))

        row = cur.fetchone()
        last_state = row["movement_type"] if row else None

        print("LAST FLOOR STATE:", last_state)

        if last_state != 'IN':
            return jsonify({"error": "Item not on floor"}), 400

        # ✅ SELL (REMOVE FROM FLOOR)
        cur.execute("""
            INSERT INTO inventory_movements
            (product_id, movement_type, quantity, created_at, notes, location)
            VALUES (%s, 'OUT', 1, NOW(), 'Sold from FLOOR', 'FLOOR')
        """, (product_id,))

        conn.commit()

        return jsonify({"message": "Sold from floor"})

    except Exception as e:
        conn.rollback()
        print("🔥 FULL SELL ERROR:", repr(e))
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
        
# -------------------------
# Get item options
# -------------------------
@stock_bp.route("/options/item", methods=["GET"])
def stock_options_item():
    conn = get_db_connection()

    from psycopg2.extras import RealDictCursor
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT id, item, description, color
            FROM products
            ORDER BY item
        """)

        rows = cur.fetchall()

        print("ROWS TYPE:", type(rows))
        print("FIRST ROW:", rows[0] if rows else "EMPTY")

        result = []
        for r in rows:
            result.append({
                "value": r["id"],
                "item": r["item"],
                "description": r.get("description", ""),
                "color": r.get("color", "")
            })

        return jsonify(result)

    except Exception as e:
        print("🔥 FULL ERROR:", repr(e))
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


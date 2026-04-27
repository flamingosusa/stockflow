# routes/dashboard.py
from flask import Blueprint, request, jsonify
from db import get_db_connection

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/api/dashboard", methods=["GET"])
def dashboard():
    warehouse = request.args.get("warehouse")
    vendor = request.args.get("vendor")
    status_filter = request.args.get("status")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT 
                p.id,
                p.sku,
                p.item,
                p.vendor,
                p.color,
                p.whs_location,
                p.lot_type,
                p.description,
                p.cost,

                COALESCE(SUM(
                    CASE
                        WHEN m.movement_type = 'IN' THEN m.quantity
                        WHEN m.movement_type = 'OUT' THEN -m.quantity
                        WHEN m.movement_type = 'ADJUST' THEN m.quantity
                        ELSE 0
                    END
                ), 0) AS stock,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM inventory_movements f_in
                        WHERE f_in.product_id = p.id
                          AND f_in.location = 'FLOOR'
                          AND f_in.movement_type = 'IN'
                          AND COALESCE((
                              SELECT SUM(
                                  CASE
                                      WHEN f2.movement_type = 'IN' THEN f2.quantity
                                      WHEN f2.movement_type = 'OUT' THEN -f2.quantity
                                      WHEN f2.movement_type = 'ADJUST' THEN f2.quantity
                                      ELSE 0
                                  END
                              )
                              FROM inventory_movements f2
                              WHERE f2.product_id = p.id
                                AND f2.location = 'FLOOR'
                          ), 0) > 0
                    )
                    THEN 1
                    ELSE 0
                END AS is_on_floor

            FROM products p

            LEFT JOIN inventory_movements m
                ON p.id = m.product_id
                AND (m.location IS NULL OR m.location = 'WAREHOUSE')
        """

        filters = []
        params = []

        if warehouse:
            filters.append("p.whs_location = %s")
            params.append(warehouse)

        if vendor:
            filters.append("p.vendor = %s")
            params.append(vendor)

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += """
            GROUP BY
                p.id, p.sku, p.item, p.vendor, p.color,
                p.whs_location, p.lot_type, p.description, p.cost
            ORDER BY p.item
        """

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        result = []

        for r in rows:
            try:
                is_dict = isinstance(r, dict)

                # ✅ corrected indexes
                stock = r["stock"] if is_dict else r[9]
                stock = float(stock or 0)

                is_on_floor = r["is_on_floor"] if is_dict else r[10]
                is_on_floor = bool(is_on_floor)

                cost = r["cost"] if is_dict else r[8]
                cost = float(cost or 0)

                if stock <= 0:
                    status = "OUT"
                    badge = "badge-out"
                elif stock <= 2:
                    status = "LOW"
                    badge = "badge-low"
                else:
                    status = "IN STOCK"
                    badge = "badge-ok"

                if status_filter and status != status_filter:
                    continue

                result.append({
                    "id": r["id"] if is_dict else r[0],
                    "sku": r["sku"] if is_dict else r[1],
                    "item": r["item"] if is_dict else r[2],
                    "vendor": r["vendor"] if is_dict else r[3],
                    "color": (r["color"] if is_dict else r[4]) or "",
                    "whs_location": r["whs_location"] if is_dict else r[5],
                    "lot_type": r["lot_type"] if is_dict else r[6],
                    "description": (r["description"] if is_dict else r[7]) or "",
                    "cost": cost,
                    "stock": stock,
                    "status": status,
                    "status_class": badge,
                    "is_on_floor": is_on_floor
                })

            except Exception as row_error:
                print("[dashboard ROW ERROR]:", r, row_error)
                continue

        return jsonify(result)

    except Exception as e:
        print("[dashboard ERROR]:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
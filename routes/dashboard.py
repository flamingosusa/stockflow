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

    query = """
        SELECT p.id, p.sku, p.item, p.vendor, p.color,
               p.whs_location, p.lot_type,
               p.description,   -- ✅ ADDED
               COALESCE(SUM(
                   CASE
                       WHEN m.movement_type='IN' THEN m.quantity
                       WHEN m.movement_type='OUT' THEN -m.quantity
                       WHEN m.movement_type='ADJUST' THEN m.quantity
                   END
               ),0) AS stock
        FROM products p
        LEFT JOIN inventory_movements m ON p.id=m.product_id
    """

    filters, params = [], []
    if warehouse:
        filters.append("p.whs_location=%s")
        params.append(warehouse)
    if vendor:
        filters.append("p.vendor=%s")
        params.append(vendor)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += """
        GROUP BY p.id,p.sku,p.item,p.vendor,p.color,
                 p.whs_location,p.lot_type,p.description   -- ✅ ADDED
        ORDER BY p.item
    """

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = []
    for r in rows:
        stock = r[8]  # 👈 shifted index (important)

        if stock <= 0:
            status, badge = "OUT", "badge-out"
        elif stock <= 2:
            status, badge = "LOW", "badge-low"
        else:
            status, badge = "IN STOCK", "badge-ok"

        if status_filter and status != status_filter:
            continue

        result.append({
            "id": r[0],
            "sku": r[1],
            "item": r[2],
            "vendor": r[3],
            "color": r[4],
            "whs_location": r[5],
            "lot_type": r[6],
            "description": r[7],  # ✅ ADDED
            "stock": stock,
            "status": status,
            "status_class": badge
        })

    return jsonify(result)
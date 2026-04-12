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
    cur = conn.cursor()  # must be RealDictCursor from your db.py

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
            COALESCE(SUM(
                CASE
                    WHEN m.movement_type = 'IN' THEN m.quantity
                    WHEN m.movement_type = 'OUT' THEN -m.quantity
                    WHEN m.movement_type = 'ADJUST' THEN m.quantity
                    ELSE 0
                END
            ), 0) AS stock
        FROM products p
        LEFT JOIN inventory_movements m 
            ON p.id = m.product_id
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
            p.whs_location, p.lot_type, p.description
        ORDER BY p.item
    """

    cur.execute(query, tuple(params))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for r in rows:
        stock = r["stock"]

        # Status logic
        if stock <= 0:
            status = "OUT"
            badge = "badge-out"
        elif stock <= 2:
            status = "LOW"
            badge = "badge-low"
        else:
            status = "IN STOCK"
            badge = "badge-ok"

        # Apply status filter if provided
        if status_filter and status != status_filter:
            continue

        result.append({
            "id": r["id"],
            "sku": r["sku"],
            "item": r["item"],
            "vendor": r["vendor"],
            "color": r["color"],
            "whs_location": r["whs_location"],
            "lot_type": r["lot_type"],
            "description": r["description"],
            "stock": stock,
            "status": status,
            "status_class": badge
        })

    return jsonify(result)
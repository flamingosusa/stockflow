# routes/sales_dashboard.py
from flask import Blueprint, render_template, jsonify
from db import get_db_connection
from psycopg2.extras import RealDictCursor

sales_dashboard_bp = Blueprint("sales_dashboard_bp", __name__, template_folder="../templates")

# =========================
# SALES DASHBOARD PAGE
# =========================
@sales_dashboard_bp.route("/reports/sales-dashboard")
def sales_dashboard():
    return render_template("sales_dashboard.html")


# =========================
# DASHBOARD SALES LIST (for table and metrics)
# =========================
@sales_dashboard_bp.route("/reports/sales/list")
def dashboard_sales_list():

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch sales and join items to get lot_type
        cur.execute("""
            SELECT
                s.id,
                s.invoice_number AS invoice,
                s.customer_name AS customer,
                s.sale_date AS date,
                COALESCE(SUM(si.qty),0) AS total_items,
                s.total AS total_amount,
                s.delivery_fee,
                s.status,
                si.id AS item_id,
                si.item,
                si.qty,
                si.line_total,
                COALESCE(si.lot_type,'ALOT') AS lot_type
            FROM sales s
            LEFT JOIN sale_items si
                ON si.sale_id = s.id
            GROUP BY s.id, si.id
            ORDER BY s.sale_date DESC
        """)

        rows = cur.fetchall()

        # Organize sales into dictionary by sale_id
        sales_dict = {}
        for r in rows:
            sid = r["id"]
            if sid not in sales_dict:
                # Initialize sale entry
                sale_entry = {
                    "id": r["id"],
                    "invoice": r["invoice"],
                    "customer": r["customer"],
                    "date": r["date"].strftime("%Y-%m-%d") if r["date"] else "",
                    "total_items": 0,
                    "total_amount": float(r["total_amount"] or 0),
                    "delivery_fee": float(r["delivery_fee"] or 0),
                    "status": r["status"],
                    "status_class": (
                        "badge-ok" if r["status"] == "COMPLETED" else
                        "badge-low" if r["status"] == "PENDING" else
                        "badge-out"
                    ),
                    "items": []
                }
                sales_dict[sid] = sale_entry

            # Add item to sale
            if r["item_id"]:
                sales_dict[sid]["items"].append({
                    "id": r["item_id"],
                    "item": r["item"],
                    "qty": float(r["qty"] or 0),
                    "line_total": float(r["line_total"] or 0),
                    "lot_type": r["lot_type"]
                })
                # Add to total_items
                sales_dict[sid]["total_items"] += float(r["qty"] or 0)

        # Return as list
        sales_list = list(sales_dict.values())

        return jsonify(sales_list)

    finally:
        cur.close()
        conn.close()
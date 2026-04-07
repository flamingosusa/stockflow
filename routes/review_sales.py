from flask import Blueprint, request, jsonify
from db import get_db_connection

review_sales_bp = Blueprint(
    "review_sales_bp",
    __name__,
    url_prefix="/api/sales"
)

@review_sales_bp.route("/review", methods=["GET"])
def list_sales():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT invoice_number, sale_date, customer_name, phone1,
                   tax_amount, delivery_fee, total
            FROM sales
            ORDER BY sale_date DESC
        """)

        rows = cur.fetchall()

        sales = [
            {
                "invoice_number": r[0],
                "sale_date": str(r[1]),
                "customer_name": r[2],
                "phone1": r[3],
                "tax_amount": float(r[4] or 0),
                "delivery_fee": float(r[5] or 0),
                "total": float(r[6] or 0)
            }
            for r in rows
        ]

        return jsonify(sales)
    finally:
        cur.close()
        conn.close()
        
@review_sales_bp.route("/review/<invoice_number>", methods=["GET", "PATCH"])
def edit_sale(invoice_number):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "GET":
            cur.execute(
                "SELECT * FROM sales WHERE invoice_number = %s",
                (invoice_number,)
            )
            sale = cur.fetchone()
            if not sale:
                return jsonify({"error": "Sale not found"}), 404
            return jsonify({"sale": sale})
    finally:
        cur.close()
        conn.close()
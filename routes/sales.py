from flask import Blueprint, jsonify, request
from db import get_db_connection
from psycopg2.extras import RealDictCursor

sales_bp = Blueprint("sales_bp", __name__, url_prefix="/api/sales")

FALLBACK_WHS = "MAIN WHS"

def format_date(d):
    if d:
        return d.strftime("%Y-%m-%d")
    return None


# ----------------------------------------------------
# LOOKUP SALES (Review / Edit page)
# ----------------------------------------------------
@sales_bp.route("/lookup")
def lookup_sales():
    q = request.args.get("q")
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if q:
            cur.execute("""
                SELECT id, invoice_number, sale_date, customer_name, phone1, total
                FROM sales
                WHERE invoice_number ILIKE %s
                   OR customer_name ILIKE %s
                   OR phone1 ILIKE %s
                ORDER BY sale_date DESC
            """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            cur.execute("""
                SELECT id, invoice_number, sale_date, customer_name, phone1, total
                FROM sales
                ORDER BY sale_date DESC
                LIMIT 500
            """)
        rows = cur.fetchall()
        for r in rows:
            r["sale_date"] = format_date(r.get("sale_date"))
        return jsonify(rows)
    finally:
        cur.close()
        conn.close()


# ----------------------------------------------------
# CREATE NEW SALE
# ----------------------------------------------------
@sales_bp.route("", methods=["POST"])
def create_sale():
    data = request.get_json()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        items = data.get("items")
        if not items or not isinstance(items, list):
            return jsonify({"error": "Sale must include items"}), 400

        # INSERT SALE HEADER
        cur.execute("""
            INSERT INTO sales
            (invoice_number, customer_name, sale_date, delivery_date, status,
             email, address, phone1, phone2, sale_type, salesperson,
             delivery_fee, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            data["invoice_number"],
            data["customer_name"],
            data.get("sale_date"),
            data.get("delivery_date"),
            data["status"],
            data.get("email"),
            data.get("address"),
            data.get("phone1"),
            data.get("phone2"),
            data.get("sale_type"),
            data.get("salesperson"),
            data.get("delivery_fee",0),
            data.get("notes")
        ))
        sale_id = cur.fetchone()["id"]
        subtotal = 0

        # PROCESS ITEMS
        for i in items:
            product_id = i["product_id"]
            qty = float(i["qty"])
            price = float(i["price"])
            line_total = qty * price
            subtotal += line_total

            cur.execute("""
                INSERT INTO sale_items
                (sale_id, product_id, sku, item, vendor, description, color, lot_type, qty, price, line_total)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                sale_id,
                product_id,
                i["sku"],
                i["item"],
                i.get("vendor"),
                i.get("description"),
                i.get("color"),
                i.get("lot_type"),
                qty,
                price,
                line_total
            ))

            # INVENTORY MOVEMENT (with invoice_number)
            cur.execute("""
                INSERT INTO inventory_movements
                (product_id, movement_type, quantity, whs_location, reference, invoice_number)
                VALUES (%s,'OUT',%s,%s,%s,%s)
            """, (
                product_id,
                qty,
                FALLBACK_WHS,
                sale_id,
                data["invoice_number"]
            ))

        # TAX + TOTAL
        tax_percent = float(data.get("tax_percent",0))
        delivery_fee = float(data.get("delivery_fee",0))
        tax_amount = subtotal * tax_percent / 100
        total = subtotal + tax_amount + delivery_fee

        cur.execute("""
            UPDATE sales
            SET tax_percent=%s,
                tax_amount=%s,
                total=%s
            WHERE id=%s
        """, (
            tax_percent,
            tax_amount,
            total,
            sale_id
        ))

        conn.commit()
        return jsonify({"status":"created","sale_id":sale_id})

    except Exception as e:
        conn.rollback()
        print("CREATE SALE ERROR:",e)
        return jsonify({"error":str(e)}),500
    finally:
        cur.close()
        conn.close()


# ----------------------------------------------------
# GET OR UPDATE SALE (Edit Sales Page)
# ----------------------------------------------------
@sales_bp.route("/<int:sale_id>", methods=["GET","PATCH"])
def edit_sale(sale_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # GET SALE FOR EDITING
        if request.method == "GET":
            cur.execute("SELECT * FROM sales WHERE id=%s",(sale_id,))
            sale = cur.fetchone()
            if sale:
                sale["sale_date"] = format_date(sale.get("sale_date"))
                sale["delivery_date"] = format_date(sale.get("delivery_date"))
                sale["created_at"] = format_date(sale.get("created_at"))

            cur.execute("""
                SELECT product_id, sku, item, vendor, description, color, lot_type, qty, price
                FROM sale_items
                WHERE sale_id=%s
            """,(sale_id,))
            items = cur.fetchall()

            return jsonify({"sale":sale,"items":items})

        # UPDATE SALE
        data = request.get_json()
        items = data.get("items")
        if not items:
            return jsonify({"error":"Sale must include items"}),400

        # REMOVE OLD INVENTORY MOVEMENTS
        cur.execute("""
            DELETE FROM inventory_movements
            WHERE movement_type='OUT'
            AND reference=%s
        """,(sale_id,))

        # UPDATE HEADER
        cur.execute("""
            UPDATE sales SET
                customer_name=%s,
                sale_date=%s,
                delivery_date=%s,
                status=%s,
                email=%s,
                address=%s,
                phone1=%s,
                phone2=%s,
                sale_type=%s,
                salesperson=%s,
                delivery_fee=%s,
                notes=%s
            WHERE id=%s
        """,(
            data["customer_name"],
            data.get("sale_date"),
            data.get("delivery_date"),
            data["status"],
            data.get("email"),
            data.get("address"),
            data.get("phone1"),
            data.get("phone2"),
            data.get("sale_type"),
            data.get("salesperson"),
            data.get("delivery_fee",0),
            data.get("notes"),
            sale_id
        ))

        # REMOVE OLD ITEMS
        cur.execute("DELETE FROM sale_items WHERE sale_id=%s",(sale_id,))
        subtotal = 0

        # INSERT NEW ITEMS
        for i in items:
            product_id = i["product_id"]
            qty = float(i["qty"])
            price = float(i["price"])
            line_total = qty * price
            subtotal += line_total

            cur.execute("""
                INSERT INTO sale_items
                (sale_id, product_id, sku, item, vendor, description, color, lot_type, qty, price, line_total)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,(
                sale_id,
                product_id,
                i["sku"],
                i["item"],
                i.get("vendor"),
                i.get("description"),
                i.get("color"),
                i.get("lot_type"),
                qty,
                price,
                line_total
            ))

            cur.execute("""
                INSERT INTO inventory_movements
                (product_id, movement_type, quantity, whs_location, reference, invoice_number)
                VALUES (%s,'OUT',%s,%s,%s,%s)
            """,(
                product_id,
                qty,
                FALLBACK_WHS,
                sale_id,
                data["invoice_number"]
            ))

        tax_percent = float(data.get("tax_percent",0))
        delivery_fee = float(data.get("delivery_fee",0))
        tax_amount = subtotal * tax_percent / 100
        total = subtotal + tax_amount + delivery_fee

        cur.execute("""
            UPDATE sales
            SET tax_percent=%s,
                tax_amount=%s,
                total=%s
            WHERE id=%s
        """,(
            tax_percent,
            tax_amount,
            total,
            sale_id
        ))

        conn.commit()
        return jsonify({"status":"updated"})

    except Exception as e:
        conn.rollback()
        print("EDIT SALE ERROR:",e)
        return jsonify({"error":str(e)}),500
    finally:
        cur.close()
        conn.close()


# ----------------------
# UPDATE SALE STATUS
# ----------------------
@sales_bp.route("/<int:sale_id>/status", methods=["PATCH"])
def update_sale_status(sale_id):
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ["Pending", "Completed", "Cancelled"]:
        return jsonify({"error": "Invalid status"}), 400

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get current status
        cur.execute("SELECT status FROM sales WHERE id=%s", (sale_id,))
        sale = cur.fetchone()
        if not sale:
            return jsonify({"error": "Sale not found"}), 404

        current_status = sale["status"]

        # If already cancelled, do not allow changes
        if current_status == "Cancelled":
            return jsonify({"error": "Cancelled sales cannot be changed"}), 400

        # If new status is cancelled, reverse inventory movements
        if new_status == "Cancelled":
            cur.execute("""
                SELECT product_id, quantity FROM inventory_movements
                WHERE reference=%s AND movement_type='OUT'
            """, (sale_id,))
            out_movements = cur.fetchall()
            for mov in out_movements:
                cur.execute("""
                    INSERT INTO inventory_movements (product_id, movement_type, quantity, whs_location, reference)
                    VALUES (%s, 'IN', %s, %s, %s)
                """, (mov["product_id"], mov["quantity"], FALLBACK_WHS, sale_id))

        # Update sale status
        cur.execute("UPDATE sales SET status=%s WHERE id=%s", (new_status, sale_id))
        conn.commit()
        return jsonify({"success": True, "sale_id": sale_id, "status": new_status})

    except Exception as e:
        conn.rollback()
        print("UPDATE STATUS ERROR:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
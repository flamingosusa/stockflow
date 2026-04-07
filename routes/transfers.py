# routes/transfers.py
from flask import Blueprint, jsonify, request
from db import get_db_connection

transfers_bp = Blueprint("transfers_bp", __name__, url_prefix="/api/transfers")


# -------------------------
# CREATE TRANSFER
# -------------------------
@transfers_bp.route("/create", methods=["POST"])
def create_transfer():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        conn.autocommit = False

        transfer_type = data["transfer_type"]   # WH_TO_SHOWROOM, WH_TO_STORE, etc.
        source = data["source_location"]
        destination = data["destination_location"]
        user_id = data["performed_by"]
        notes = data.get("notes")

        cur.execute("""
            INSERT INTO transfers (transfer_type, source_location, destination_location, performed_by, notes, transfer_date)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING transfer_id
        """, (transfer_type, source, destination, user_id, notes))

        transfer_id = cur.fetchone()[0]

        for item in data["items"]:  # list of {sku, item_name, vendor, quantity, notes}
            sku = item["sku"]
            item_name = item["item_name"]
            vendor = item["vendor"]
            qty = int(item["quantity"])
            item_notes = item.get("notes")

            # Insert into transfer_items
            cur.execute("""
                INSERT INTO transfer_items (transfer_id, sku, item_name, vendor, quantity, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (transfer_id, sku, item_name, vendor, qty, item_notes))

            # Deduct from source stock
            cur.execute("""
                UPDATE warehouse_stock
                SET quantity = quantity - %s
                WHERE sku = %s AND location = %s
            """, (qty, sku, source))

            # Add to destination if internal transfer (warehouse → showroom)
            if transfer_type == "WH_TO_SHOWROOM":
                cur.execute("""
                    UPDATE warehouse_stock
                    SET quantity = quantity + %s
                    WHERE sku = %s AND location = %s
                """, (qty, sku, destination))

        conn.commit()
        return jsonify({"success": True, "transfer_id": transfer_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.autocommit = True
        cur.close()
        conn.close()


# -------------------------
# SEARCH TRANSFERS
# -------------------------
@transfers_bp.route("/search", methods=["GET"])
def search_transfers():
    conn = get_db_connection()
    cur = conn.cursor()

    transfer_no = request.args.get("transfer_no")
    transfer_type = request.args.get("type")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    query = """
        SELECT
            t.transfer_no,
            t.transfer_date,
            t.transfer_type,
            COUNT(i.id) AS total_items
        FROM transfers t
        LEFT JOIN transfer_items i
            ON t.transfer_no = i.transfer_no
        WHERE 1=1
    """
    params = []

    if transfer_no:
        query += " AND t.transfer_no ILIKE %s"
        params.append(f"%{transfer_no}%")
    if transfer_type:
        query += " AND t.transfer_type = %s"
        params.append(transfer_type)
    if from_date:
        query += " AND t.transfer_date >= %s"
        params.append(from_date)
    if to_date:
        query += " AND t.transfer_date <= %s"
        params.append(to_date)

    query += """
        GROUP BY t.transfer_no, t.transfer_date, t.transfer_type
        ORDER BY t.transfer_date DESC
        LIMIT 200
    """

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    results = []
    for r in rows:
        results.append({
            "transfer_no": r[0],
            "date": r[1].strftime("%Y-%m-%d"),
            "type": r[2],
            "items": r[3]
        })

    cur.close()
    conn.close()
    return jsonify(results)


# -------------------------
# GET PRODUCT BY ITEM
# -------------------------
@transfers_bp.route("/item/<item>", methods=["GET"])
def get_product_by_item(item):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sku, item, vendor
        FROM products
        WHERE item ILIKE %s
        LIMIT 1
    """, (item,))
    product = cur.fetchone()
    cur.close()
    conn.close()

    if product:
        return jsonify({"sku": product[0], "item": product[1], "vendor": product[2]})
    else:
        return jsonify({"error": "Product not found"}), 404


# -------------------------
# GET DISTINCT VENDORS
# -------------------------
@transfers_bp.route("/vendors", methods=["GET"])
def fetch_vendors():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT vendor
        FROM products
        ORDER BY vendor
    """)
    vendors = [{"vendor": v[0]} for v in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(vendors)


# -------------------------
# GET ALL ITEMS
# -------------------------
@transfers_bp.route("/items", methods=["GET"])
def get_items():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sku, item
        FROM products
        ORDER BY item
    """)
    items = [{"sku": row[0], "item": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(items)
from flask import Blueprint, jsonify, request
from db import get_db_connection
from services.inventory_service import adjust_stock_and_log

products_bp = Blueprint("products_bp", __name__)

# ---------------------------
# SKU Generator Helper (Randomized Version)
# ---------------------------
import random
import string

def generate_sku(vendor_code, item):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Base item code
        item_code = "".join(item.split())[:5].upper()

        while True:
            # Random 4-digit number
            rand_suffix = str(random.randint(1000, 9999))
            sku = f"{vendor_code}-{item_code}-{rand_suffix}"

            # Check if SKU exists in DB
            cur.execute("SELECT 1 FROM products WHERE sku=%s", (sku,))
            if not cur.fetchone():
                return sku

    finally:
        cur.close()
        conn.close()

# ---------------------------
# API endpoint to generate SKU
# ---------------------------
@products_bp.route("/api/products/generate-sku", methods=["POST"])
def generate_sku_endpoint():
    data = request.get_json()
    vendor = data.get("vendor")
    item = data.get("item")
    if not vendor or not item:
        return jsonify({"error": "Missing vendor or item"}), 400
    sku = generate_sku(vendor, item)
    return jsonify({"sku": sku})

# ---------------------------
# GET all products
# ---------------------------
@products_bp.route("/api/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, sku, item, vendor, description, color, sale_price, whs_location, lot_type, cost, freight, extended_cost
            FROM products ORDER BY item
        """)
        rows = cur.fetchall()
        return jsonify([{
            "id": r[0], "sku": r[1], "item": r[2], "vendor": r[3],
            "description": r[4] or "", "color": r[5] or "",
            "sale_price": float(r[6] or 0), "whs_location": r[7], "lot_type": r[8],
            "cost": float(r[9] or 0), "freight": float(r[10] or 0), "extended_cost": float(r[11] or 0)
        } for r in rows])
    finally:
        cur.close()
        conn.close()

# ---------------------------
# GET single product
# ---------------------------
@products_bp.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, sku, item, vendor, color, whs_location, lot_type, description, cost, sale_price, freight, extended_cost
            FROM products WHERE id=%s
        """, (product_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Product not found"}), 404
        return jsonify({
            "id": row[0], "sku": row[1], "item": row[2], "vendor": row[3],
            "color": row[4], "whs_location": row[5], "lot_type": row[6],
            "description": row[7] or "", "cost": float(row[8]), "sale_price": float(row[9]),
            "freight": float(row[10] or 0), "extended_cost": float(row[11] or 0)
        })
    finally:
        cur.close()
        conn.close()

# ---------------------------
# CREATE product with freight & extended cost
# ---------------------------
@products_bp.route("/api/products", methods=["POST"])
def create_product():
    data = request.get_json()
    required = ["item","vendor","whs_location","lot_type","cost","initial_qty"]
    for r in required:
        if r not in data:
            return jsonify({"error": f"Missing field '{r}'"}), 400

    # Generate SKU if not provided
    if not data.get("sku"):
        data["sku"] = generate_sku(data["vendor"], data["item"])

    cost = float(data.get("cost", 0))
    qty = int(data.get("initial_qty", 0))
    freight = float(data.get("freight", 0))  # percentage

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Insert product (no extended_cost here)
        cur.execute("""
            INSERT INTO products
            (sku, item, vendor, color, whs_location, lot_type, description, cost, sale_price, freight)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            data["sku"], data["item"], data["vendor"], data.get("color",""),
            data["whs_location"], data["lot_type"], data.get("description",""),
            cost, float(data.get("sale_price",0)), freight
        ))
        product_id = cur.fetchone()[0]

        # Insert initial inventory movement with extended_cost
        if qty > 0:
            extended_cost = qty * cost * (1 + freight/100)
            cur.execute("""
                INSERT INTO inventory_movements
                (product_id, quantity, whs_location, movement_type, reference, notes, extended_cost)
                VALUES (%s,%s,%s,'IN',NULL,'Initial stock',%s)
            """, (
                product_id,
                qty,
                data["whs_location"],
                extended_cost
            ))

        conn.commit()
        return jsonify({"status":"ok","id":product_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
# ---------------------------
# EDIT product
# ---------------------------
@products_bp.route("/api/products/<int:product_id>", methods=["PATCH"])
def edit_product(product_id):
    data = request.get_json()
    allowed = ["sku","item","vendor","color","whs_location","lot_type","cost","sale_price","description","freight","extended_cost"]
    fields, values = [], []
    for f in allowed:
        if f in data:
            fields.append(f"{f}=%s")
            values.append(data[f])
    if not fields:
        return jsonify({"error":"No fields provided"}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        values.append(product_id)
        cur.execute(f"UPDATE products SET {', '.join(fields)} WHERE id=%s", tuple(values))
        conn.commit()
        return jsonify({"status":"updated"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ---------------------------
# SEARCH products
# ---------------------------
@products_bp.route("/api/products/search", methods=["GET"])
def search_products():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, sku, item, vendor, color, sale_price
            FROM products
            WHERE
                sku ILIKE %s OR
                item ILIKE %s OR
                vendor ILIKE %s
            ORDER BY item
            LIMIT 20
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))

        rows = cur.fetchall()

        return jsonify([
            {
                "id": r[0],
                "sku": r[1],
                "item": r[2],
                "vendor": r[3],
                "color": r[4],
                "sale_price": float(r[5] or 0)
            }
            for r in rows
        ])

    finally:
        cur.close()
        conn.close()
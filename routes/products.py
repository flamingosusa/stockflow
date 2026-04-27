from flask import Blueprint, jsonify, request
from db import get_db_connection
import random

products_bp = Blueprint("products_bp", __name__, url_prefix="/api/products")


# ---------------------------
# Helpers
# ---------------------------
def generate_sku(vendor_code, item):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        item_code = "".join(item.split())[:5].upper()

        while True:
            rand_suffix = str(random.randint(1000, 9999))
            sku = f"{vendor_code}-{item_code}-{rand_suffix}"

            cur.execute("SELECT 1 FROM products WHERE sku = %s", (sku,))
            if not cur.fetchone():
                return sku
    finally:
        cur.close()
        conn.close()


# ---------------------------
# GET ALL PRODUCTS
# ---------------------------
@products_bp.route("", methods=["GET"])
def get_products():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, sku, item, vendor, description, color,
                   sale_price, whs_location, lot_type,
                   cost, freight, extended_cost
            FROM products
            ORDER BY item
        """)

        rows = cur.fetchall()

        result = []

        for r in rows:
            is_dict = isinstance(r, dict)

            result.append({
                "id": r["id"] if is_dict else r[0],
                "sku": r["sku"] if is_dict else r[1],
                "item": r["item"] if is_dict else r[2],
                "vendor": r["vendor"] if is_dict else r[3],
                "description": (r["description"] if is_dict else r[4]) or "",
                "color": (r["color"] if is_dict else r[5]) or "",
                "sale_price": float((r["sale_price"] if is_dict else r[6]) or 0),
                "whs_location": r["whs_location"] if is_dict else r[7],
                "lot_type": r["lot_type"] if is_dict else r[8],
                "cost": float((r["cost"] if is_dict else r[9]) or 0),
                "freight": float((r["freight"] if is_dict else r[10]) or 0),
                "extended_cost": float((r["extended_cost"] if is_dict else r[11]) or 0),
            })

        return jsonify(result)

    except Exception as e:
        print("GET PRODUCTS ERROR:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# ---------------------------
# GET SINGLE PRODUCT
# ---------------------------
@products_bp.route("/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, sku, item, vendor, color,
                   whs_location, lot_type, description,
                   cost, sale_price, freight, extended_cost
            FROM products
            WHERE id = %s
        """, (product_id,))

        row = cur.fetchone()

        if not row:
            return jsonify({"error": "Product not found"}), 404

        return jsonify({
            "id": row[0],
            "sku": row[1],
            "item": row[2],
            "vendor": row[3],
            "color": row[4],
            "whs_location": row[5],
            "lot_type": row[6],
            "description": row[7] or "",
            "cost": float(row[8] or 0),
            "sale_price": float(row[9] or 0),
            "freight": float(row[10] or 0),
            "extended_cost": float(row[11] or 0),
        })

    except Exception as e:
        print("GET PRODUCT ERROR:", e)
        return jsonify({"error": "Server error"}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------
# CREATE PRODUCT
# ---------------------------
@products_bp.route("", methods=["POST"])
def create_product():
    data = request.get_json()

    required = ["item", "vendor", "whs_location", "lot_type", "cost", "initial_qty"]
    for r in required:
        if r not in data:
            return jsonify({"error": f"Missing field '{r}'"}), 400

    sku = data.get("sku") or generate_sku(data["vendor"], data["item"])

    cost = float(data.get("cost", 0))
    qty = int(data.get("initial_qty", 0))
    freight = float(data.get("freight", 0))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO products
            (sku, item, vendor, color, whs_location, lot_type, description,
             cost, sale_price, freight)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            sku,
            data["item"],
            data["vendor"],
            data.get("color", ""),
            data["whs_location"],
            data["lot_type"],
            data.get("description", ""),
            cost,
            float(data.get("sale_price", 0)),
            freight
        ))

        row = cur.fetchone()
        product_id = list(row.values())[0]

        # Initial stock movement
        if qty > 0:
            extended_cost = qty * cost * (1 + freight / 100)

            cur.execute("""
                INSERT INTO inventory_movements
                (product_id, quantity, whs_location, movement_type, notes, extended_cost)
                VALUES (%s,%s,%s,'IN','Initial stock',%s)
            """, (
                product_id,
                qty,
                data["whs_location"],
                extended_cost
            ))

        conn.commit()
        return jsonify({"status": "ok", "id": product_id})

    except Exception as e:
        conn.rollback()
        print("PRODUCT PAYLOAD:", data)
        print("CREATE PRODUCT ERROR:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# ---------------------------
# UPDATE PRODUCT
# ---------------------------
@products_bp.route("/<int:product_id>", methods=["PATCH"])
def edit_product(product_id):
    data = request.get_json()

    allowed = [
        "sku", "item", "vendor", "color", "whs_location",
        "lot_type", "cost", "sale_price", "description",
        "freight", "extended_cost"
    ]

    fields = []
    values = []

    for f in allowed:
        if f in data:
            fields.append(f"{f}=%s")
            values.append(data[f])

    if not fields:
        return jsonify({"error": "No fields provided"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        values.append(product_id)

        cur.execute(
            f"UPDATE products SET {', '.join(fields)} WHERE id=%s",
            tuple(values)
        )

        conn.commit()
        return jsonify({"status": "updated"})

    except Exception as e:
        conn.rollback()
        print("UPDATE PRODUCT ERROR:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# ---------------------------
# SEARCH PRODUCTS
# ---------------------------
@products_bp.route("/search", methods=["GET"])
def search_products():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, sku, item, vendor, color, sale_price
            FROM products
            WHERE sku ILIKE %s OR item ILIKE %s OR vendor ILIKE %s
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

    except Exception as e:
        print("SEARCH ERROR:", e)
        return jsonify({"error": "Search failed"}), 500

    finally:
        cur.close()
        conn.close()


# ---------------------------
# SKU GENERATOR ENDPOINT
# ---------------------------
@products_bp.route("/generate-sku", methods=["POST"])
def generate_sku_endpoint():
    data = request.get_json()

    vendor = data.get("vendor")
    item = data.get("item")

    if not vendor or not item:
        return jsonify({"error": "Missing vendor or item"}), 400

    sku = generate_sku(vendor, item)
    return jsonify({"sku": sku})
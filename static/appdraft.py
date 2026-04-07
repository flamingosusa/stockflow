from flask import Flask, jsonify, request, render_template
import psycopg2
from config import DB_CONFIG

app = Flask(__name__)

# -------------------------
# Database connection
# -------------------------
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# -------------------------
# UI (ROOT)
# -------------------------
@app.route("/")
def ui():
    return render_template("index.html")

# -------------------------
# Health check
# -------------------------
@app.route("/health")
def health():
    return "API is running"

# -------------------------
# DB test
# -------------------------
@app.route("/db-test")
def db_test():
    try:
        conn = get_db_connection()
        conn.close()
        return "Database connection OK"
    except Exception as e:
        return str(e), 500

# -------------------------
# CREATE PRODUCT
# -------------------------
@app.route("/api/products", methods=["POST"])
def create_product():
    data = request.get_json()

    required = ["sku", "item", "vendor", "color", "whs_location"]
    if not all(k in data and data[k] for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products
        (sku, item, vendor, color, whs_location, description, barcode, cost, sale_price)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        data["sku"],
        data["item"],
        data["vendor"],
        data["color"],
        data["whs_location"],
        data.get("description"),
        data.get("barcode"),
        data.get("cost", 0),
        data.get("sale_price", 0)
    ))

    product_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"id": product_id}), 201

# -------------------------
# GET ALL PRODUCTS (DASHBOARD DATA)
# -------------------------
@app.route("/api/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.id,
            p.sku,
            p.item,
            p.vendor,
            p.color,
            COALESCE(SUM(
                CASE
                    WHEN m.movement_type = 'IN' THEN m.quantity
                    WHEN m.movement_type = 'OUT' THEN -m.quantity
                    WHEN m.movement_type = 'ADJUST' THEN m.quantity
                END
            ), 0) AS stock
        FROM products p
        LEFT JOIN inventory_movements m ON p.id = m.product_id
        GROUP BY p.id, p.sku, p.item, p.vendor, p.color
        ORDER BY p.id;
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "sku": r[1],
            "item": r[2],
            "vendor": r[3],
            "color": r[4],
            "stock": r[5]
        } for r in rows
    ])

# -------------------------
# GET SINGLE PRODUCT (NO DUPLICATE NAME)
# -------------------------
@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product_by_id(product_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id, sku, item, vendor, color, whs_location,
            description, barcode, cost, sale_price, min_stock, active, created_at
        FROM products
        WHERE id = %s;
    """, (product_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Product not found"}), 404

    return jsonify({
        "id": row[0],
        "sku": row[1],
        "item": row[2],
        "vendor": row[3],
        "color": row[4],
        "whs_location": row[5],
        "description": row[6],
        "barcode": row[7],
        "cost": float(row[8]),
        "sale_price": float(row[9]),
        "min_stock": row[10],
        "active": row[11],
        "created_at": row[12].isoformat()
    })

# -------------------------
# INVENTORY MOVEMENTS (GENERIC)
# -------------------------
@app.route("/api/movements", methods=["POST"])
def create_movement():
    data = request.get_json()

    if not all(k in data for k in ("product_id", "movement_type", "quantity")):
        return jsonify({"error": "Missing fields"}), 400

    if data["movement_type"] not in ("IN", "OUT", "ADJUST"):
        return jsonify({"error": "Invalid movement_type"}), 400

    if data["quantity"] <= 0:
        return jsonify({"error": "Quantity must be > 0"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO inventory_movements
        (product_id, movement_type, quantity, notes)
        VALUES (%s,%s,%s,%s)
        RETURNING id
    """, (
        data["product_id"],
        data["movement_type"],
        data["quantity"],
        data.get("notes")
    ))

    movement_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"id": movement_id}), 201

# -------------------------
# INVENTORY IN
# -------------------------
@app.route("/api/movements/in", methods=["POST"])
def inventory_in():
    data = request.get_json()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO inventory_movements
        (product_id, movement_type, quantity, notes)
        VALUES (%s, 'IN', %s, %s)
    """, (
        data["product_id"],
        data["quantity"],
        data.get("notes")
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "IN recorded"}), 201

# -------------------------
# INVENTORY OUT
# -------------------------
@app.route("/api/movements/out", methods=["POST"])
def inventory_out():
    data = request.get_json()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO inventory_movements
        (product_id, movement_type, quantity, notes)
        VALUES (%s, 'OUT', %s, %s)
    """, (
        data["product_id"],
        data["quantity"],
        data.get("notes")
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "OUT recorded"}), 201

# -------------------------
# INVENTORY ADJUST
# -------------------------
@app.route("/api/movements/adjust", methods=["POST"])
def inventory_adjust():
    data = request.get_json()

    product_id = data.get("product_id")
    quantity = data.get("quantity")
    notes = data.get("notes")

    if product_id is None or quantity is None:
        return jsonify({"error": "product_id and quantity are required"}), 400

    if quantity == 0:
        return jsonify({"error": "quantity cannot be zero"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO inventory_movements
        (product_id, movement_type, quantity, notes)
        VALUES (%s, 'ADJUST', %s, %s)
        RETURNING id, quantity;
    """, (product_id, quantity, notes))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "status": "ADJUST recorded",
        "movement_id": result[0],
        "quantity_saved": result[1]
    }), 201
# -------------------------
# STOCK ROUTE	
# -------------------------

@app.route("/api/stock", methods=["GET"])
def stock_summary():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.id,
            p.sku,
            p.item,
            COALESCE(SUM(
                CASE
                    WHEN m.movement_type = 'IN' THEN m.quantity
                    WHEN m.movement_type = 'OUT' THEN -m.quantity
                    WHEN m.movement_type = 'ADJUST' THEN m.quantity
                END
            ), 0) AS stock
        FROM products p
        LEFT JOIN inventory_movements m
            ON p.id = m.product_id
        GROUP BY p.id, p.sku, p.item
        ORDER BY p.id;
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "sku": r[1],
            "item": r[2],
            "stock": r[3]
        } for r in rows
    ])


# -------------------------
# ROUTE LIST (DEBUG)
# -------------------------
@app.route("/api/routes")
def list_routes():
    return jsonify([str(r) for r in app.url_map.iter_rules()])


# 🔴 NOTHING ROUTE-RELATED AFTER THIS 🔴
# -------------------------
# START APP
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)

# services/inventory_service.py
def adjust_stock_and_log(cur, product_id, qty, whs_location, movement_type, reference=None, notes=""):
    """
    Adjusts warehouse stock and logs the movement.
    Ensures warehouse_stock row exists and is updated correctly.
    """
    # Normalize warehouse location
    whs_location = (whs_location or "MAIN WHS").strip().upper()

    # Ensure warehouse_stock exists
    cur.execute("""
        INSERT INTO warehouse_stock (product_id, whs_location, min_stock, current_qty)
        VALUES (%s, %s, 0, 0)
        ON CONFLICT (product_id, whs_location) DO NOTHING
    """, (product_id, whs_location))

    # Update current quantity
    cur.execute("""
        UPDATE warehouse_stock
        SET current_qty = current_qty + %s
        WHERE product_id=%s AND whs_location=%s
    """, (qty, product_id, whs_location))

    # Log inventory movement
    cur.execute("""
        INSERT INTO inventory_movements
        (product_id, movement_type, quantity, reference, notes, whs_location, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """, (
        product_id,
        movement_type,
        qty,
        str(reference) if reference else None,
        notes,
        whs_location
    ))
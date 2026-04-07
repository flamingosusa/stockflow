from flask import Blueprint, render_template

ui_bp = Blueprint("ui", __name__)

# -------------------------------------------------
# UI ROUTES
# -------------------------------------------------
@ui_bp.route("/")
def ui():
    return render_template("index.html")

@ui_bp.route("/check-stock")
def check_stock_ui():
    return render_template("check_stock.html")

@ui_bp.route("/sales")
def sales_ui():
    return render_template("sales.html")

@ui_bp.route("/review-sales")
def review_sales():
    return render_template("review_sales.html")

@ui_bp.route("/add-product/single-product")
def add_single_product_ui():
    return render_template("add_product.html")

@ui_bp.route("/add-product/upload-po")
def upload_po_ui():
    return render_template("upload_po.html")

@ui_bp.route("/transfers")
def transfers_page():
    return render_template("transfers.html")

@ui_bp.route("/transfers/review")
def review_transfers():
    return render_template("transfers_review.html")

@ui_bp.route("/transfers/<transfer_number>/pdf")
def transfer_pdf(transfer_number):
    # generate or fetch PDF
    return send_file(...)

@ui_bp.route("/transfers/<transfer_number>/edit")
def edit_transfer(transfer_number):
    return render_template(
        "transfers_edit.html",
        transfer=transfer_data
    )
    
@ui_bp.route("/sales/<invoice_number>/edit")
def edit_sale_page(sale_id):
    return render_template("edit_sale.html", sale_id=sale_id)

@ui_bp.route("/health")
def health():
    return "API is running"

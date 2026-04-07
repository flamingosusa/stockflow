import os
from flask import Flask
from routes.ui import ui_bp
from routes.dashboard import dashboard_bp
from routes.products import products_bp
from routes.sales import sales_bp
from routes.review_sales import review_sales_bp
from routes.transfers import transfers_bp
from routes.vendors import vendors_bp
from routes.stock import stock_bp
from routes.movements import movements_bp
from routes.sales_dashboard import sales_dashboard_bp

app = Flask(__name__)

# Register blueprints
app.register_blueprint(sales_dashboard_bp)
app.register_blueprint(ui_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(products_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(review_sales_bp)
app.register_blueprint(transfers_bp)
app.register_blueprint(vendors_bp)
app.register_blueprint(stock_bp)
app.register_blueprint(movements_bp, url_prefix="/api/movements")

if __name__ == "__main__":
    # Use environment variables if available, otherwise fallback to defaults
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    
    print(f"Starting server on {host}:{port} | Debug={debug}")
    app.run(host=host, port=port, debug=debug)
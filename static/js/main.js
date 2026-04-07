async function loadProducts() {
    const res = await fetch('/api/stock');
    const products = await res.json();
    const tbody = $('#productsTable tbody');
    tbody.empty();

    products.forEach(p => {
        tbody.append(`
            <tr>
                <td>${p.sku}</td>
                <td>${p.item}</td>
                <td>${p.stock}</td>
                <td>
                    <button class="btn btn-sm btn-success" onclick="inventoryIn(${p.id})">IN</button>
                    <button class="btn btn-sm btn-danger" onclick="inventoryOut(${p.id})">OUT</button>
                    <button class="btn btn-sm btn-warning" onclick="inventoryAdjust(${p.id})">ADJUST</button>
                </td>
            </tr>
        `);
    });
}

async function inventoryIn(id) {
    const qty = prompt('Quantity to add?');
    const notes = prompt('Notes?');
    if (!qty) return;
    await fetch('/api/movements/in', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ product_id: id, quantity: parseInt(qty), notes })
    });
    loadProducts();
}

async function inventoryOut(id) {
    const qty = prompt('Quantity to remove?');
    const notes = prompt('Notes?');
    if (!qty) return;
    await fetch('/api/movements/out', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ product_id: id, quantity: parseInt(qty), notes })
    });
    loadProducts();
}

async function inventoryAdjust(id) {
    const qty = prompt('Adjustment quantity (+/-)?');
    const notes = prompt('Notes?');
    if (!qty) return;
    await fetch('/api/movements/adjust', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ product_id: id, quantity: parseInt(qty), notes })
    });
    loadProducts();
}

// Initial load
$(document).ready(loadProducts);
const API_BASE = "/api";

async function loadStock() {
  const response = await fetch(`${API_BASE}/stock`);
  const data = await response.json();

  const tbody = document.querySelector("#inventoryTable tbody");
  tbody.innerHTML = "";

  data.forEach(p => {
    const row = document.createElement("tr");

row.innerHTML = `
  <td>${p.sku}</td>
  <td>${p.item}</td>
  <td>${p.vendor}</td>
  <td>${p.color}</td>
  <td>${p.stock}</td>
  <td>${p.whs_location}</td>
 <td>
  <button class="btn btn-info btn-sm" onclick="viewProduct(${p.id})">VIEW</button>
  <button class="btn btn-success btn-sm" onclick="moveIn(${p.id})">IN</button>
  <button class="btn btn-danger btn-sm" onclick="moveOut(${p.id})">OUT</button>
  <button class="btn btn-warning btn-sm" onclick="adjust(${p.id})">ADJUST</button>
</td>
;



    tbody.appendChild(row);
  });
}

async function moveIn(id) {
  const qty = Number(prompt("Quantity IN:"));
  if (!qty) return;

  await fetch(`${API_BASE}/movements/in`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: id, quantity: qty })
  });

  loadStock();
}

async function moveOut(id) {
  const qty = Number(prompt("Quantity OUT:"));
  if (!qty) return;

  await fetch(`${API_BASE}/movements/out`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: id, quantity: qty })
  });

  loadStock();
}

async function adjust(id) {
  const qty = Number(prompt("Adjustment (+/-):"));
  if (!qty) return;

  await fetch(`${API_BASE}/movements/adjust`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: id, quantity: qty })
  });

  loadStock();
}

loadStock();
function viewProduct(productId) {
  fetch(`/api/product/${productId}`)
    .then(res => res.json())
    .then(data => {
      alert(
        `SKU: ${data.sku}\n` +
        `Item: ${data.item}\n` +
        `Vendor: ${data.vendor}\n` +
        `Color: ${data.color}\n` +
        `Cost: ${data.cost}\n` +
        `Sale Price: ${data.sale_price}\n` +
        `Warehouse: ${data.whs_location}`
      );
    });
}

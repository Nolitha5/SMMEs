/* ============================================================
   Inventory Management Agent — Frontend Application
   All data fetched from existing FastAPI backend APIs.
   No hard-coded numbers. No fake data.
   ============================================================ */

"use strict";

// ── API base (same origin) ──────────────────────────────────
const API = "";   // relative — same host:port

async function get(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`HTTP ${r.status} from ${path}`);
  return r.json();
}

// ── Navigation ─────────────────────────────────────────────
const pages = ["dashboard", "stock", "reorders", "risks", "exceptions", "products"];

function navigate(pageId) {
  pages.forEach(p => {
    const el = document.getElementById("page-" + p);
    const nav = document.querySelector(`[data-page="${p}"]`);
    if (el)  el.classList.toggle("active", p === pageId);
    if (nav) nav.classList.toggle("active",  p === pageId);
  });
  document.getElementById("topbar-title").textContent = pageTitles[pageId] || pageId;
  pageLoaders[pageId]?.();

  // close sidebar on narrow screens
  document.querySelector(".sidebar")?.classList.remove("open");
}

const pageTitles = {
  dashboard:  "Dashboard",
  stock:      "Stock Inventory",
  reorders:   "Reorder Management",
  risks:      "Stock Risks",
  exceptions: "Inventory Exceptions",
  products:   "Products",
};

// ── Helpers ─────────────────────────────────────────────────
function badge(text, cls) {
  return `<span class="badge badge-${cls}">${text}</span>`;
}

function severityBadge(sev) {
  const map = { HIGH: "danger", MEDIUM: "warning", LOW: "success", CRITICAL: "danger" };
  return badge(sev, map[sev?.toUpperCase()] || "neutral");
}

function statusBadge(status, stockStatus) {
  const s = (status || stockStatus || "").toUpperCase();
  const cls = s === "OUT_OF_STOCK" || s === "CRITICAL" ? "danger"
            : s === "LOW"          || s === "REORDER"   ? "warning"
            : s === "OK"           || s === "HEALTHY"   ? "success"
            : "neutral";
  const label = s.replace(/_/g, " ");
  return badge(label, cls);
}

function fmt(n) {
  if (n == null || n === "" || n === undefined) return "—";
  const num = parseFloat(n);
  if (isNaN(num)) return n;
  return Number.isInteger(num) ? num.toLocaleString() : num.toFixed(1);
}

function fmtDate(s) {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return s; }
}

function excTypeFriendly(t) {
  const m = {
    NEGATIVE_STOCK:                 "Negative Stock",
    LARGE_STOCK_ADJUSTMENT:         "Large Adjustment",
    MOVEMENT_SNAPSHOT_MISMATCH:     "Movement / Snapshot Mismatch",
    RECEIPT_STOCK_MISMATCH:         "Receipt / Stock Mismatch",
    DUPLICATE_SUSPICIOUS_MOVEMENT:  "Suspicious Movement",
  };
  return m[t] || t;
}

function riskTypeFriendly(t) {
  const m = {
    EXPIRY_RISK:  "Expiry Risk",
    SLOW_STOCK:   "Slow Stock",
    DEAD_STOCK:   "Dead Stock",
    EXCESS_STOCK: "Excess Stock",
  };
  return m[t] || t?.replace(/_/g, " ") || "—";
}

function riskTypeClass(t) {
  return { EXPIRY_RISK: "risk-expiry", SLOW_STOCK: "risk-slow", DEAD_STOCK: "risk-dead", EXCESS_STOCK: "risk-excess" }[t] || "";
}

function showLoading(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Loading…</p></div>`;
}

function showError(containerId, msg) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div><p>${msg}</p></div>`;
}

function showEmpty(containerId, msg) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><p>${msg}</p></div>`;
}

// ── Global product cache (for fast product name lookup) ─────
let _products = [];
async function ensureProducts() {
  if (_products.length) return _products;
  const d = await get("/products/");
  _products = d.products || [];
  return _products;
}
function productName(id) {
  const p = _products.find(x => x.product_id?.toUpperCase() === id?.toUpperCase());
  return p ? p.product_name : id;
}

// ══════════════════════════════════════════════════════════════
// PAGE: DASHBOARD
// ══════════════════════════════════════════════════════════════
let _dashLoaded = false;
async function loadDashboard() {
  if (_dashLoaded) return;
  _dashLoaded = true;
  await ensureProducts();

  const kpiEl      = document.getElementById("dash-kpis");
  const attEl      = document.getElementById("dash-attention");
  kpiEl.innerHTML  = `<div class="loading-state"><div class="spinner"></div></div>`;
  attEl.innerHTML  = kpiEl.innerHTML;

  try {
    const [stockData, alertData, reorderData, riskData, excData] = await Promise.allSettled([
      get("/stock/"),
      get("/alerts/summary"),
      get("/reorders/"),
      get("/api/stock-risk/"),
      get("/api/inventory-exceptions/"),
    ]);

    const stock   = stockData.status   === "fulfilled" ? stockData.value   : null;
    const alerts  = alertData.status   === "fulfilled" ? alertData.value   : null;
    const reorders= reorderData.status === "fulfilled" ? reorderData.value : null;
    const risks   = riskData.status    === "fulfilled" ? riskData.value    : null;
    const exc     = excData.status     === "fulfilled" ? excData.value     : null;

    // ── KPIs ──
    const items         = stock?.items || [];
    const totalProds    = _products.length;
    const healthy       = items.filter(i => i.stock_status === "OK" || i.stock_status === "HEALTHY").length;
    const critical      = items.filter(i => ["OUT_OF_STOCK","CRITICAL","LOW"].includes(i.stock_status)).length;
    const reorderNeeded = reorders?.reorder_needed_count ?? 0;
    const totalRisks    = risks?.total_alerts ?? 0;
    const totalExc      = exc?.total_exceptions ?? 0;

    kpiEl.innerHTML = `
      <div class="kpi-card kpi-neutral">
        <div class="kpi-icon">📦</div>
        <div class="kpi-value">${totalProds}</div>
        <div class="kpi-label">Total Products</div>
      </div>
      <div class="kpi-card kpi-success">
        <div class="kpi-icon">✅</div>
        <div class="kpi-value">${healthy}</div>
        <div class="kpi-label">Healthy Stock</div>
      </div>
      <div class="kpi-card kpi-danger">
        <div class="kpi-icon">🔴</div>
        <div class="kpi-value">${critical}</div>
        <div class="kpi-label">Critical / Low Stock</div>
      </div>
      <div class="kpi-card kpi-warning">
        <div class="kpi-icon">🔄</div>
        <div class="kpi-value">${reorderNeeded}</div>
        <div class="kpi-label">Reorders Needed</div>
      </div>
      <div class="kpi-card kpi-info">
        <div class="kpi-icon">⚠️</div>
        <div class="kpi-value">${totalRisks}</div>
        <div class="kpi-label">Stock Risks</div>
      </div>
      <div class="kpi-card kpi-purple">
        <div class="kpi-icon">🚨</div>
        <div class="kpi-value">${totalExc}</div>
        <div class="kpi-label">Exceptions</div>
      </div>
    `;

    // ── Attention Required ──
    const items_att = [];

    // Critical/OOS stock
    const critItems = items.filter(i => i.stock_status === "OUT_OF_STOCK");
    if (critItems.length) items_att.push({
      icon: "🔴", sev: "sev-high",
      title: `${critItems.length} product${critItems.length>1?"s":""} out of stock`,
      sub: critItems.slice(0,3).map(i => i.product_name || i.product_id).join(", ") + (critItems.length>3?" …":""),
      action: () => navigate("stock"),
    });

    const lowItems = items.filter(i => i.stock_status === "LOW" || i.stock_status === "CRITICAL");
    if (lowItems.length) items_att.push({
      icon: "🟡", sev: "sev-medium",
      title: `${lowItems.length} product${lowItems.length>1?"s":""} with low/critical stock`,
      sub: lowItems.slice(0,3).map(i => i.product_name || i.product_id).join(", ") + (lowItems.length>3?" …":""),
      action: () => navigate("stock"),
    });

    // Reorders
    if (reorderNeeded > 0) items_att.push({
      icon: "🔄", sev: "sev-medium",
      title: `${reorderNeeded} product${reorderNeeded>1?"s":""} need reordering`,
      sub: "Review the Reorders page for suggested quantities.",
      action: () => navigate("reorders"),
    });

    // High-severity risks
    const highRisks = (risks?.alerts || []).filter(a => a.severity === "HIGH");
    if (highRisks.length) items_att.push({
      icon: "⚠️", sev: "sev-high",
      title: `${highRisks.length} high-severity stock risk${highRisks.length>1?"s":""}`,
      sub: highRisks.slice(0,3).map(a => productName(a.product_id)).join(", ") + (highRisks.length>3?" …":""),
      action: () => navigate("risks"),
    });

    // High exceptions
    const highExc = (exc?.exceptions || []).filter(e => e.severity === "HIGH");
    if (highExc.length) items_att.push({
      icon: "🚨", sev: "sev-high",
      title: `${highExc.length} high-severity inventory exception${highExc.length>1?"s":""}`,
      sub: highExc.slice(0,3).map(e => productName(e.product_id)).join(", ") + (highExc.length>3?" …":""),
      action: () => navigate("exceptions"),
    });

    if (items_att.length === 0) {
      attEl.innerHTML = `<div class="empty-state"><div class="empty-icon">🎉</div><p>No immediate issues detected.</p></div>`;
    } else {
      attEl.innerHTML = `<div class="attention-grid">${items_att.map(a =>
        `<div class="attention-item ${a.sev}" onclick='(${a.action.toString()})()' style="cursor:pointer">
          <div class="att-icon">${a.icon}</div>
          <div class="att-body">
            <div class="att-title">${a.title}</div>
            <div class="att-sub">${a.sub}</div>
          </div>
        </div>`).join("")}</div>`;
    }

  } catch(e) {
    showError("dash-kpis", "Could not load dashboard data. Is the server running?");
    attEl.innerHTML = "";
  }
}

// ══════════════════════════════════════════════════════════════
// PAGE: STOCK
// ══════════════════════════════════════════════════════════════
let _stockData = [];
let _stockCategories = [];
let _stockFilter = "";
let _stockCatFilter = "";
let _stockStatusFilter = "";
let _stockSortCol = "";
let _stockSortDir = 1;

async function loadStock() {
  showLoading("stock-table-body");
  try {
    await ensureProducts();
    const d = await get("/stock/");
    _stockData = d.items || [];
    _stockCategories = [...new Set(_stockData.map(i => i.category).filter(Boolean))].sort();
    renderCatFilter();
    renderStockTable();
  } catch(e) {
    showError("stock-table-body", "Unable to load stock data.");
  }
}

function renderCatFilter() {
  const sel = document.getElementById("stock-cat-filter");
  if (!sel) return;
  sel.innerHTML = `<option value="">All Categories</option>` +
    _stockCategories.map(c => `<option value="${c}">${c}</option>`).join("");
}

function renderStockTable() {
  const tbody = document.getElementById("stock-table-body");
  if (!tbody) return;

  let data = _stockData.filter(item => {
    const q = _stockFilter.toLowerCase();
    const nameMatch = (item.product_name||item.product_id||"").toLowerCase().includes(q);
    const catMatch  = !_stockCatFilter  || item.category === _stockCatFilter;
    const statMatch = !_stockStatusFilter || item.stock_status === _stockStatusFilter;
    return (nameMatch) && catMatch && statMatch;
  });

  if (_stockSortCol) {
    data = [...data].sort((a,b) => {
      const av = a[_stockSortCol] ?? 0, bv = b[_stockSortCol] ?? 0;
      return (av < bv ? -1 : av > bv ? 1 : 0) * _stockSortDir;
    });
  }

  document.getElementById("stock-count").textContent = `${data.length} product${data.length!==1?"s":""}`;

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="no-data-message">No products match the current filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(item => {
    const avail = item.available_stock ?? (item.stock_on_hand - (item.reserved||0) - (item.damaged||0));
    const maxSoh = Math.max(..._stockData.map(x => x.stock_on_hand || 0), 1);
    const pct    = Math.min(100, Math.round((item.stock_on_hand / maxSoh) * 100));
    const barColor = item.stock_status === "OUT_OF_STOCK" ? "var(--color-danger)"
                   : item.stock_status === "LOW" || item.stock_status === "CRITICAL" ? "var(--color-warning)"
                   : "var(--color-success)";
    return `<tr onclick="openProductModal('${item.product_id}')">
      <td>
        <div class="product-name">${item.product_name || item.product_id}</div>
        <div class="product-id">${item.product_id}</div>
      </td>
      <td>${item.category || "—"}</td>
      <td>
        <div class="stock-bar-wrap">
          <span class="fw-600">${fmt(item.stock_on_hand)}</span>
          <div class="stock-bar"><div class="stock-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
        </div>
      </td>
      <td>${fmt(avail)}</td>
      <td>${fmt(item.in_transit)}</td>
      <td>${statusBadge(item.stock_status)}</td>
      <td>${item.days_of_cover != null ? fmt(item.days_of_cover) + " d" : "—"}</td>
      <td class="text-right" style="font-size:18px;color:var(--color-text-muted)">›</td>
    </tr>`;
  }).join("");
}

// ══════════════════════════════════════════════════════════════
// PAGE: REORDERS
// ══════════════════════════════════════════════════════════════
let _reorderLoaded = false;
async function loadReorders() {
  if (_reorderLoaded) return;
  _reorderLoaded = true;
  showLoading("reorder-table-body");
  try {
    await ensureProducts();
    const d = await get("/reorders/");
    const decisions = d.decisions || [];
    renderReorderTable(decisions);
  } catch(e) {
    showError("reorder-table-body", "Unable to load reorder data.");
  }
}

function renderReorderTable(decisions) {
  const tbody = document.getElementById("reorder-table-body");
  if (!tbody) return;

  const urgentFirst = [...decisions].sort((a,b) => {
    if (a.reorder_needed && !b.reorder_needed) return -1;
    if (!a.reorder_needed && b.reorder_needed) return 1;
    return (a.inventory_position ?? 999) - (b.inventory_position ?? 999);
  });

  const needed   = urgentFirst.filter(d => d.reorder_needed);
  const ok       = urgentFirst.filter(d => !d.reorder_needed);
  document.getElementById("reorder-urgent-count").textContent = needed.length;

  const rows = (arr, isNeeded) => arr.map(d => {
    const statusHtml = isNeeded
      ? `<span class="badge badge-danger">🔴 Reorder Required</span>`
      : `<span class="badge badge-success">🟢 Stock Sufficient</span>`;
    return `<tr onclick="openProductModal('${d.product_id}')">
      <td>
        <div class="product-name">${d.product_name || productName(d.product_id)}</div>
        <div class="product-id">${d.product_id}</div>
      </td>
      <td>${fmt(d.available_stock)}</td>
      <td>${fmt(d.inventory_position)}</td>
      <td>${fmt(d.reorder_point)}</td>
      <td class="fw-600">${isNeeded ? fmt(d.suggested_reorder_qty) : "—"}</td>
      <td>${d.lead_time_days != null ? d.lead_time_days + " d" : "—"}</td>
      <td>${statusHtml}</td>
    </tr>`;
  }).join("");

  tbody.innerHTML = rows(needed, true) + rows(ok, false);
}

// ══════════════════════════════════════════════════════════════
// PAGE: STOCK RISKS (I4)
// ══════════════════════════════════════════════════════════════
let _riskLoaded = false;
async function loadRisks() {
  if (_riskLoaded) return;
  _riskLoaded = true;
  showLoading("risk-table-body");
  try {
    await ensureProducts();
    const d = await get("/api/stock-risk/");
    renderRiskTable(d.alerts || []);
  } catch(e) {
    showError("risk-table-body", "Unable to load stock risk data.");
  }
}

function renderRiskTable(alerts) {
  const tbody = document.getElementById("risk-table-body");
  if (!tbody) return;
  if (!alerts.length) { showEmpty("risk-table-body", "No stock risks detected."); return; }

  const sevOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const sorted = [...alerts].sort((a,b) => (sevOrder[a.severity]||9) - (sevOrder[b.severity]||9));

  document.getElementById("risk-count").textContent = sorted.length;

  tbody.innerHTML = sorted.map(a => `
    <tr onclick="openProductModal('${a.product_id}')">
      <td>
        <div class="product-name">${a.product_name || productName(a.product_id)}</div>
        <div class="product-id">${a.product_id}</div>
      </td>
      <td><span class="${riskTypeClass(a.risk_type)}">${riskTypeFriendly(a.risk_type)}</span></td>
      <td>${severityBadge(a.severity)}</td>
      <td>${fmt(a.available_stock)}</td>
      <td>${a.sales_velocity != null ? fmt(a.sales_velocity) + " /d" : "—"}</td>
      <td>${a.days_of_cover != null ? fmt(a.days_of_cover) + " d" : "—"}</td>
      <td>${a.days_to_expiry != null ? fmt(a.days_to_expiry) + " d" : "—"}</td>
      <td style="max-width:260px;font-size:12.5px;color:var(--color-text-muted)">${a.reason || a.rationale || "—"}</td>
    </tr>`).join("");
}

// ══════════════════════════════════════════════════════════════
// PAGE: EXCEPTIONS (I5)
// ══════════════════════════════════════════════════════════════
let _excLoaded = false;
async function loadExceptions() {
  if (_excLoaded) return;
  _excLoaded = true;
  showLoading("exc-table-body");
  try {
    await ensureProducts();
    const d = await get("/api/inventory-exceptions/");
    renderExcTable(d.exceptions || []);
  } catch(e) {
    showError("exc-table-body", "Unable to load exception data.");
  }
}

function renderExcTable(excs) {
  const tbody = document.getElementById("exc-table-body");
  if (!tbody) return;
  if (!excs.length) { showEmpty("exc-table-body", "No inventory exceptions detected."); return; }

  const sevOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const sorted = [...excs].sort((a,b) => (sevOrder[a.severity]||9) - (sevOrder[b.severity]||9));

  document.getElementById("exc-count").textContent = sorted.length;

  tbody.innerHTML = sorted.map(e => `
    <tr onclick="openProductModal('${e.product_id}')">
      <td>
        <div class="product-name">${productName(e.product_id)}</div>
        <div class="product-id">${e.product_id}</div>
      </td>
      <td>${excTypeFriendly(e.exception_type)}</td>
      <td>${severityBadge(e.severity)}</td>
      <td><span class="badge badge-warning">${e.status || "OPEN"}</span></td>
      <td style="max-width:260px;font-size:12.5px;color:var(--color-text-muted)">${e.reason || e.message || "—"}</td>
      <td class="text-muted" style="white-space:nowrap">${fmtDate(e.generated_at)}</td>
    </tr>`).join("");
}

// ══════════════════════════════════════════════════════════════
// PAGE: PRODUCTS
// ══════════════════════════════════════════════════════════════
let _prodFilter = "";
async function loadProducts() {
  showLoading("products-table-body");
  try {
    await ensureProducts();
    renderProductsTable();
  } catch(e) {
    showError("products-table-body", "Unable to load products.");
  }
}

function renderProductsTable() {
  const tbody = document.getElementById("products-table-body");
  if (!tbody) return;
  const q = _prodFilter.toLowerCase();
  const data = _products.filter(p =>
    (p.product_name||"").toLowerCase().includes(q) ||
    (p.product_id||"").toLowerCase().includes(q) ||
    (p.category||"").toLowerCase().includes(q)
  );
  document.getElementById("products-count").textContent = `${data.length} product${data.length!==1?"s":""}`;
  if (!data.length) { tbody.innerHTML = `<tr><td colspan="6" class="no-data-message">No products match.</td></tr>`; return; }
  tbody.innerHTML = data.map(p => `
    <tr onclick="openProductModal('${p.product_id}')">
      <td class="fw-600">${p.product_id}</td>
      <td><div class="product-name">${p.product_name || "—"}</div></td>
      <td>${p.category || "—"}</td>
      <td>${p.supplier_id || "—"}</td>
      <td>${p.shelf_life_days != null ? p.shelf_life_days + " d" : "—"}</td>
      <td class="text-right" style="font-size:18px;color:var(--color-text-muted)">›</td>
    </tr>`).join("");
}

// ══════════════════════════════════════════════════════════════
// PRODUCT DETAIL MODAL
// ══════════════════════════════════════════════════════════════
async function openProductModal(productId) {
  const pid = productId.toUpperCase();
  const overlay = document.getElementById("product-modal-overlay");
  const title   = document.getElementById("modal-product-title");
  const body    = document.getElementById("modal-product-body");

  title.textContent = "Loading…";
  body.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Loading product details…</p></div>`;
  overlay.classList.add("open");
  document.body.style.overflow = "hidden";

  try {
    // fetch all in parallel; individual failures handled gracefully
    const [prod, stock, reorder, safety, risks, excs] = await Promise.allSettled([
      get(`/products/${pid}`),
      get(`/stock/${pid}`),
      get(`/reorders/${pid}`),
      get(`/api/safety-stock/${pid}`),
      get(`/api/stock-risk/${pid}`),
      get(`/api/inventory-exceptions/${pid}`),
    ]);

    const p   = prod.status   === "fulfilled" ? prod.value   : null;
    const s   = stock.status  === "fulfilled" ? stock.value  : null;
    const r2  = reorder.status=== "fulfilled" ? reorder.value: null;
    const r3  = safety.status === "fulfilled" ? safety.value : null;
    const r4  = risks.status  === "fulfilled" ? risks.value  : null;
    const r5  = excs.status   === "fulfilled" ? excs.value   : null;

    const snap = s?.snapshots?.[0];  // latest snapshot is first (monitor sorts desc)

    title.textContent = p?.product_name || pid;

    let html = "";

    // ── Product info ──
    html += `<div class="detail-section">
      <div class="detail-section-title">Product Information</div>
      <div class="detail-grid">
        <div class="detail-field"><div class="field-label">Product ID</div><div class="field-value">${pid}</div></div>
        <div class="detail-field"><div class="field-label">Category</div><div class="field-value">${p?.category || "—"}</div></div>
        <div class="detail-field"><div class="field-label">Supplier</div><div class="field-value">${p?.supplier_id || "—"}</div></div>
        <div class="detail-field"><div class="field-label">Unit</div><div class="field-value">${p?.unit || "—"}</div></div>
        <div class="detail-field"><div class="field-label">Shelf Life</div><div class="field-value">${p?.shelf_life_days != null ? p.shelf_life_days+" days" : "—"}</div></div>
        <div class="detail-field"><div class="field-label">Reorder Level</div><div class="field-value">${p?.reorder_level != null ? p.reorder_level : "—"}</div></div>
      </div>
    </div>`;

    // ── Stock position ──
    if (snap) {
      const avail = snap.available_stock ?? (snap.stock_on_hand - (snap.reserved||0) - (snap.damaged||0));
      const availClass = avail < 0 ? "value-danger" : avail < 5 ? "value-warning" : "";
      html += `<div class="detail-section">
        <div class="detail-section-title">📦 Stock Position (I1 — Stock Monitor)</div>
        <div class="detail-grid">
          <div class="detail-field"><div class="field-label">Stock On Hand</div><div class="field-value">${fmt(snap.stock_on_hand)}</div></div>
          <div class="detail-field"><div class="field-label">Available</div><div class="field-value ${availClass}">${fmt(avail)}</div></div>
          <div class="detail-field"><div class="field-label">Reserved</div><div class="field-value">${fmt(snap.reserved)}</div></div>
          <div class="detail-field"><div class="field-label">Damaged</div><div class="field-value">${fmt(snap.damaged)}</div></div>
          <div class="detail-field"><div class="field-label">In Transit</div><div class="field-value">${fmt(snap.in_transit)}</div></div>
          <div class="detail-field"><div class="field-label">Stock Status</div><div class="field-value">${statusBadge(snap.stock_status)}</div></div>
          <div class="detail-field"><div class="field-label">Days of Cover</div><div class="field-value">${snap.days_of_cover != null ? fmt(snap.days_of_cover)+" d" : "—"}</div></div>
        </div>
      </div>`;
    } else {
      html += `<div class="detail-section"><div class="detail-section-title">📦 Stock Position</div><p class="text-muted">No snapshot data available.</p></div>`;
    }

    // ── Reorder (I2) ──
    html += `<div class="detail-section">
      <div class="detail-section-title">🔄 Reorder Information (I2 — Reorder Point)</div>`;
    if (r2) {
      const needBadge = r2.reorder_needed
        ? `<span class="badge badge-danger">Reorder Required</span>`
        : `<span class="badge badge-success">Stock Sufficient</span>`;
      html += `<div class="detail-grid">
        <div class="detail-field"><div class="field-label">Decision</div><div class="field-value">${needBadge}</div></div>
        <div class="detail-field"><div class="field-label">Inventory Position</div><div class="field-value">${fmt(r2.inventory_position)}</div></div>
        <div class="detail-field"><div class="field-label">Reorder Point</div><div class="field-value">${fmt(r2.reorder_point)}</div></div>
        <div class="detail-field"><div class="field-label">Suggested Qty</div><div class="field-value">${r2.reorder_needed ? fmt(r2.suggested_reorder_qty) : "—"}</div></div>
        <div class="detail-field"><div class="field-label">Lead Time</div><div class="field-value">${r2.lead_time_days != null ? r2.lead_time_days+" d" : "—"}</div></div>
        <div class="detail-field"><div class="field-label">Avg Daily Demand</div><div class="field-value">${fmt(r2.avg_daily_demand)}</div></div>
      </div>`;
      if (r2.rationale) html += `<p style="margin-top:10px;font-size:12.5px;color:var(--color-text-muted)">${r2.rationale}</p>`;
    } else {
      html += `<p class="text-muted">Reorder data not available for this product.</p>`;
    }
    html += `</div>`;

    // ── Safety stock (I3) ──
    html += `<div class="detail-section">
      <div class="detail-section-title">🛡️ Safety Stock (I3 — Safety Stock Agent)</div>`;
    if (r3 && r3.safety_stock != null) {
      html += `<div class="detail-grid">
        <div class="detail-field"><div class="field-label">Safety Stock</div><div class="field-value">${fmt(r3.safety_stock)}</div></div>
        <div class="detail-field"><div class="field-label">Max Lead Time</div><div class="field-value">${r3.max_lead_time_days != null ? r3.max_lead_time_days+" d" : "—"}</div></div>
        <div class="detail-field"><div class="field-label">Avg Lead Time</div><div class="field-value">${r3.avg_lead_time_days != null ? r3.avg_lead_time_days+" d" : "—"}</div></div>
        <div class="detail-field"><div class="field-label">Demand StdDev</div><div class="field-value">${fmt(r3.demand_std_dev)}</div></div>
        <div class="detail-field"><div class="field-label">Formula</div><div class="field-value">${r3.formula || "—"}</div></div>
      </div>`;
    } else {
      html += `<p class="text-muted">Safety stock data not available for this product.</p>`;
    }
    html += `</div>`;

    // ── Stock Risks (I4) ──
    html += `<div class="detail-section">
      <div class="detail-section-title">⚠️ Stock Risks (I4 — Expiry &amp; Slow Stock)</div>`;
    const r4alerts = r4?.alerts || [];
    if (r4alerts.length) {
      html += `<table class="mini-table">
        <thead><tr><th>Risk Type</th><th>Severity</th><th>Days of Cover</th><th>Days to Expiry</th><th>Reason</th></tr></thead>
        <tbody>${r4alerts.map(a => `<tr>
          <td class="${riskTypeClass(a.risk_type)}">${riskTypeFriendly(a.risk_type)}</td>
          <td>${severityBadge(a.severity)}</td>
          <td>${a.days_of_cover != null ? fmt(a.days_of_cover)+" d" : "—"}</td>
          <td>${a.days_to_expiry != null ? fmt(a.days_to_expiry)+" d" : "—"}</td>
          <td style="font-size:12px">${a.reason || "—"}</td>
        </tr>`).join("")}</tbody>
      </table>`;
    } else {
      html += `<p class="text-muted">No stock risks for this product.</p>`;
    }
    html += `</div>`;

    // ── Exceptions (I5) ──
    html += `<div class="detail-section">
      <div class="detail-section-title">🚨 Inventory Exceptions (I5 — Exception Agent)</div>`;
    const excList = r5?.exceptions || [];
    if (excList.length) {
      html += `<table class="mini-table">
        <thead><tr><th>Exception</th><th>Severity</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>${excList.map(e => `<tr>
          <td>${excTypeFriendly(e.exception_type)}</td>
          <td>${severityBadge(e.severity)}</td>
          <td><span class="badge badge-warning">${e.status || "OPEN"}</span></td>
          <td style="font-size:12px">${e.reason || e.message || "—"}</td>
        </tr>`).join("")}</tbody>
      </table>`;
    } else {
      html += `<p class="text-muted">No exceptions for this product.</p>`;
    }
    html += `</div>`;

    body.innerHTML = html;

  } catch(e) {
    body.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div><p>Could not load product details.<br><small>${e.message}</small></p></div>`;
  }
}

function closeProductModal() {
  document.getElementById("product-modal-overlay").classList.remove("open");
  document.body.style.overflow = "";
}

// ══════════════════════════════════════════════════════════════
// PAGE LOADERS MAP
// ══════════════════════════════════════════════════════════════
const pageLoaders = {
  dashboard:  loadDashboard,
  stock:      loadStock,
  reorders:   loadReorders,
  risks:      loadRisks,
  exceptions: loadExceptions,
  products:   loadProducts,
};

// ══════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {

  // Nav clicks
  document.querySelectorAll("[data-page]").forEach(el =>
    el.addEventListener("click", () => navigate(el.dataset.page))
  );

  // Hamburger
  const hamburger = document.getElementById("hamburger");
  hamburger?.addEventListener("click", () =>
    document.querySelector(".sidebar")?.classList.toggle("open")
  );

  // Modal close
  document.getElementById("modal-close-btn")?.addEventListener("click", closeProductModal);
  document.getElementById("product-modal-overlay")?.addEventListener("click", e => {
    if (e.target === e.currentTarget) closeProductModal();
  });

  // Stock search & filters
  document.getElementById("stock-search")?.addEventListener("input", e => {
    _stockFilter = e.target.value;
    renderStockTable();
  });
  document.getElementById("stock-status-filter")?.addEventListener("change", e => {
    _stockStatusFilter = e.target.value;
    renderStockTable();
  });
  document.getElementById("stock-cat-filter")?.addEventListener("change", e => {
    _stockCatFilter = e.target.value;
    renderStockTable();
  });

  // Sort on stock table headers
  document.querySelectorAll("#stock-thead th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      if (_stockSortCol === th.dataset.sort) _stockSortDir *= -1;
      else { _stockSortCol = th.dataset.sort; _stockSortDir = 1; }
      renderStockTable();
    });
  });

  // Products search
  document.getElementById("products-search")?.addEventListener("input", e => {
    _prodFilter = e.target.value;
    renderProductsTable();
  });

  // Start on dashboard
  navigate("dashboard");
});

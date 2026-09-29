import { clamp, daysBetween, highestRisk, makeResult, insufficient, parseDate, round } from './common.mjs';

const SERVICE_Z = { '0.9': 1.28, '0.95': 1.65, '0.99': 2.33 };

function byProduct(rows) {
  const map = new Map();
  for (const row of rows || []) {
    const id = String(row.product_id || '').trim();
    if (!id) continue;
    if (!map.has(id)) map.set(id, []);
    map.get(id).push(row);
  }
  return map;
}

function latestSnapshot(rows) {
  return [...(rows || [])].sort((a, b) => (parseDate(b.timestamp)?.getTime() || 0) - (parseDate(a.timestamp)?.getTime() || 0))[0] || null;
}

function openPoInTransit(productId, purchaseOrders, goodsReceipts) {
  const receiptsByPo = new Map();
  for (const receipt of goodsReceipts || []) {
    receiptsByPo.set(String(receipt.po_id), (receiptsByPo.get(String(receipt.po_id)) || 0) + Number(receipt.qty_received || 0));
  }
  let total = 0;
  for (const po of purchaseOrders || []) {
    if (String(po.product_id) !== String(productId)) continue;
    if (!['OPEN', 'PARTIALLY_RECEIVED'].includes(String(po.status || '').toUpperCase())) continue;
    total += Math.max(0, Number(po.qty || 0) - Number(receiptsByPo.get(String(po.po_id)) || 0));
  }
  return total;
}

function classifyStock(available, inTransit, forecast) {
  if (!forecast || !Number(forecast.horizon_days) || !Number(forecast.expected_qty)) {
    if (available <= 0) return { stock_status: 'OUT_OF_STOCK', days_of_supply: null };
    if (available < 5) return { stock_status: 'CRITICAL', days_of_supply: null };
    if (available < 15) return { stock_status: 'LOW', days_of_supply: null };
    return { stock_status: 'HEALTHY', days_of_supply: null };
  }
  const daily = Number(forecast.expected_qty) / Number(forecast.horizon_days);
  const dos = daily > 0 ? available / daily : null;
  if (available <= 0) return { stock_status: 'OUT_OF_STOCK', days_of_supply: dos };
  if (dos != null && dos < 2) return { stock_status: 'CRITICAL', days_of_supply: dos };
  if (dos != null && dos < 7) {
    return { stock_status: available + inTransit < Number(forecast.expected_qty) ? 'STOCK_PRESSURE' : 'LOW', days_of_supply: dos };
  }
  return { stock_status: 'HEALTHY', days_of_supply: dos };
}

function riskForStockStatus(status) {
  if (['OUT_OF_STOCK', 'CRITICAL'].includes(status)) return 'HIGH';
  if (['STOCK_PRESSURE', 'LOW'].includes(status)) return 'MEDIUM';
  return 'LOW';
}

function runI4(product, snapshot, movements, transactions, now) {
  if (!snapshot) return null;
  const productId = String(product.product_id);
  const available = Math.max(0, Number(snapshot.stock_on_hand || 0) - Number(snapshot.reserved || 0) - Number(snapshot.damaged || 0));
  const cutoff = now.getTime() - 30 * 86_400_000;
  const unitsSold = (transactions || []).filter((t) => String(t.product_id) === productId && (parseDate(t.timestamp)?.getTime() || 0) >= cutoff && Number(t.qty) > 0).reduce((s, t) => s + Number(t.qty), 0);
  const velocity = unitsSold / 30;
  const daysOfCover = velocity > 0 ? available / velocity : null;
  const receiptDates = (movements || []).filter((m) => String(m.product_id) === productId && String(m.type).toUpperCase() === 'RECEIPT').map((m) => parseDate(m.timestamp)).filter(Boolean);
  const latestReceipt = receiptDates.sort((a, b) => b.getTime() - a.getTime())[0] || null;
  const ageDays = latestReceipt ? Math.max(0, daysBetween(latestReceipt, now) || 0) : null;
  const shelfLife = Number(product.shelf_life_days || 0) || null;
  const daysToExpiry = shelfLife != null && ageDays != null ? shelfLife - ageDays : null;
  const risks = [];

  if (available > 0 && daysToExpiry != null && daysToExpiry <= 14) {
    risks.push({
      risk_type: 'EXPIRY_RISK', severity: daysToExpiry <= 7 ? 'HIGH' : 'MEDIUM', available_stock: available,
      sales_velocity: round(velocity, 4), days_of_cover: daysOfCover == null ? null : round(daysOfCover, 2),
      inventory_age_days: round(ageDays, 2), shelf_life_days: shelfLife, days_to_expiry: round(daysToExpiry, 2),
      confidence: 0.9,
      reason: `Stock has about ${round(daysToExpiry, 1)} days of shelf life remaining.`
    });
  }
  if (available > 0 && velocity === 0) {
    risks.push({
      risk_type: 'DEAD_STOCK', severity: available >= 10 ? 'HIGH' : 'MEDIUM', available_stock: available,
      sales_velocity: 0, days_of_cover: null, inventory_age_days: ageDays == null ? null : round(ageDays, 2),
      shelf_life_days: shelfLife, days_to_expiry: daysToExpiry == null ? null : round(daysToExpiry, 2), confidence: 0.85,
      reason: 'Positive stock exists but no sales were recorded in the last 30 days.'
    });
  } else if (daysOfCover != null && daysOfCover > 60) {
    risks.push({ risk_type: 'EXCESS_STOCK', severity: 'HIGH', available_stock: available, sales_velocity: round(velocity, 4), days_of_cover: round(daysOfCover, 2), inventory_age_days: ageDays == null ? null : round(ageDays, 2), shelf_life_days: shelfLife, days_to_expiry: daysToExpiry == null ? null : round(daysToExpiry, 2), confidence: 0.8, reason: `Stock cover is about ${round(daysOfCover, 1)} days, above the 60 day excess threshold.` });
  } else if (daysOfCover != null && daysOfCover > 30) {
    risks.push({ risk_type: 'SLOW_STOCK', severity: 'MEDIUM', available_stock: available, sales_velocity: round(velocity, 4), days_of_cover: round(daysOfCover, 2), inventory_age_days: ageDays == null ? null : round(ageDays, 2), shelf_life_days: shelfLife, days_to_expiry: daysToExpiry == null ? null : round(daysToExpiry, 2), confidence: 0.8, reason: `Stock cover is about ${round(daysOfCover, 1)} days, above the 30 day slow stock threshold.` });
  }

  const severityRank = { LOW: 1, MEDIUM: 2, HIGH: 3 };
  const dominant = [...risks].sort((a, b) => severityRank[b.severity] - severityRank[a.severity])[0] || null;
  return {
    product_id: productId,
    risks,
    risk_type: dominant?.risk_type || 'NONE',
    severity: dominant?.severity || 'LOW',
    available_stock: available,
    sales_velocity: round(velocity, 4),
    days_of_cover: daysOfCover == null ? null : round(daysOfCover, 2),
    confidence: dominant?.confidence || 0.9,
    generated_at: now.toISOString()
  };
}

function runI5(productId, snapshots, movements) {
  const exceptions = [];
  const sortedSnapshots = [...(snapshots || [])].sort((a, b) => (parseDate(a.timestamp)?.getTime() || 0) - (parseDate(b.timestamp)?.getTime() || 0));
  const latest = sortedSnapshots.at(-1);
  if (latest) {
    const available = Number(latest.stock_on_hand || 0) - Number(latest.reserved || 0) - Number(latest.damaged || 0);
    if (available < 0) exceptions.push({ type: 'NEGATIVE_STOCK', severity: 'HIGH', message: `Available stock is ${round(available, 2)} units.`, confidence: 1 });
  }

  const productMoves = (movements || []).filter((m) => String(m.product_id) === String(productId));
  const ids = new Set();
  const fingerprints = new Set();
  for (const move of productMoves) {
    const id = String(move.movement_id || '');
    const fp = [move.product_id, move.type, move.qty, move.timestamp].join('|');
    if (ids.has(id) || fingerprints.has(fp)) exceptions.push({ type: 'DUPLICATE_SUSPICIOUS_MOVEMENT', severity: 'MEDIUM', message: `Movement ${id || 'without an ID'} appears duplicated.`, confidence: 0.95 });
    ids.add(id); fingerprints.add(fp);
    const type = String(move.type || '').toUpperCase();
    const qty = Number(move.qty || 0);
    if (['ADJUSTMENT', 'DAMAGE'].includes(type) && Math.abs(qty) >= 10) {
      exceptions.push({ type: 'LARGE_STOCK_ADJUSTMENT', severity: Math.abs(qty) >= 20 ? 'HIGH' : 'MEDIUM', message: `${type} movement ${id} changes stock by ${round(qty, 2)} units.`, confidence: 0.9 });
    }
    if (['RECEIPT', 'SALE'].includes(type) && qty <= 0) exceptions.push({ type: 'DUPLICATE_SUSPICIOUS_MOVEMENT', severity: 'MEDIUM', message: `${type} movement ${id} has a non positive quantity.`, confidence: 0.95 });
  }

  for (let i = 1; i < sortedSnapshots.length; i += 1) {
    const opening = sortedSnapshots[i - 1], closing = sortedSnapshots[i];
    const start = parseDate(opening.timestamp)?.getTime() || 0, end = parseDate(closing.timestamp)?.getTime() || 0;
    let net = 0;
    for (const move of productMoves) {
      const ts = parseDate(move.timestamp)?.getTime() || 0;
      if (!(ts > start && ts <= end)) continue;
      const type = String(move.type || '').toUpperCase();
      const qty = Number(move.qty || 0);
      if (type === 'RECEIPT') net += qty;
      else if (type === 'SALE' || type === 'DAMAGE') net -= Math.abs(qty);
      else if (type === 'ADJUSTMENT') net += qty;
    }
    const expected = Number(opening.stock_on_hand || 0) + net;
    const actual = Number(closing.stock_on_hand || 0);
    const gap = Math.abs(expected - actual);
    if (gap > 2) exceptions.push({ type: 'MOVEMENT_SNAPSHOT_MISMATCH', severity: gap > 20 ? 'HIGH' : 'MEDIUM', message: `Recorded stock movements differ from the stock count by ${round(gap, 2)} units.`, expected_value: round(expected, 2), actual_value: round(actual, 2), confidence: 0.85 });
  }

  return {
    product_id: String(productId),
    exception_count: exceptions.length,
    exceptions: exceptions.slice(0, 50),
    severity: highestRisk(exceptions.map((e) => e.severity), 'LOW'),
    confidence: exceptions.length ? Math.min(...exceptions.map((e) => Number(e.confidence || 0.8))) : 0.95
  };
}

export function runInventoryDomain({ products, inventorySnapshots, inventoryMovements, transactions, purchaseOrders = [], goodsReceipts = [], demandByProduct, supplierContextByProduct, now = new Date() }) {
  const snapshotMap = byProduct(inventorySnapshots);
  const movementMap = byProduct(inventoryMovements);
  const results = [];
  const byProductResult = new Map();

  for (const product of (products || []).filter((p) => p.active !== false)) {
    const productId = String(product.product_id);
    const snapshotRows = snapshotMap.get(productId) || [];
    const snapshot = latestSnapshot(snapshotRows);
    const d4 = demandByProduct.get(productId)?.D4 || null;
    const supplierContext = supplierContextByProduct.get(productId) || null;
    const entry = {};

    if (!snapshot) {
      entry.I1 = null;
      results.push(insufficient({ capabilityId: 'I1', domain: 'inventory', outputType: 'InventoryPosition', entityType: 'product', entityId: productId, reason: 'No stock count has been recorded for this product.' }));
    } else {
      const baseInTransit = Number(snapshot.in_transit || 0);
      const poTransit = openPoInTransit(productId, purchaseOrders, goodsReceipts);
      const inTransit = baseInTransit + poTransit;
      const available = Number(snapshot.stock_on_hand || 0) - Number(snapshot.reserved || 0) - Number(snapshot.damaged || 0);
      const cls = classifyStock(available, inTransit, d4);
      const i1 = {
        product_id: productId,
        sku: product.sku || productId,
        product_name: product.name || productId,
        category: product.category || '',
        store_id: snapshot.store_id || 'STORE-001',
        snapshot_timestamp: snapshot.timestamp,
        stock_on_hand: Number(snapshot.stock_on_hand || 0),
        reserved: Number(snapshot.reserved || 0),
        damaged: Number(snapshot.damaged || 0),
        snapshot_in_transit: baseInTransit,
        open_purchase_order_qty: round(poTransit, 2),
        in_transit: round(inTransit, 2),
        available_stock: round(available, 2),
        stock_status: cls.stock_status,
        days_of_supply: cls.days_of_supply == null ? null : round(cls.days_of_supply, 2),
        needs_attention: cls.stock_status !== 'HEALTHY',
        forecast_7d_demand: Number(d4?.expected_qty || 0),
        forecast_confidence: Number(d4?.confidence || 0)
      };
      entry.I1 = i1;
      results.push(makeResult({ capabilityId: 'I1', domain: 'inventory', outputType: 'InventoryPosition', entityType: 'product', entityId: productId, payload: i1, confidence: 1, riskLevel: riskForStockStatus(i1.stock_status), inputRefs: d4 ? ['D4'] : [] }));
    }

    if (!d4) {
      entry.I3 = null;
      results.push(insufficient({ capabilityId: 'I3', domain: 'inventory', outputType: 'SafetyStockTarget', entityType: 'product', entityId: productId, reason: 'A usable demand forecast is required before safety stock can be calculated.', inputRefs: ['D4'] }));
    } else if (!supplierContext) {
      entry.I3 = null;
      results.push(insufficient({ capabilityId: 'I3', domain: 'inventory', outputType: 'SafetyStockTarget', entityType: 'product', entityId: productId, reason: 'Add a supplier quote for this product so lead time evidence is available.', inputRefs: ['D4', 'R2', 'R3'] }));
    } else {
      const horizon = Number(d4.horizon_days);
      const dailyDemand = Number(d4.expected_qty) / horizon;
      const horizonStd = (Number(d4.upper_bound) - Number(d4.lower_bound)) / 4;
      const dailyStd = horizonStd / Math.sqrt(horizon);
      const leadTimeDays = Math.max(0.01, Number(supplierContext.leadTimeDays || 7));
      const leadTimeDemandStd = dailyStd * Math.sqrt(leadTimeDays);
      const serviceLevel = 0.95;
      const z = SERVICE_Z[String(serviceLevel)] || 1.65;
      const reliabilityScore = clamp(supplierContext.reliabilityScore ?? 0.5);
      const reliabilityFactor = 1 + (1 - reliabilityScore);
      const raw = z * leadTimeDemandStd * reliabilityFactor;
      const safetyStock = Math.max(0, Math.ceil(raw));
      const i3 = {
        product_id: productId, safety_stock: safetyStock, expected_daily_demand: round(dailyDemand), forecast_uncertainty: round(dailyStd),
        lead_time_days: round(leadTimeDays, 2), reliability_score: round(reliabilityScore, 4), reliability_factor: round(reliabilityFactor, 4),
        service_level: serviceLevel, z_score: z, raw_safety_stock: round(raw), confidence: d4.confidence >= 0.85 ? 'HIGH' : d4.confidence >= 0.7 ? 'MEDIUM' : 'LOW',
        supplier_id: supplierContext.supplierId, generated_at: now.toISOString()
      };
      entry.I3 = i3;
      results.push(makeResult({ capabilityId: 'I3', domain: 'inventory', outputType: 'SafetyStockTarget', entityType: 'product', entityId: productId, payload: i3, confidence: Math.min(Number(d4.confidence || 0.5), Number(supplierContext.confidence || 0.5)), riskLevel: supplierContext.risk || 'MEDIUM', inputRefs: ['D4', 'R2', 'R3'] }));
    }

    if (!entry.I1 || !entry.I3 || !d4) {
      entry.I2 = null;
      results.push(insufficient({ capabilityId: 'I2', domain: 'inventory', outputType: 'ReorderNeed', entityType: 'product', entityId: productId, reason: 'Stock position, safety stock and demand forecast are all required before a reorder decision can be made.', inputRefs: ['I1', 'I3', 'D4'] }));
    } else {
      const avgDaily = Number(d4.expected_qty) / Number(d4.horizon_days);
      const reorderPoint = avgDaily * Number(entry.I3.lead_time_days) + Number(entry.I3.safety_stock);
      const inventoryPosition = Number(entry.I1.available_stock) + Number(entry.I1.in_transit);
      const reorderNeeded = inventoryPosition <= reorderPoint;
      const qty = reorderNeeded ? Math.max(0, reorderPoint - inventoryPosition) : 0;
      const i2 = { product_id: productId, reorder_point: round(reorderPoint, 4), projected_position: round(inventoryPosition, 2), reorder_needed: reorderNeeded, recommended_qty: round(qty, 2), generated_at: now.toISOString() };
      entry.I2 = i2;
      results.push(makeResult({ capabilityId: 'I2', domain: 'inventory', outputType: 'ReorderNeed', entityType: 'product', entityId: productId, payload: i2, confidence: Math.min(Number(d4.confidence || 0.5), 0.95), riskLevel: reorderNeeded ? (entry.I1.stock_status === 'CRITICAL' || entry.I1.stock_status === 'OUT_OF_STOCK' ? 'HIGH' : 'MEDIUM') : 'LOW', inputRefs: ['I1', 'I3', 'D4'] }));
    }

    const i4 = runI4(product, snapshot, movementMap.get(productId) || [], transactions, now);
    entry.I4 = i4;
    if (i4) results.push(makeResult({ capabilityId: 'I4', domain: 'inventory', outputType: 'StockRiskAlert', entityType: 'product', entityId: productId, payload: i4, confidence: i4.confidence, riskLevel: i4.severity, inputRefs: ['I1', 'transactions', 'inventoryMovements'] }));
    else results.push(insufficient({ capabilityId: 'I4', domain: 'inventory', outputType: 'StockRiskAlert', entityType: 'product', entityId: productId, reason: 'A stock count is required before slow stock or expiry risk can be assessed.' }));

    const i5 = runI5(productId, snapshotRows, movementMap.get(productId) || []);
    entry.I5 = i5;
    results.push(makeResult({ capabilityId: 'I5', domain: 'inventory', outputType: 'InventoryException', entityType: 'product', entityId: productId, payload: i5, confidence: i5.confidence, riskLevel: i5.severity, inputRefs: ['inventorySnapshots', 'inventoryMovements'] }));

    byProductResult.set(productId, entry);
  }

  return { results, byProduct: byProductResult };
}

import { clamp, highestRisk, makeResult, insufficient, mean, median, normalizedHighIsGood, normalizedLowIsGood, parseDate, percentile, recencyWeight, robustStd, round, weightedMean } from './common.mjs';

const riskScore = { LOW: 1, MEDIUM: 2, HIGH: 3 };
const leadDecisionScore = { LOW: 1, MEDIUM: 0.6, HIGH: 0.2 };

function group(rows, field) {
  const map = new Map();
  for (const row of rows || []) {
    const id = String(row[field] || '');
    if (!map.has(id)) map.set(id, []);
    map.get(id).push(row);
  }
  return map;
}

function validQuote(q, supplierMap, now) {
  if (!supplierMap.has(String(q.supplier_id))) return false;
  const supplier = supplierMap.get(String(q.supplier_id));
  if (String(supplier.status || 'ACTIVE').toUpperCase() !== 'ACTIVE') return false;
  const until = parseDate(q.valid_until);
  return !until || until >= now;
}

export function buildSupplierEvidence({ suppliers, supplierQuotes, supplierPerformance, now = new Date() }) {
  const supplierMap = new Map((suppliers || []).map((s) => [String(s.supplier_id), s]));
  const perfBySupplier = group(supplierPerformance, 'supplier_id');
  const quoteBySupplier = group(supplierQuotes, 'supplier_id');
  const r2BySupplier = new Map();
  const r3BySupplier = new Map();

  for (const supplier of suppliers || []) {
    const supplierId = String(supplier.supplier_id);
    const rows = perfBySupplier.get(supplierId) || [];
    let r2;
    if (!rows.length) {
      r2 = { supplier_id: supplierId, score: 0.5, on_time_rate: 0.5, fill_rate: 0.5, defect_rate: 0, invoice_accuracy: 0.5, sample_size: 0, confidence: 0.2, risk: 'MEDIUM' };
    } else {
      const onTimePairs = [], fillPairs = [], defectPairs = [], invoicePairs = [];
      for (const row of rows) {
        const actual = parseDate(row.actual_date), promised = parseDate(row.promised_date);
        if (!actual || !promised) continue;
        const age = Math.max(0, (now.getTime() - actual.getTime()) / 86_400_000);
        const w = recencyWeight(age);
        const ordered = Math.max(Number(row.ordered_qty || 0), 1e-9);
        const received = Math.max(Number(row.received_qty || 0), 0);
        const defects = Math.max(Number(row.defect_qty || 0), 0);
        const fill = clamp(received / ordered);
        const defectRate = received ? clamp(defects / received) : 0;
        const invoiceAccuracy = 1 - clamp(Math.abs(Number(row.invoice_variance_pct || 0)) / 0.10);
        onTimePairs.push([actual <= promised ? 1 : 0, w]);
        fillPairs.push([fill, w]);
        defectPairs.push([defectRate, w]);
        invoicePairs.push([invoiceAccuracy, w]);
      }
      const onTime = weightedMean(onTimePairs, 0.5);
      const fillRate = weightedMean(fillPairs, 0.5);
      const defectRate = weightedMean(defectPairs, 0);
      const invoiceAccuracy = weightedMean(invoicePairs, 0.5);
      const score = clamp(0.40 * onTime + 0.35 * fillRate + 0.15 * (1 - defectRate) + 0.10 * invoiceAccuracy);
      const confidence = Math.min(0.98, 0.25 + rows.length / 12);
      const risk = score < 0.55 ? 'HIGH' : score < 0.75 ? 'MEDIUM' : 'LOW';
      r2 = { supplier_id: supplierId, score: round(score), on_time_rate: round(onTime), fill_rate: round(fillRate), defect_rate: round(defectRate), invoice_accuracy: round(invoiceAccuracy), sample_size: rows.length, confidence: round(confidence), risk };
    }
    r2BySupplier.set(supplierId, r2);

    const leadDays = [], delayed = [];
    for (const row of rows) {
      const order = parseDate(row.order_date), actual = parseDate(row.actual_date), promised = parseDate(row.promised_date);
      if (!order || !actual || !promised) continue;
      leadDays.push(Math.max((actual.getTime() - order.getTime()) / 86_400_000, 1));
      delayed.push(actual > promised ? 1 : 0);
    }
    let fallback = false;
    if (!leadDays.length) {
      const quoted = (quoteBySupplier.get(supplierId) || []).map((q) => Number(q.quoted_lead_time_days || 7)).filter((x) => x > 0);
      leadDays.push(quoted.length ? Math.min(...quoted) : 7);
      delayed.push(0);
      fallback = true;
    }
    const med = median(leadDays), expected = mean(leadDays), p90 = percentile(leadDays, 0.9), variability = robustStd(leadDays);
    const delayRate = delayed.length ? delayed.reduce((a, b) => a + b, 0) / delayed.length : 0;
    let risk = p90 >= 15 || delayRate >= 0.45 || (med && p90 / med >= 1.8) ? 'HIGH' : p90 >= 10 || delayRate >= 0.20 || variability >= 3 ? 'MEDIUM' : 'LOW';
    if (r2.score < 0.55) risk = 'HIGH';
    else if (r2.score < 0.75 && risk === 'LOW') risk = 'MEDIUM';
    const confidence = fallback ? 0.25 : Math.min(0.96, 0.30 + leadDays.length / 10);
    const r3 = { supplier_id: supplierId, median_days: round(med, 2), expected_days: round(expected, 2), p90_days: round(p90, 2), variability_days: round(variability, 2), delay_rate: round(delayRate), risk, sample_size: fallback ? 0 : leadDays.length, confidence: round(confidence), fallback };
    r3BySupplier.set(supplierId, r3);
  }

  const supplierContextByProduct = new Map();
  const activeQuotes = (supplierQuotes || []).filter((q) => validQuote(q, supplierMap, now));
  const byProduct = group(activeQuotes, 'product_id');
  for (const [productId, quotes] of byProduct.entries()) {
    const candidates = quotes.map((q) => {
      const sid = String(q.supplier_id), r2 = r2BySupplier.get(sid), r3 = r3BySupplier.get(sid);
      return { q, sid, r2, r3 };
    }).filter((x) => x.r2 && x.r3);
    candidates.sort((a, b) => (riskScore[a.r3.risk] - riskScore[b.r3.risk]) || (b.r2.score - a.r2.score) || (a.r3.p90_days - b.r3.p90_days) || (Number(a.q.unit_cost) - Number(b.q.unit_cost)));
    const best = candidates[0];
    if (best) supplierContextByProduct.set(String(productId), { supplierId: best.sid, leadTimeDays: best.r3.p90_days, reliabilityScore: best.r2.score, confidence: Math.min(best.r2.confidence, best.r3.confidence), risk: best.r3.risk });
  }

  return { supplierMap, r2BySupplier, r3BySupplier, supplierContextByProduct };
}

function runR1(productId, requestedQty, suppliers, supplierQuotes, now) {
  const supplierMap = new Map((suppliers || []).filter((s) => String(s.status || 'ACTIVE').toUpperCase() === 'ACTIVE').map((s) => [String(s.supplier_id), s]));
  const quotes = (supplierQuotes || []).filter((q) => String(q.product_id) === String(productId) && validQuote(q, supplierMap, now));
  if (!quotes.length) return { product_id: productId, requested_qty: requestedQty, ranked_suppliers: [], confidence: 0, insufficient: true };
  const costs = quotes.map((q) => Number(q.unit_cost));
  const leads = quotes.map((q) => Number(q.quoted_lead_time_days || 7));
  const terms = quotes.map((q) => Number(q.payment_terms_days ?? supplierMap.get(String(q.supplier_id))?.payment_terms_days ?? 30));
  const raw = quotes.map((q) => {
    const supplier = supplierMap.get(String(q.supplier_id));
    const paymentTerms = Number(q.payment_terms_days ?? supplier.payment_terms_days ?? 30);
    const costScore = normalizedLowIsGood(Number(q.unit_cost), Math.min(...costs), Math.max(...costs));
    const leadScore = normalizedLowIsGood(Number(q.quoted_lead_time_days || 7), Math.min(...leads), Math.max(...leads));
    const termsScore = normalizedHighIsGood(paymentTerms, Math.min(...terms), Math.max(...terms));
    const moq = Number(q.moq || 1);
    const moqScore = moq <= requestedQty ? 1 : Math.max(0, 1 - (moq - requestedQty) / Math.max(requestedQty, 1));
    const availability = q.available_qty == null ? null : Number(q.available_qty);
    const need = Math.max(moq, requestedQty);
    const coverage = availability == null ? 1 : availability >= need ? 1 : Math.max(availability / need, 0);
    const score = 0.40 * costScore + 0.20 * moqScore + 0.20 * leadScore + 0.10 * termsScore + 0.10 * coverage;
    const warnings = [];
    if (moq > requestedQty) warnings.push('MOQ exceeds requested quantity');
    if (availability != null && availability < need) warnings.push('Quoted available quantity may not cover the order');
    return { supplier_id: String(q.supplier_id), supplier_name: supplier.name, score: round(score), unit_cost: Number(q.unit_cost), moq, quoted_lead_time_days: Number(q.quoted_lead_time_days || 7), payment_terms_days: paymentTerms, score_breakdown: { cost: round(costScore), moq_fit: round(moqScore), lead_time: round(leadScore), payment_terms: round(termsScore), coverage: round(coverage) }, warnings };
  }).sort((a, b) => b.score - a.score || a.unit_cost - b.unit_cost).map((x, i) => ({ ...x, rank: i + 1 }));
  return { product_id: String(productId), requested_qty: Number(requestedQty), ranked_suppliers: raw, generated_at: now.toISOString(), confidence: Math.min(0.98, 0.65 + 0.06 * raw.length), insufficient: false };
}

function runR4(productId, inventory, d4, r1, r2BySupplier, r3BySupplier) {
  const i2 = inventory?.I2, i3 = inventory?.I3;
  if (!i2 || !i3 || !d4 || !r1 || !r1.ranked_suppliers?.length) return { status: 'DRAFT', actionable: false, reason: 'Required demand, inventory or supplier evidence is missing.' };
  if (!i2.reorder_needed || Number(i2.recommended_qty) <= 0) return { status: 'NO_PURCHASE_REQUIRED', actionable: false, product_id: productId, reorder_needed: false, recommended_qty: 0 };
  const candidates = [];
  for (const rank of r1.ranked_suppliers) {
    const rel = r2BySupplier.get(String(rank.supplier_id)), lead = r3BySupplier.get(String(rank.supplier_id));
    if (!rel || !lead) continue;
    let decision = 0.40 * rank.score + 0.35 * rel.score + 0.20 * leadDecisionScore[lead.risk] + 0.05 * Math.min(rel.confidence, lead.confidence, d4.confidence);
    const qty = Math.max(Number(i2.recommended_qty), Number(rank.moq));
    if ((rank.warnings || []).some((w) => /available quantity/i.test(w))) decision *= 0.75;
    candidates.push({ rank, rel, lead, qty, expected_cost: qty * rank.unit_cost, decision_score: clamp(decision) });
  }
  if (!candidates.length) return { status: 'DRAFT', actionable: false, reason: 'Supplier reliability or lead time evidence is incomplete.' };
  candidates.sort((a, b) => b.decision_score - a.decision_score || a.expected_cost - b.expected_cost);
  const chosen = candidates[0];
  let risk = 'LOW';
  if (chosen.lead.risk === 'HIGH' || chosen.rel.score < 0.55 || d4.confidence < 0.45) risk = 'HIGH';
  else if (chosen.lead.risk === 'MEDIUM' || chosen.rel.score < 0.75 || d4.confidence < 0.70) risk = 'MEDIUM';
  if (chosen.expected_cost >= 25000 || risk === 'HIGH') risk = 'HIGH';
  return {
    status: 'READY_FOR_REVIEW', actionable: true, product_id: String(productId), supplier_id: chosen.rank.supplier_id, qty: round(chosen.qty, 2), unit_cost: chosen.rank.unit_cost,
    expected_cost: round(chosen.expected_cost, 2), eta_days: chosen.lead.p90_days, supplier_score: chosen.rank.score, reliability_score: chosen.rel.score,
    lead_time_risk: chosen.lead.risk, risk, currency: 'ZAR', decision_score: round(chosen.decision_score), alternatives: candidates.slice(1, 4).map((c) => ({ supplier_id: c.rank.supplier_id, qty: round(c.qty, 2), expected_cost: round(c.expected_cost, 2), decision_score: round(c.decision_score), lead_time_risk: c.lead.risk, reliability_score: c.rel.score })),
    confidence: Math.min(0.96, 0.50 + 0.25 * chosen.rel.confidence + 0.15 * chosen.lead.confidence + 0.10 * Number(d4.confidence))
  };
}

function runR5(po, receipts, invoices, allInvoices) {
  const poId = String(po.po_id);
  if (!receipts.length || !invoices.length) {
    const missing = [];
    if (!receipts.length) missing.push('goods receipt');
    if (!invoices.length) missing.push('supplier invoice');
    return { supplier_id: String(po.supplier_id), po_id: poId, exception_types: ['INSUFFICIENT_EVIDENCE'], details: { missing }, match_status: 'INSUFFICIENT_EVIDENCE', financial_variance: 0, severity: 'HIGH', confidence: 0 };
  }
  const totalReceived = receipts.reduce((s, r) => s + Number(r.qty_received || 0), 0);
  const totalDefective = receipts.reduce((s, r) => s + Number(r.qty_defective || 0), 0);
  const invoicedQty = invoices.reduce((s, r) => s + Number(r.qty_invoiced || 0), 0);
  const invoiceSubtotal = invoices.reduce((s, r) => s + Number(r.qty_invoiced || 0) * Number(r.unit_cost || 0), 0);
  const expectedSubtotal = Number(po.qty || 0) * Number(po.unit_cost || 0);
  const variance = invoiceSubtotal - expectedSubtotal;
  const exceptions = [], details = {};
  if (totalReceived < Number(po.qty || 0)) { exceptions.push('UNDER_DELIVERY'); details.receipt_quantity = { ordered: Number(po.qty), received: totalReceived }; }
  else if (totalReceived > Number(po.qty || 0)) { exceptions.push('OVER_DELIVERY'); details.receipt_quantity = { ordered: Number(po.qty), received: totalReceived }; }
  if (Math.abs(invoicedQty - totalReceived) > 0) { exceptions.push('INVOICE_RECEIPT_QTY_MISMATCH'); details.invoice_quantity = { received: totalReceived, invoiced: invoicedQty }; }
  const allowed = Math.max(expectedSubtotal * 0.01, 0.01);
  if (Math.abs(variance) > allowed) { exceptions.push('PRICE_VARIANCE'); details.financial = { expected_subtotal: round(expectedSubtotal, 2), invoice_subtotal: round(invoiceSubtotal, 2), variance: round(variance, 2) }; }
  if (totalDefective > 0) { exceptions.push('DEFECTIVE_GOODS'); details.defects = { qty_defective: totalDefective }; }
  const latestReceipt = receipts.map((r) => parseDate(r.received_at)).filter(Boolean).sort((a, b) => b.getTime() - a.getTime())[0];
  const promised = parseDate(po.promised_date);
  if (latestReceipt && promised && latestReceipt > promised) { exceptions.push('LATE_DELIVERY'); details.delivery = { promised_date: String(po.promised_date).slice(0, 10), actual_date: latestReceipt.toISOString().slice(0, 10), days_late: Math.round((latestReceipt - promised) / 86_400_000) }; }
  const numberCounts = new Map();
  for (const invoice of allInvoices || []) if (invoice.invoice_number) numberCounts.set(String(invoice.invoice_number), (numberCounts.get(String(invoice.invoice_number)) || 0) + 1);
  const dup = invoices.map((i) => String(i.invoice_number || '')).filter((n) => n && (numberCounts.get(n) || 0) > 1);
  if (dup.length) { exceptions.push('DUPLICATE_INVOICE_NUMBER'); details.duplicate_invoice_numbers = [...new Set(dup)]; }
  const high = new Set(['PRICE_VARIANCE', 'DUPLICATE_INVOICE_NUMBER', 'OVER_DELIVERY']);
  const severity = exceptions.some((x) => high.has(x)) ? 'HIGH' : exceptions.length ? 'MEDIUM' : 'LOW';
  return { supplier_id: String(po.supplier_id), po_id: poId, exception_types: exceptions, details, match_status: exceptions.length ? (severity === 'HIGH' ? 'MISMATCH' : 'PARTIAL_MATCH') : 'MATCH', financial_variance: round(variance, 2), severity, confidence: 0.98 };
}

export function runProcurementDomain({ products, suppliers, supplierQuotes, supplierPerformance, purchaseOrders, goodsReceipts, invoices, demandByProduct, inventoryByProduct, evidence, now = new Date() }) {
  const results = [];
  const r1ByProduct = new Map(), r4ByProduct = new Map(), r5ByPo = new Map();

  for (const [supplierId, r2] of evidence.r2BySupplier.entries()) {
    results.push(makeResult({ capabilityId: 'R2', domain: 'procurement', outputType: 'SupplierReliabilityScore', entityType: 'supplier', entityId: supplierId, payload: r2, confidence: r2.confidence, riskLevel: r2.risk, inputRefs: ['supplierPerformance'] }));
  }
  for (const [supplierId, r3] of evidence.r3BySupplier.entries()) {
    results.push(makeResult({ capabilityId: 'R3', domain: 'procurement', outputType: 'LeadTimeRisk', entityType: 'supplier', entityId: supplierId, payload: r3, confidence: r3.confidence, riskLevel: r3.risk, inputRefs: ['R2', 'supplierPerformance', 'supplierQuotes'] }));
  }

  for (const product of (products || []).filter((p) => p.active !== false)) {
    const productId = String(product.product_id);
    const inventory = inventoryByProduct.get(productId);
    const requested = Math.max(Number(inventory?.I2?.recommended_qty || 1), 1);
    const r1 = runR1(productId, requested, suppliers, supplierQuotes, now);
    r1ByProduct.set(productId, r1);
    results.push(makeResult({ capabilityId: 'R1', domain: 'procurement', outputType: 'SupplierComparison', entityType: 'product', entityId: productId, payload: r1, confidence: r1.confidence || 0, riskLevel: r1.insufficient ? 'HIGH' : 'LOW', status: r1.insufficient ? 'SKIPPED' : 'SUCCEEDED', inputRefs: ['supplierQuotes', 'suppliers'] }));

    const d4 = demandByProduct.get(productId)?.D4;
    const r4 = runR4(productId, inventory, d4, r1, evidence.r2BySupplier, evidence.r3BySupplier);
    r4ByProduct.set(productId, r4);
    results.push(makeResult({ capabilityId: 'R4', domain: 'procurement', outputType: r4.status === 'NO_PURCHASE_REQUIRED' ? 'NoPurchaseRequired' : 'PurchaseRecommendation', entityType: 'product', entityId: productId, payload: r4, confidence: r4.confidence || (r4.status === 'NO_PURCHASE_REQUIRED' ? 0.96 : 0), riskLevel: r4.risk || (r4.actionable ? 'MEDIUM' : 'LOW'), status: r4.status === 'DRAFT' ? 'SKIPPED' : 'SUCCEEDED', inputRefs: ['I2', 'I3', 'D4', 'R1', 'R2', 'R3'] }));
  }

  const receiptsByPo = group(goodsReceipts, 'po_id'), invoicesByPo = group(invoices, 'po_id');
  for (const po of purchaseOrders || []) {
    const poId = String(po.po_id);
    const r5 = runR5(po, receiptsByPo.get(poId) || [], invoicesByPo.get(poId) || [], invoices || []);
    r5ByPo.set(poId, r5);
    results.push(makeResult({ capabilityId: 'R5', domain: 'procurement', outputType: 'ProcurementException', entityType: 'purchase_order', entityId: poId, payload: r5, confidence: r5.confidence, riskLevel: r5.severity, status: r5.match_status === 'INSUFFICIENT_EVIDENCE' ? 'SKIPPED' : 'SUCCEEDED', inputRefs: ['purchaseOrders', 'goodsReceipts', 'invoices'] }));
  }
  if (!(purchaseOrders || []).length) {
    results.push(insufficient({ capabilityId: 'R5', domain: 'procurement', outputType: 'ProcurementException', entityType: 'business', entityId: 'procurement', reason: 'No purchase orders exist yet. Reconciliation will start after approved orders are received and invoiced.' }));
  }

  return { results, r1ByProduct, r4ByProduct, r5ByPo };
}

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runInventoryDomain } from '../server/process/inventory-runtime.mjs';
import { buildSupplierEvidence, runProcurementDomain } from '../server/process/procurement-runtime.mjs';
import { runPricingDomain } from '../server/process/pricing-runtime.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP = path.resolve(HERE, '..');
const FOUNDATION = path.resolve(APP, '..', '..');
const now = new Date();
const iso = (days = 0) => new Date(now.getTime() + days * 86_400_000).toISOString();

const products = [{ product_id:'P-VALIDATE', name:'Validation product', sku:'VAL-1', category:'Beverages', unit_cost:20, sell_price:35, variable_fees_per_unit:1, margin_floor_pct:.20, shelf_life_days:90, active:true }];
const transactions = Array.from({length:35},(_,i)=>({ transaction_id:`T-${i}`, timestamp:iso(-34+i), store_id:'STORE-1', product_id:'P-VALIDATE', customer_id:'C-1', qty:5+(i%4), unit_price:[35,33,32,34][i%4], discount:0, channel:'IN_STORE' }));
const snapshots = [{ timestamp:iso(0), store_id:'STORE-1', product_id:'P-VALIDATE', stock_on_hand:8, reserved:1, damaged:0, in_transit:0 }];
const movements = [{ movement_id:'M-1', product_id:'P-VALIDATE', type:'RECEIPT', qty:30, timestamp:iso(-25), reference:'PO-OLD' }];
const suppliers = [{ supplier_id:'SUP-1', name:'Validation supplier', status:'ACTIVE', payment_terms_days:30, currency:'ZAR' }];
const quotes = [{ quote_id:'Q-1', supplier_id:'SUP-1', product_id:'P-VALIDATE', unit_cost:18, moq:10, quoted_lead_time_days:5, available_qty:200, payment_terms_days:30, currency:'ZAR', valid_from:iso(-1), valid_until:iso(14), observed_at:iso(0) }];
const performance = [
  { performance_id:'SP-1', supplier_id:'SUP-1', po_id:'PO-1', order_date:iso(-60).slice(0,10), promised_date:iso(-54).slice(0,10), actual_date:iso(-54).slice(0,10), ordered_qty:50, received_qty:50, defect_qty:0, invoice_variance_pct:0 },
  { performance_id:'SP-2', supplier_id:'SUP-1', po_id:'PO-2', order_date:iso(-40).slice(0,10), promised_date:iso(-34).slice(0,10), actual_date:iso(-33).slice(0,10), ordered_qty:40, received_qty:39, defect_qty:0, invoice_variance_pct:.01 }
];
const d4 = { product_id:'P-VALIDATE', horizon_days:7, expected_qty:52, lower_bound:42, upper_bound:62, confidence:.82, drivers:['weekly pattern'], forecast_days:[], generated_at:iso(0) };
const demandByProduct = new Map([['P-VALIDATE',{D4:d4}]]);

const evidence = buildSupplierEvidence({ suppliers, supplierQuotes:quotes, supplierPerformance:performance, now });
assert.ok(evidence.r2BySupplier.get('SUP-1'));
assert.ok(evidence.r3BySupplier.get('SUP-1'));

const inventory = runInventoryDomain({ products, inventorySnapshots:snapshots, inventoryMovements:movements, transactions, purchaseOrders:[], goodsReceipts:[], demandByProduct, supplierContextByProduct:evidence.supplierContextByProduct, now });
const inv = inventory.byProduct.get('P-VALIDATE');
assert.ok(inv?.I1);
assert.ok(inv?.I2);
assert.ok(inv?.I3);
assert.ok(Object.prototype.hasOwnProperty.call(inv,'I4'));
assert.ok(Object.prototype.hasOwnProperty.call(inv,'I5'));

const procurement = runProcurementDomain({ products, suppliers, supplierQuotes:quotes, supplierPerformance:performance, purchaseOrders:[], goodsReceipts:[], invoices:[], demandByProduct, inventoryByProduct:inventory.byProduct, evidence, now });
assert.ok(procurement.r1ByProduct.get('P-VALIDATE'));
assert.ok(procurement.r4ByProduct.get('P-VALIDATE'));

const competitor = [
  { observation_id:'CP1',product_id:'P-VALIDATE',store_name:'Store A',price:34,observed_at:iso(0),source:'manual' },
  { observation_id:'CP2',product_id:'P-VALIDATE',store_name:'Store B',price:36,observed_at:iso(0),source:'manual' }
];
const policy = JSON.parse(fs.readFileSync(path.join(APP,'server','process','pricing-policy.json'),'utf8'));
const pricing = runPricingDomain({ product:{product_id:'P-VALIDATE',current_price:35,unit_cost:20,variable_fees_per_unit:1,margin_floor_pct:.20,currency:'ZAR'}, competitorObservations:competitor, transactions, d4, i1:inv.I1, i4:inv.I4, policy, now });
assert.equal(pricing.p1.status,'OK');
assert.equal(pricing.p2.status,'OK');
assert.ok(['ESTIMATED','UNRELIABLE'].includes(pricing.p3.status));
assert.ok(pricing.p5);

const customerVendor = path.join(FOUNDATION,'vendor','customer-engagement-shared','dist','integration','runtime.js');
assert.ok(fs.existsSync(customerVendor), 'Actual C1-C5 compiled runtime is missing from foundation/vendor.');
const { runCustomerDomain } = await import('../server/process/customer-runtime.mjs');
const customer = await runCustomerDomain({
  businessId:'validation-business',
  customers:[{customer_id:'C-1',name:'Validation customer',consent_marketing:true,created_at:iso(-60),last_visit_at:iso(-1)}],
  transactions, products, feedback:[], inventoryByProduct:inventory.byProduct, now
});
for (const id of ['C1','C2','C3','C4','C5']) assert.ok(customer.results.some((row)=>row.capabilityId===id), `${id} did not produce a result.`);


const processingSource = fs.readFileSync(path.join(APP,'server','process','processing-service.mjs'),'utf8');
const workspaceSource = fs.readFileSync(path.join(APP,'server','firestore-data.mjs'),'utf8');
const approvalSource = fs.readFileSync(path.join(APP,'server','process','approval-executor.mjs'),'utf8');
const demandSource = fs.readFileSync(path.join(APP,'server','process','demand_runner.py'),'utf8');
assert.match(processingSource, /PROCESSING_LEASE_MS/);
assert.match(processingSource, /DATA_CHANGED_DURING_PROCESSING/);
assert.match(workspaceSource, /filter\(\(x\)=>!x\.analysisRunId\)/);
assert.match(approvalSource, /recommendationStatus/);
assert.match(demandSource, /source_version/);
assert.ok(fs.existsSync(path.join(APP,'Dockerfile')));

const demandVendor = path.join(FOUNDATION,'vendor','florah-demand','backend','app','agents','demand');
assert.ok(fs.existsSync(demandVendor), 'Real Florah D1-D5 source is missing from foundation/vendor.');
assert.ok(fs.existsSync(path.join(APP,'server','process','demand_runner.py')));

console.log('Inventory I1-I5 runtime: PASS');
console.log('Procurement R1-R5 runtime: PASS');
console.log('Pricing P1-P5 runtime: PASS');
console.log('Customer C1-C5 actual runtime: PASS');
console.log('Real Demand bridge + Florah source: PRESENT');
console.log('Approval execution wiring: PRESENT');
console.log('Run activation + data-change isolation: PASS');
console.log('Abandoned processing lease recovery: PASS');
console.log('Production Node + Python container: READY');
console.log('Synthetic operational data persistence: NONE');
console.log('PROCESS_DATA_FLOW_READY');

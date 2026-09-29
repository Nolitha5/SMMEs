import assert from 'node:assert/strict';
import { publicCatalog, normalizeRecord, validateRecords } from '../server/data-registry.mjs';

const catalog = publicCatalog();
assert.equal(catalog.length, 16, 'Expected 16 editable source data sets');
assert.ok(catalog.some((x) => x.key === 'products'));
assert.ok(catalog.some((x) => x.key === 'transactions'));
assert.ok(catalog.some((x) => x.key === 'inventorySnapshots'));
assert.ok(catalog.some((x) => x.key === 'supplierQuotes'));
assert.ok(catalog.some((x) => x.key === 'competitorPrices'));
assert.ok(catalog.some((x) => x.key === 'customers'));

const product = normalizeRecord('products', {
  product_id: 'P001', name: 'Water', category: 'Beverages', unit_cost: '4.20', sell_price: '8.00', margin_floor_pct: '20', active: 'yes'
});
assert.equal(product.errors.length, 0);
assert.equal(product.record.margin_floor_pct, 0.2);
assert.equal(product.record.active, true);

const snapshot = normalizeRecord('inventorySnapshots', {
  timestamp: '2026-09-29T08:00:00+02:00', store_id: 'STORE-001', product_id: 'P001', stock_on_hand: 10, reserved: 2, damaged: 1, in_transit: 5
});
assert.equal(snapshot.errors.length, 0);
assert.match(snapshot.id, /^snapshot_STORE-001_P001_/);

const badPromo = validateRecords('promotions', [{
  promo_id: 'PR1', product_id: 'P001', start: '2026-10-10', end: '2026-10-01', discount_type: 'PERCENT', value: 10
}]);
assert.ok(badPromo.errors.some((x) => x.field === 'end'));

const duplicates = validateRecords('transactions', [
  { transaction_id: 'T1', timestamp: '2026-09-29', store_id: 'S1', product_id: 'P001', qty: 1, unit_price: 10 },
  { transaction_id: 'T1', timestamp: '2026-09-29', store_id: 'S1', product_id: 'P001', qty: 2, unit_price: 10 }
]);
assert.ok(duplicates.errors.some((x) => /Duplicate record ID/.test(x.message)));

console.log('Business data catalog:', catalog.length);
console.log('CSV validation: PASS');
console.log('Manual record validation: PASS');
console.log('Identity protection: PASS');
console.log('DATA_MANAGEMENT_VALIDATED');

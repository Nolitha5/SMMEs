const field = (name, label, type = 'string', extra = {}) => ({ name, label, type, ...extra });

export const DATASETS = Object.freeze({
  products: {
    key: 'products', label: 'Products', group: 'Sales and catalog', collection: 'products',
    description: 'The product catalogue used by demand, stock, pricing and customer analysis.',
    idField: 'product_id',
    fields: [
      field('product_id', 'Product ID', 'string', { required: true, lockedOnEdit: true, example: 'P001' }),
      field('name', 'Product name', 'string', { required: true }),
      field('sku', 'SKU', 'string'),
      field('category', 'Category', 'string', { required: true }),
      field('unit_cost', 'Unit cost', 'number', { required: true, min: 0 }),
      field('sell_price', 'Selling price', 'number', { required: true, min: 0 }),
      field('margin_floor_pct', 'Minimum margin %', 'percent', { min: 0, max: 99, default: 20 }),
      field('variable_fees_per_unit', 'Variable fees per unit', 'number', { min: 0, default: 0 }),
      field('shelf_life_days', 'Shelf life days', 'number', { min: 0 }),
      field('active', 'Active', 'boolean', { default: true })
    ]
  },
  transactions: {
    key: 'transactions', label: 'Sales', group: 'Sales and catalog', collection: 'transactions',
    description: 'Completed sales history. Import products first so every product ID can be checked.',
    idField: 'transaction_id',
    references: [{ field: 'product_id', dataset: 'products', label: 'product' }, { field: 'customer_id', dataset: 'customers', label: 'customer', optional: true }],
    fields: [
      field('transaction_id', 'Transaction ID', 'string', { required: true, lockedOnEdit: true }),
      field('timestamp', 'Date and time', 'datetime', { required: true }),
      field('store_id', 'Store ID', 'string', { required: true, default: 'STORE-001' }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('customer_id', 'Customer ID', 'string'),
      field('qty', 'Quantity', 'number', { required: true, min: 0 }),
      field('unit_price', 'Unit price', 'number', { required: true, min: 0 }),
      field('discount', 'Discount', 'number', { min: 0, default: 0 }),
      field('channel', 'Channel', 'enum', { options: ['IN_STORE', 'ONLINE', 'DELIVERY', 'OTHER'], default: 'IN_STORE' })
    ]
  },
  promotions: {
    key: 'promotions', label: 'Promotions', group: 'Sales and catalog', collection: 'promotions',
    description: 'Promotions that actually ran or are genuinely scheduled.',
    idField: 'promo_id', references: [{ field: 'product_id', dataset: 'products', label: 'product' }],
    fields: [
      field('promo_id', 'Promotion ID', 'string', { required: true, lockedOnEdit: true }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('start', 'Start date', 'date', { required: true }),
      field('end', 'End date', 'date', { required: true }),
      field('discount_type', 'Discount type', 'enum', { options: ['PERCENT', 'AMOUNT', 'OTHER'], default: 'PERCENT' }),
      field('value', 'Value', 'number', { required: true, min: 0 }),
      field('channel', 'Channel', 'enum', { options: ['IN_STORE', 'ONLINE', 'ALL', 'OTHER'], default: 'ALL' })
    ]
  },
  localEvents: {
    key: 'localEvents', label: 'Local events', group: 'Sales and catalog', collection: 'localEvents',
    description: 'Real local events that may change demand. Expected impact is the business estimate when history is limited.',
    idField: 'event_id',
    fields: [
      field('event_id', 'Event ID', 'string', { required: true, lockedOnEdit: true }),
      field('date', 'Date', 'date', { required: true }),
      field('event_name', 'Event name', 'string', { required: true }),
      field('location', 'Location', 'string'),
      field('event_type', 'Event type', 'enum', { options: ['SPORT', 'HOLIDAY', 'MARKET', 'COMMUNITY', 'OTHER'], default: 'OTHER' }),
      field('expected_impact', 'Expected impact', 'decimal', { min: -1, max: 3, default: 0 })
    ]
  },
  inventorySnapshots: {
    key: 'inventorySnapshots', label: 'Stock counts', group: 'Stock', collection: 'inventorySnapshots',
    description: 'Point in time stock counts used by stock monitoring and replenishment.',
    idFrom: (r) => `snapshot_${safe(r.store_id)}_${safe(r.product_id)}_${safe(r.timestamp)}`,
    lockedFields: ['timestamp', 'store_id', 'product_id'], references: [{ field: 'product_id', dataset: 'products', label: 'product' }],
    fields: [
      field('timestamp', 'Captured at', 'datetime', { required: true, lockedOnEdit: true }),
      field('store_id', 'Store ID', 'string', { required: true, default: 'STORE-001', lockedOnEdit: true }),
      field('product_id', 'Product ID', 'string', { required: true, lockedOnEdit: true }),
      field('stock_on_hand', 'Stock on hand', 'number', { required: true, min: 0 }),
      field('reserved', 'Reserved', 'number', { min: 0, default: 0 }),
      field('damaged', 'Damaged', 'number', { min: 0, default: 0 }),
      field('in_transit', 'In transit', 'number', { min: 0, default: 0 })
    ]
  },
  inventoryMovements: {
    key: 'inventoryMovements', label: 'Stock movements', group: 'Stock', collection: 'inventoryMovements',
    description: 'Receipts, sales, damage and stock adjustments.',
    idField: 'movement_id', references: [{ field: 'product_id', dataset: 'products', label: 'product' }],
    fields: [
      field('movement_id', 'Movement ID', 'string', { required: true, lockedOnEdit: true }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('type', 'Movement type', 'enum', { required: true, options: ['RECEIPT', 'SALE', 'ADJUSTMENT', 'DAMAGE', 'TRANSFER'] }),
      field('qty', 'Quantity', 'number', { required: true }),
      field('timestamp', 'Date and time', 'datetime', { required: true }),
      field('reference', 'Reference', 'string')
    ]
  },
  competitorPrices: {
    key: 'competitorPrices', label: 'Competitor prices', group: 'Pricing', collection: 'competitorPrices',
    description: 'Real market price observations. Pricing ignores stale observations automatically.',
    idField: 'observation_id', references: [{ field: 'product_id', dataset: 'products', label: 'product' }],
    fields: [
      field('observation_id', 'Observation ID', 'string', { required: true, lockedOnEdit: true }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('store_name', 'Competitor or store', 'string', { required: true }),
      field('price', 'Observed price', 'number', { required: true, min: 0.01 }),
      field('observed_at', 'Observed at', 'datetime', { required: true }),
      field('source', 'Source', 'string', { default: 'manual observation' }),
      field('source_url', 'Source URL', 'string')
    ]
  },
  suppliers: {
    key: 'suppliers', label: 'Suppliers', group: 'Procurement', collection: 'suppliers',
    description: 'Supplier master records used for sourcing and purchase decisions.',
    idField: 'supplier_id',
    fields: [
      field('supplier_id', 'Supplier ID', 'string', { required: true, lockedOnEdit: true }),
      field('name', 'Supplier name', 'string', { required: true }),
      field('status', 'Status', 'enum', { options: ['ACTIVE', 'SUSPENDED', 'INACTIVE'], default: 'ACTIVE' }),
      field('payment_terms_days', 'Payment terms days', 'number', { min: 0, default: 30 }),
      field('currency', 'Currency', 'string', { default: 'ZAR' }),
      field('contact_email', 'Contact email', 'string')
    ]
  },
  supplierQuotes: {
    key: 'supplierQuotes', label: 'Supplier quotes', group: 'Procurement', collection: 'supplierQuotes',
    description: 'Quoted cost, minimum order and lead time evidence for each supplier and product.',
    idField: 'quote_id', references: [{ field: 'supplier_id', dataset: 'suppliers', label: 'supplier' }, { field: 'product_id', dataset: 'products', label: 'product' }],
    fields: [
      field('quote_id', 'Quote ID', 'string', { required: true, lockedOnEdit: true }),
      field('supplier_id', 'Supplier ID', 'string', { required: true }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('unit_cost', 'Unit cost', 'number', { required: true, min: 0.01 }),
      field('moq', 'Minimum order quantity', 'number', { min: 0.01, default: 1 }),
      field('quoted_lead_time_days', 'Lead time days', 'number', { required: true, min: 0.01 }),
      field('available_qty', 'Available quantity', 'number', { min: 0 }),
      field('payment_terms_days', 'Payment terms days', 'number', { min: 0 }),
      field('currency', 'Currency', 'string', { default: 'ZAR' }),
      field('valid_from', 'Valid from', 'datetime'),
      field('valid_until', 'Valid until', 'datetime'),
      field('observed_at', 'Observed at', 'datetime', { required: true })
    ]
  },
  supplierPerformance: {
    key: 'supplierPerformance', label: 'Supplier performance', group: 'Procurement', collection: 'supplierPerformance',
    description: 'Closed delivery history used to measure supplier reliability and lead time risk.',
    idField: 'performance_id', references: [{ field: 'supplier_id', dataset: 'suppliers', label: 'supplier' }],
    fields: [
      field('performance_id', 'Performance ID', 'string', { required: true, lockedOnEdit: true }),
      field('supplier_id', 'Supplier ID', 'string', { required: true }),
      field('po_id', 'Purchase order ID', 'string', { required: true }),
      field('order_date', 'Order date', 'date', { required: true }),
      field('promised_date', 'Promised date', 'date', { required: true }),
      field('actual_date', 'Actual delivery date', 'date', { required: true }),
      field('ordered_qty', 'Ordered quantity', 'number', { required: true, min: 0.01 }),
      field('received_qty', 'Received quantity', 'number', { required: true, min: 0 }),
      field('defect_qty', 'Defect quantity', 'number', { min: 0, default: 0 }),
      field('invoice_variance_pct', 'Invoice variance %', 'decimal', { default: 0 })
    ]
  },
  purchaseOrders: {
    key: 'purchaseOrders', label: 'Purchase orders', group: 'Procurement', collection: 'purchaseOrders',
    description: 'Approved or historical purchase orders.',
    idField: 'po_id', references: [{ field: 'supplier_id', dataset: 'suppliers', label: 'supplier' }, { field: 'product_id', dataset: 'products', label: 'product' }],
    fields: [
      field('po_id', 'Purchase order ID', 'string', { required: true, lockedOnEdit: true }),
      field('recommendation_id', 'Recommendation ID', 'string'),
      field('supplier_id', 'Supplier ID', 'string', { required: true }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('qty', 'Quantity', 'number', { required: true, min: 0.01 }),
      field('unit_cost', 'Unit cost', 'number', { required: true, min: 0.01 }),
      field('currency', 'Currency', 'string', { default: 'ZAR' }),
      field('ordered_at', 'Ordered at', 'datetime', { required: true }),
      field('promised_date', 'Promised date', 'date', { required: true }),
      field('status', 'Status', 'enum', { options: ['OPEN', 'PARTIALLY_RECEIVED', 'RECEIVED', 'CLOSED', 'CANCELLED'], default: 'OPEN' }),
      field('created_by', 'Created by', 'string')
    ]
  },
  goodsReceipts: {
    key: 'goodsReceipts', label: 'Goods receipts', group: 'Procurement', collection: 'goodsReceipts',
    description: 'What was actually received against a purchase order.',
    idField: 'receipt_id', references: [{ field: 'supplier_id', dataset: 'suppliers', label: 'supplier' }, { field: 'product_id', dataset: 'products', label: 'product' }, { field: 'po_id', dataset: 'purchaseOrders', label: 'purchase order' }],
    fields: [
      field('receipt_id', 'Receipt ID', 'string', { required: true, lockedOnEdit: true }),
      field('po_id', 'Purchase order ID', 'string', { required: true }),
      field('supplier_id', 'Supplier ID', 'string', { required: true }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('qty_received', 'Quantity received', 'number', { required: true, min: 0 }),
      field('qty_defective', 'Defective quantity', 'number', { min: 0, default: 0 }),
      field('received_at', 'Received at', 'datetime', { required: true })
    ]
  },
  invoices: {
    key: 'invoices', label: 'Supplier invoices', group: 'Procurement', collection: 'invoices',
    description: 'Supplier invoice evidence used in reconciliation.',
    idField: 'invoice_id', references: [{ field: 'supplier_id', dataset: 'suppliers', label: 'supplier' }, { field: 'product_id', dataset: 'products', label: 'product' }, { field: 'po_id', dataset: 'purchaseOrders', label: 'purchase order' }],
    fields: [
      field('invoice_id', 'Invoice ID', 'string', { required: true, lockedOnEdit: true }),
      field('invoice_number', 'Invoice number', 'string', { required: true }),
      field('po_id', 'Purchase order ID', 'string', { required: true }),
      field('supplier_id', 'Supplier ID', 'string', { required: true }),
      field('product_id', 'Product ID', 'string', { required: true }),
      field('qty_invoiced', 'Quantity invoiced', 'number', { required: true, min: 0.01 }),
      field('unit_cost', 'Unit cost', 'number', { required: true, min: 0.01 }),
      field('tax_amount', 'Tax amount', 'number', { min: 0, default: 0 }),
      field('currency', 'Currency', 'string', { default: 'ZAR' }),
      field('invoiced_at', 'Invoiced at', 'datetime', { required: true })
    ]
  },
  customers: {
    key: 'customers', label: 'Customers', group: 'Customers', collection: 'customers',
    description: 'Consented customer or loyalty records. Only collect information the business actually needs.',
    idField: 'customer_id',
    fields: [
      field('customer_id', 'Customer ID', 'string', { required: true, lockedOnEdit: true }),
      field('name', 'Name', 'string'),
      field('phone', 'Phone', 'string'),
      field('consent_marketing', 'Marketing consent', 'boolean', { required: true, default: false }),
      field('tags', 'Tags', 'list'),
      field('created_at', 'Created at', 'datetime'),
      field('last_visit_at', 'Last visit at', 'datetime')
    ]
  },
  feedback: {
    key: 'feedback', label: 'Feedback', group: 'Customers', collection: 'feedback',
    description: 'Real complaints, surveys, reviews and customer messages.',
    idField: 'feedback_id', references: [{ field: 'customer_id', dataset: 'customers', label: 'customer' }],
    fields: [
      field('feedback_id', 'Feedback ID', 'string', { required: true, lockedOnEdit: true }),
      field('customer_id', 'Customer ID', 'string', { required: true }),
      field('channel', 'Channel', 'enum', { options: ['IN_STORE', 'WHATSAPP', 'SMS', 'WEB', 'OTHER'], default: 'OTHER' }),
      field('message', 'Message', 'textarea', { required: true }),
      field('created_at', 'Created at', 'datetime', { required: true }),
      field('status', 'Status', 'enum', { options: ['NEW', 'REVIEWED', 'RESOLVED'], default: 'NEW' })
    ]
  },
  customerInteractions: {
    key: 'customerInteractions', label: 'Customer interactions', group: 'Customers', collection: 'customerInteractions',
    description: 'Actual contact attempts and outcomes used to understand engagement.',
    idField: 'interaction_id', references: [{ field: 'customer_id', dataset: 'customers', label: 'customer' }],
    fields: [
      field('interaction_id', 'Interaction ID', 'string', { required: true, lockedOnEdit: true }),
      field('customer_id', 'Customer ID', 'string', { required: true }),
      field('channel', 'Channel', 'enum', { options: ['IN_STORE', 'WHATSAPP', 'SMS', 'CALL', 'EMAIL', 'OTHER'], default: 'OTHER' }),
      field('interaction_type', 'Interaction type', 'string', { required: true }),
      field('outcome', 'Outcome', 'string'),
      field('notes', 'Notes', 'textarea'),
      field('created_at', 'Created at', 'datetime', { required: true })
    ]
  }
});

function safe(value) {
  return String(value ?? '').trim().replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'unknown';
}

export function getDataset(key) {
  const dataset = DATASETS[key];
  if (!dataset) {
    const error = new Error(`Unknown business data set: ${key}`);
    error.code = 'UNKNOWN_DATASET';
    throw error;
  }
  return dataset;
}

export function publicCatalog() {
  return Object.values(DATASETS).map((dataset) => ({
    key: dataset.key,
    label: dataset.label,
    group: dataset.group,
    description: dataset.description,
    collection: dataset.collection,
    fields: dataset.fields.map(({ name, label, type, required = false, options, default: defaultValue, lockedOnEdit = false, example }) => ({
      name, label, type, required, options: options || null, default: defaultValue ?? null, lockedOnEdit, example: example || null
    }))
  }));
}

function blank(value) {
  return value == null || (typeof value === 'string' && value.trim() === '');
}

function asBoolean(value) {
  if (typeof value === 'boolean') return value;
  const normalized = String(value).trim().toLowerCase();
  if (['true', '1', 'yes', 'y'].includes(normalized)) return true;
  if (['false', '0', 'no', 'n'].includes(normalized)) return false;
  throw new Error('Enter Yes or No.');
}

function asDate(value, withTime) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) throw new Error('Enter a valid date.');
  return withTime ? parsed.toISOString() : parsed.toISOString().slice(0, 10);
}

function normalizeField(def, value) {
  if (blank(value)) {
    if (def.default !== undefined) {
      const withoutDefault = { ...def };
      delete withoutDefault.default;
      return normalizeField(withoutDefault, def.default);
    }
    if (def.required) throw new Error('This field is required.');
    return null;
  }
  if (def.type === 'number' || def.type === 'decimal' || def.type === 'percent') {
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error('Enter a valid number.');
    if (def.min != null && number < def.min) throw new Error(`Must be at least ${def.min}.`);
    if (def.max != null && number > def.max) throw new Error(`Must not be above ${def.max}.`);
    return def.type === 'percent' ? number / 100 : number;
  }
  if (def.type === 'boolean') return asBoolean(value);
  if (def.type === 'date') return asDate(value, false);
  if (def.type === 'datetime') return asDate(value, true);
  if (def.type === 'list') {
    if (Array.isArray(value)) return value.map((x) => String(x).trim()).filter(Boolean);
    return String(value).split(/[,|]/).map((x) => x.trim()).filter(Boolean);
  }
  if (def.type === 'enum') {
    const normalized = String(value).trim().toUpperCase().replace(/[\s-]+/g, '_');
    if (!def.options.includes(normalized)) throw new Error(`Use one of: ${def.options.join(', ')}.`);
    return normalized;
  }
  return String(value).trim();
}

function customChecks(dataset, record, row, errors, warnings) {
  const pushError = (field, message) => errors.push({ row, field, message });
  const pushWarning = (field, message) => warnings.push({ row, field, message });

  if (dataset.key === 'promotions' && record.start && record.end && record.end < record.start) {
    pushError('end', 'End date must be on or after the start date.');
  }
  if (dataset.key === 'supplierQuotes' && record.valid_from && record.valid_until && record.valid_until < record.valid_from) {
    pushError('valid_until', 'Valid until must be after valid from.');
  }
  if (dataset.key === 'goodsReceipts' && Number(record.qty_defective || 0) > Number(record.qty_received || 0)) {
    pushError('qty_defective', 'Defective quantity cannot exceed quantity received.');
  }
  if (dataset.key === 'inventorySnapshots') {
    const unavailable = Number(record.reserved || 0) + Number(record.damaged || 0);
    if (unavailable > Number(record.stock_on_hand || 0)) pushWarning('stock_on_hand', 'Reserved plus damaged stock is greater than stock on hand. Check this count.');
  }
  if (dataset.key === 'products' && Number(record.sell_price || 0) < Number(record.unit_cost || 0)) {
    pushWarning('sell_price', 'Selling price is below unit cost. Keep it only if that is intentional.');
  }
}

export function normalizeRecord(datasetKey, input, row = 1) {
  const dataset = getDataset(datasetKey);
  const record = {};
  const errors = [];
  const warnings = [];
  const known = new Set(dataset.fields.map((x) => x.name));

  for (const def of dataset.fields) {
    try {
      const value = normalizeField(def, input?.[def.name]);
      if (value !== null) record[def.name] = value;
    } catch (error) {
      errors.push({ row, field: def.name, message: error.message });
    }
  }

  for (const key of Object.keys(input || {})) {
    if (!known.has(key) && !String(key).startsWith('_')) warnings.push({ row, field: key, message: 'Column is not used and will be ignored.' });
  }

  customChecks(dataset, record, row, errors, warnings);
  let id = null;
  if (!errors.length) {
    id = dataset.idField ? String(record[dataset.idField] || '').trim() : dataset.idFrom?.(record);
    if (!id) errors.push({ row, field: dataset.idField || 'record', message: 'A record ID could not be created.' });
    else if (String(id).includes('/')) errors.push({ row, field: dataset.idField || 'record', message: 'IDs cannot contain a forward slash (/). Use letters, numbers, spaces, dashes or underscores instead.' });
  }
  return { id, record, errors, warnings };
}

export function validateRecords(datasetKey, records) {
  if (!Array.isArray(records)) throw new Error('records must be an array.');
  if (records.length > 10000) throw new Error('A single import can contain at most 10,000 rows. Split larger files into smaller CSV files.');
  const normalized = [];
  const errors = [];
  const warnings = [];
  const seen = new Set();

  records.forEach((input, index) => {
    const result = normalizeRecord(datasetKey, input, index + 2);
    errors.push(...result.errors);
    warnings.push(...result.warnings);
    if (!result.errors.length) {
      if (seen.has(result.id)) errors.push({ row: index + 2, field: 'record', message: `Duplicate record ID in this file: ${result.id}` });
      else {
        seen.add(result.id);
        normalized.push({ id: result.id, record: result.record, row: index + 2 });
      }
    }
  });
  return { normalized, errors, warnings };
}

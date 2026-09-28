import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App.js';

const h = React.createElement;

const SUPPLIERS = [
  { supplier_id: 'SUP-001', name: 'Ubuntu Wholesale', status: 'ACTIVE', payment_terms_days: 30, currency: 'ZAR' },
  { supplier_id: 'SUP-002', name: 'Mzansi Distribution', status: 'ACTIVE', payment_terms_days: 45, currency: 'ZAR' },
];

const SCORECARD = {
  supplier: { supplier_id: 'SUP-001', name: 'Ubuntu Wholesale' },
  reliability: { score: 0.91, on_time_rate: 0.79, fill_rate: 1.0, defect_rate: 0.02, confidence: 0.88 },
  lead_time: { risk: 'MEDIUM', expected_days: 5, p90_days: 5.7, delay_rate: 0.21, sample_size: 14 },
};

const READY_RECOMMENDATION = {
  recommendation_id: 'REC-ready-1',
  agent_id: 'R4',
  action_type: 'PurchaseRecommendation',
  entity_id: 'SKU-100',
  status: 'READY_FOR_REVIEW',
  risk_level: 'LOW',
  confidence: 0.84,
  action: { supplier_id: 'SUP-002', qty: 260, expected_cost: 4914 },
  rationale: ['R4 selected Mzansi Distribution after combining R1, R2 and R3 evidence.'],
};

const PURCHASE_ORDERS = [
  { po_id: 'PO-DEMO-001', supplier_id: 'SUP-002', product_id: 'SKU-100', qty: 260, unit_cost: 18.9, status: 'OPEN' },
  { po_id: 'PO-DEMO-002', supplier_id: 'SUP-001', product_id: 'SKU-200', qty: 40, unit_cost: 42, status: 'OPEN' },
];

const DASHBOARD = {
  active_suppliers: 3,
  pending_approvals: 1,
  open_purchase_orders: 2,
  procurement_exceptions: 0,
  purchase_order_value: 6594,
  agent_status: [
    { agent_id: 'R1', name: 'Supplier Comparator', version: '1.0.0-r1', last_error: null },
    { agent_id: 'R2', name: 'Supplier Reliability', version: '1.0.0-r2', last_error: null },
    { agent_id: 'R3', name: 'Lead-Time Risk', version: '1.0.0-r3', last_error: null },
    { agent_id: 'R4', name: 'Purchase Order Recommender', version: '1.0.0-r4', last_error: null },
    { agent_id: 'R5', name: 'Delivery & Invoice Reconciliation', version: '1.0.0-r5', last_error: null },
  ],
};

/**
 * Routes are matched by "METHOD path-suffix". A handler may be a value or a
 * function; returning an Error instance produces a failed HTTP response.
 */
function installApi(routes) {
  global.fetch = vi.fn(async (url, init = {}) => {
    const method = (init.method || 'GET').toUpperCase();
    const path = String(url).replace(/^.*\/api\/v1/, '');
    const key = Object.keys(routes).find(k => {
      const [routeMethod, routePath] = k.split(' ');
      return routeMethod === method && path === routePath;
    });
    if (!key) return { ok: false, status: 404, json: async () => ({ detail: `No mock for ${method} ${path}` }) };
    const handler = routes[key];
    const body = typeof handler === 'function' ? handler() : handler;
    if (body instanceof Error) {
      return { ok: false, status: 500, json: async () => ({ detail: body.message }) };
    }
    return { ok: true, status: 200, json: async () => body };
  });
}

async function goTo(pageName) {
  fireEvent.click(screen.getByRole('button', { name: pageName }));
}

beforeEach(() => {
  installApi({ 'GET /dashboard': DASHBOARD });
});

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

describe('Dashboard', () => {
  it('renders procurement KPIs once the dashboard resolves', async () => {
    render(h(App));
    expect(await screen.findByText('3')).toBeInTheDocument();
    expect(screen.getByText('Active suppliers')).toBeInTheDocument();
    expect(screen.getByText('Open POs')).toBeInTheDocument();
  });

  it('lists all five procurement agents as ready', async () => {
    render(h(App));
    expect(await screen.findByText('R1 · Supplier Comparator')).toBeInTheDocument();
    expect(screen.getByText('R5 · Delivery & Invoice Reconciliation')).toBeInTheDocument();
    expect(screen.getAllByText('READY')).toHaveLength(5);
  });

  it('shows the API error message when the dashboard request fails', async () => {
    installApi({ 'GET /dashboard': () => new Error('Backend unavailable') });
    render(h(App));
    expect(await screen.findByText('Backend unavailable')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Supplier intelligence (R1 inputs, R2/R3 outputs)
// ---------------------------------------------------------------------------

describe('Supplier intelligence', () => {
  it('renders the supplier list', async () => {
    installApi({ 'GET /dashboard': DASHBOARD, 'GET /data/suppliers': SUPPLIERS });
    render(h(App));
    await goTo('Suppliers');

    expect(await screen.findByText('Ubuntu Wholesale')).toBeInTheDocument();
    expect(screen.getByText('Mzansi Distribution')).toBeInTheDocument();
    expect(screen.getByText('45 days')).toBeInTheDocument();
  });

  it('renders an empty supplier table without crashing', async () => {
    installApi({ 'GET /dashboard': DASHBOARD, 'GET /data/suppliers': [] });
    render(h(App));
    await goTo('Suppliers');

    expect(await screen.findByText('Supplier intelligence')).toBeInTheDocument();
    expect(screen.queryByText('Ubuntu Wholesale')).not.toBeInTheDocument();
  });

  it('renders the R2 reliability and R3 lead-time scorecard on demand', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /data/suppliers': SUPPLIERS,
      'GET /suppliers/SUP-001/scorecard': SCORECARD,
    });
    render(h(App));
    await goTo('Suppliers');

    fireEvent.click((await screen.findAllByRole('button', { name: 'View scorecard' }))[0]);

    expect(await screen.findByText('R2 · Ubuntu Wholesale')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
    expect(screen.getByText('79%')).toBeInTheDocument();
    expect(screen.getByText('R3 · Lead-time risk')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
    expect(screen.getByText('5.7 days')).toBeInTheDocument();
  });

  it('surfaces a scorecard API failure without losing the supplier table', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /data/suppliers': SUPPLIERS,
      'GET /suppliers/SUP-001/scorecard': () => new Error('Scorecard unavailable'),
    });
    render(h(App));
    await goTo('Suppliers');

    fireEvent.click((await screen.findAllByRole('button', { name: 'View scorecard' }))[0]);

    expect(await screen.findByText('Scorecard unavailable')).toBeInTheDocument();
    expect(screen.getByText('Ubuntu Wholesale')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// R4 recommendation rendering + approval controls
// ---------------------------------------------------------------------------

describe('R4 recommendations', () => {
  it('renders recommendation evidence, confidence, risk and status', async () => {
    installApi({ 'GET /dashboard': DASHBOARD, 'GET /recommendations': [READY_RECOMMENDATION] });
    render(h(App));
    await goTo('Recommendations');

    const card = (await screen.findByText('SKU-100')).closest('article');
    expect(within(card).getByText('R4 · PurchaseRecommendation')).toBeInTheDocument();
    expect(within(card).getByText('SUP-002')).toBeInTheDocument();
    expect(within(card).getByText('260')).toBeInTheDocument();
    expect(within(card).getByText('84%')).toBeInTheDocument();
    expect(within(card).getByText('LOW')).toBeInTheDocument();
    expect(within(card).getByText('READY_FOR_REVIEW')).toBeInTheDocument();
    expect(within(card).getByText(/R4 selected Mzansi Distribution/)).toBeInTheDocument();
  });

  it('shows no recommendation cards when none exist', async () => {
    installApi({ 'GET /dashboard': DASHBOARD, 'GET /recommendations': [] });
    render(h(App));
    await goTo('Recommendations');

    expect(await screen.findByText('R4 purchase recommendation')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('offers approve and reject controls only while awaiting review', async () => {
    installApi({ 'GET /dashboard': DASHBOARD, 'GET /recommendations': [READY_RECOMMENDATION] });
    render(h(App));
    await goTo('Recommendations');

    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create purchase order' })).not.toBeInTheDocument();
  });

  it('hides the execute control for a rejected recommendation', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /recommendations': [{ ...READY_RECOMMENDATION, status: 'REJECTED' }],
    });
    render(h(App));
    await goTo('Recommendations');

    expect(await screen.findByText('REJECTED')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create purchase order' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('reveals the purchase-order control only after approval', async () => {
    let status = 'READY_FOR_REVIEW';
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /recommendations': () => [{ ...READY_RECOMMENDATION, status }],
      'POST /recommendations/REC-ready-1/decision': () => {
        status = 'APPROVED';
        return { ...READY_RECOMMENDATION, status };
      },
    });
    render(h(App));
    await goTo('Recommendations');

    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));

    expect(await screen.findByRole('button', { name: 'Create purchase order' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('sends an APPROVED decision with a reason to the API', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /recommendations': [READY_RECOMMENDATION],
      'POST /recommendations/REC-ready-1/decision': { ...READY_RECOMMENDATION, status: 'APPROVED' },
    });
    render(h(App));
    await goTo('Recommendations');

    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([url]) => String(url).includes('/decision'));
      expect(call).toBeDefined();
      const payload = JSON.parse(call[1].body);
      expect(payload.decision).toBe('APPROVED');
      expect(payload.reason).toBeTruthy();
    });
  });

  it('sends a REJECTED decision when the reject control is used', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /recommendations': [READY_RECOMMENDATION],
      'POST /recommendations/REC-ready-1/decision': { ...READY_RECOMMENDATION, status: 'REJECTED' },
    });
    render(h(App));
    await goTo('Recommendations');

    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([url]) => String(url).includes('/decision'));
      expect(JSON.parse(call[1].body).decision).toBe('REJECTED');
    });
  });

  it('calls the execute endpoint when creating the purchase order', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /recommendations': [{ ...READY_RECOMMENDATION, status: 'APPROVED' }],
      'POST /recommendations/REC-ready-1/execute': { po_id: 'PO-NEW-001' },
    });
    render(h(App));
    await goTo('Recommendations');

    fireEvent.click(await screen.findByRole('button', { name: 'Create purchase order' }));

    await waitFor(() => {
      expect(global.fetch.mock.calls.some(([url]) => String(url).includes('/execute'))).toBe(true);
    });
  });

  it('surfaces a governance rejection from the execute endpoint', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /recommendations': [{ ...READY_RECOMMENDATION, status: 'APPROVED' }],
      'POST /recommendations/REC-ready-1/execute': () =>
        new Error('Recommendation must be APPROVED or MODIFIED before execution.'),
    });
    render(h(App));
    await goTo('Recommendations');

    fireEvent.click(await screen.findByRole('button', { name: 'Create purchase order' }));

    expect(
      await screen.findByText('Recommendation must be APPROVED or MODIFIED before execution.'),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// R5 reconciliation
// ---------------------------------------------------------------------------

describe('R5 reconciliation', () => {
  const baseRoutes = {
    'GET /dashboard': DASHBOARD,
    'GET /data/purchase_orders': PURCHASE_ORDERS,
  };

  it('renders the purchase order list', async () => {
    installApi(baseRoutes);
    render(h(App));
    await goTo('Purchase Orders');

    expect(await screen.findByText('PO-DEMO-001')).toBeInTheDocument();
    expect(screen.getByText('PO-DEMO-002')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Run R5' })).toHaveLength(2);
  });

  it('renders a clean three-way MATCH result', async () => {
    installApi({
      ...baseRoutes,
      'POST /procurement/reconcile/PO-DEMO-001': {
        recommendation_id: 'REC-r5-clean',
        entity_id: 'PO-DEMO-001',
        status: 'APPROVED',
        action: { match_status: 'MATCH', exception_types: [], financial_variance: 0 },
      },
    });
    render(h(App));
    await goTo('Purchase Orders');

    fireEvent.click((await screen.findAllByRole('button', { name: 'Run R5' }))[0]);

    expect(await screen.findByText('R5 result · PO-DEMO-001')).toBeInTheDocument();
    expect(screen.getByText('MATCH')).toBeInTheDocument();
    expect(screen.getByText('No reconciliation exceptions detected.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close PO' })).toBeInTheDocument();
  });

  it('renders a MISMATCH result with every detected exception type', async () => {
    installApi({
      ...baseRoutes,
      'POST /procurement/reconcile/PO-DEMO-002': {
        recommendation_id: 'REC-r5-exception',
        output_id: 'REC-r5-exception',
        entity_id: 'PO-DEMO-002',
        status: 'APPROVED',
        action_recommendation_id: 'REC-review-1',
        action: {
          match_status: 'MISMATCH',
          exception_types: ['UNDER_DELIVERY', 'PRICE_VARIANCE', 'DEFECTIVE_GOODS', 'LATE_DELIVERY'],
          financial_variance: 60,
        },
      },
    });
    render(h(App));
    await goTo('Purchase Orders');

    fireEvent.click((await screen.findAllByRole('button', { name: 'Run R5' }))[1]);

    expect(await screen.findByText('R5 result · PO-DEMO-002')).toBeInTheDocument();
    expect(screen.getByText('MISMATCH')).toBeInTheDocument();
    expect(
      screen.getByText(/UNDER_DELIVERY, PRICE_VARIANCE, DEFECTIVE_GOODS, LATE_DELIVERY/),
    ).toBeInTheDocument();
  });

  it('requires explicit acceptance before closing a mismatched PO', async () => {
    installApi({
      ...baseRoutes,
      'POST /procurement/reconcile/PO-DEMO-002': {
        recommendation_id: 'REC-r5-exception',
        output_id: 'REC-r5-exception',
        entity_id: 'PO-DEMO-002',
        status: 'APPROVED',
        action_recommendation_id: 'REC-review-1',
        action: { match_status: 'MISMATCH', exception_types: ['UNDER_DELIVERY'], financial_variance: 60 },
      },
    });
    render(h(App));
    await goTo('Purchase Orders');

    fireEvent.click((await screen.findAllByRole('button', { name: 'Run R5' }))[1]);

    expect(await screen.findByRole('button', { name: 'Accept result & close PO' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Close PO' })).not.toBeInTheDocument();
  });

  it('approves the derived review action — not the R5 evidence — before closing', async () => {
    installApi({
      ...baseRoutes,
      'POST /procurement/reconcile/PO-DEMO-002': {
        recommendation_id: 'REC-r5-exception',
        output_id: 'REC-r5-exception',
        entity_id: 'PO-DEMO-002',
        status: 'APPROVED',
        action_recommendation_id: 'REC-review-1',
        action: { match_status: 'MISMATCH', exception_types: ['UNDER_DELIVERY'], financial_variance: 60 },
      },
      'POST /recommendations/REC-review-1/decision': { status: 'APPROVED' },
      'POST /procurement/close/PO-DEMO-002/REC-r5-exception': { purchase_order: { status: 'CLOSED' } },
    });
    render(h(App));
    await goTo('Purchase Orders');

    fireEvent.click((await screen.findAllByRole('button', { name: 'Run R5' }))[1]);
    fireEvent.click(await screen.findByRole('button', { name: 'Accept result & close PO' }));

    await waitFor(() => {
      const urls = global.fetch.mock.calls.map(([u]) => String(u));
      expect(urls.some(u => u.includes('/recommendations/REC-review-1/decision'))).toBe(true);
      expect(urls.some(u => u.includes('/recommendations/REC-r5-exception/decision'))).toBe(false);
      expect(urls.some(u => u.includes('/procurement/close/PO-DEMO-002/REC-r5-exception'))).toBe(true);
    });
  });

  it('closes a clean MATCH directly without any approval call', async () => {
    installApi({
      ...baseRoutes,
      'POST /procurement/reconcile/PO-DEMO-001': {
        recommendation_id: 'REC-r5-clean',
        output_id: 'REC-r5-clean',
        entity_id: 'PO-DEMO-001',
        status: 'APPROVED',
        action: { match_status: 'MATCH', exception_types: [], financial_variance: 0 },
      },
      'POST /procurement/close/PO-DEMO-001/REC-r5-clean': { purchase_order: { status: 'CLOSED' } },
    });
    render(h(App));
    await goTo('Purchase Orders');

    fireEvent.click((await screen.findAllByRole('button', { name: 'Run R5' }))[0]);
    fireEvent.click(await screen.findByRole('button', { name: 'Close PO' }));

    await waitFor(() => {
      const urls = global.fetch.mock.calls.map(([u]) => String(u));
      expect(urls.some(u => u.includes('/decision'))).toBe(false);
      expect(urls.some(u => u.includes('/procurement/close/PO-DEMO-001/REC-r5-clean'))).toBe(true);
    });
  });

  it('shows an error when reconciliation evidence is missing', async () => {
    installApi({
      ...baseRoutes,
      'POST /procurement/reconcile/PO-DEMO-001': () =>
        new Error('Receipt and invoice evidence are required before closing'),
    });
    render(h(App));
    await goTo('Purchase Orders');

    fireEvent.click((await screen.findAllByRole('button', { name: 'Run R5' }))[0]);

    expect(
      await screen.findByText('Receipt and invoice evidence are required before closing'),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Imports and audit
// ---------------------------------------------------------------------------

describe('Data imports', () => {
  it('shows the empty state before any import runs', async () => {
    installApi({ 'GET /dashboard': DASHBOARD });
    render(h(App));
    await goTo('Data Imports');

    expect(await screen.findByText('No import has been run in this session.')).toBeInTheDocument();
  });

  it('disables the import control until a file is chosen', async () => {
    installApi({ 'GET /dashboard': DASHBOARD });
    render(h(App));
    await goTo('Data Imports');

    expect(await screen.findByRole('button', { name: 'Import & validate' })).toBeDisabled();
  });
});

describe('Audit trail', () => {
  it('renders governance events with actor and entity', async () => {
    installApi({
      'GET /dashboard': DASHBOARD,
      'GET /audit': [
        {
          event_id: 'EVT-1',
          created_at: '2026-09-09T10:24:13.000000',
          event_type: 'recommendation.decision',
          entity_type: 'recommendation',
          entity_id: 'REC-ready-1',
          actor_id: 'demo:manager@example.com',
        },
      ],
    });
    render(h(App));
    await goTo('Audit');

    expect(await screen.findByText('recommendation.decision')).toBeInTheDocument();
    expect(screen.getByText('recommendation:REC-ready-1')).toBeInTheDocument();
    expect(screen.getByText('demo:manager@example.com')).toBeInTheDocument();
  });

  it('renders an empty audit table without crashing', async () => {
    installApi({ 'GET /dashboard': DASHBOARD, 'GET /audit': [] });
    render(h(App));
    await goTo('Audit');

    expect(await screen.findByText('Governance audit trail')).toBeInTheDocument();
  });
});

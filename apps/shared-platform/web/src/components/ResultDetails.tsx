import type { ReactNode } from 'react';

const hiddenKeys = new Set([
  'schema_version', 'source_version', 'model_or_rule_version', 'formula_version',
  'run_id', 'analysis_run_id', 'correlation_id', 'output_id', 'state_id'
]);

const labels: Record<string, string> = {
  product_id: 'Product', customer_id: 'Customer', supplier_id: 'Supplier', po_id: 'Purchase order',
  expected_qty: 'Expected demand', lower_bound: 'Lower estimate', upper_bound: 'Upper estimate',
  confidence: 'Confidence', horizon_days: 'Forecast period', stock_on_hand: 'Stock on hand',
  available_stock: 'Available stock', in_transit: 'On the way', days_of_supply: 'Days of supply',
  stock_status: 'Stock status', safety_stock: 'Safety stock', reorder_point: 'Reorder point',
  reorder_needed: 'Reorder needed', recommended_qty: 'Recommended quantity', minimum_price: 'Minimum safe price',
  current_price: 'Current price', proposed_price: 'Proposed price', change_pct: 'Price change',
  margin_after_pct: 'Margin after change', market_average: 'Market average', elasticity: 'Price sensitivity',
  expected_cost: 'Expected cost', eta_days: 'Expected arrival', risk: 'Risk', risk_level: 'Risk',
  decision_score: 'Decision score', reliability_score: 'Supplier reliability', supplier_score: 'Supplier score',
  lead_time_risk: 'Lead time risk', segment: 'Customer segment', risk_band: 'Retention risk',
  offer_pct: 'Offer', reason: 'Reason', status: 'Status', actionable: 'Action available',
  fairness_checks: 'Checks completed', drivers: 'Forecast drivers', detected_patterns: 'Patterns detected',
  observation_count: 'Observations', distinct_price_count: 'Distinct prices', market_min: 'Lowest observed price',
  market_max: 'Highest observed price', market_position_pct: 'Position vs market', effective_unit_cost: 'Effective unit cost',
  margin_floor_pct: 'Minimum margin', candidate_price: 'Candidate price', discount_pct: 'Discount',
  days_of_cover: 'Days of cover', days_to_expiry: 'Days to expiry', sales_velocity: 'Sales per day',
  exception_types: 'Exceptions', match_status: 'Reconciliation', financial_variance: 'Financial variance'
};

function humanize(key: string) {
  return labels[key] || key
    .replace(/\.v\d+$/i, '')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function isInternal(key: string) {
  const normalized = key.toLowerCase();
  return hiddenKeys.has(normalized) || normalized.endsWith('_version') || normalized === 'generated_at' || normalized === 'evaluated_at';
}

function formatPrimitive(key: string, value: unknown): ReactNode {
  if (value == null || value === '') return 'Not available';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') {
    if (/(_pct|confidence|score|rate)$/.test(key) && Math.abs(value) <= 1) return `${Math.round(value * 1000) / 10}%`;
    if (/price|cost|financial|market_|minimum_price|unit_cost/.test(key)) return new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR', maximumFractionDigits: 2 }).format(value);
    return new Intl.NumberFormat('en-ZA', { maximumFractionDigits: 2 }).format(value);
  }
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  }
  if (typeof value === 'string') return value.replace(/\.v\d+$/i, '').replaceAll('_', ' ');
  return String(value);
}

function Value({ name, value, depth = 0 }: { name: string; value: unknown; depth?: number }) {
  if (Array.isArray(value)) {
    if (!value.length) return <span className="result-empty">None</span>;
    if (value.every((item) => item == null || ['string', 'number', 'boolean'].includes(typeof item))) {
      return <div className="result-tags">{value.slice(0, 12).map((item, index) => <span key={index}>{formatPrimitive(name, item)}</span>)}</div>;
    }
    return <div className="result-nested-list">{value.slice(0, 6).map((item, index) => <Value key={index} name={`${humanize(name)} ${index + 1}`} value={item} depth={depth + 1} />)}</div>;
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).filter(([key]) => !isInternal(key));
    if (!entries.length) return <span className="result-empty">No additional details</span>;
    return (
      <div className={depth ? 'result-subgroup' : 'result-grid'}>
        {entries.slice(0, 18).map(([key, item]) => (
          <div className={item && typeof item === 'object' ? 'result-field result-field-wide' : 'result-field'} key={key}>
            <span>{humanize(key)}</span>
            <div>{item && typeof item === 'object' ? <Value name={key} value={item} depth={depth + 1} /> : <strong>{formatPrimitive(key, item)}</strong>}</div>
          </div>
        ))}
      </div>
    );
  }
  return <strong>{formatPrimitive(name, value)}</strong>;
}

export function friendlyOutputType(value?: string) {
  const map: Record<string, string> = {
    CleanDemandSeries: 'Clean demand history', SeasonalityProfile: 'Seasonality profile', DemandSignalAdjustment: 'Demand signals',
    DemandForecast: 'Demand forecast', ForecastQualityAlert: 'Forecast quality', InventoryPosition: 'Inventory position',
    ReorderNeed: 'Reorder need', SafetyStockTarget: 'Safety stock target', StockRiskAlert: 'Stock risk', InventoryException: 'Inventory exception',
    CompetitorPriceSignal: 'Market price signal', AllowedPriceRange: 'Safe price range', ElasticityEstimate: 'Price sensitivity',
    PromoPriceCandidate: 'Promotion price', PriceRecommendation: 'Price recommendation', SupplierComparison: 'Supplier comparison',
    SupplierReliabilityScore: 'Supplier reliability', LeadTimeRisk: 'Lead time risk', PurchaseRecommendation: 'Purchase recommendation',
    NoPurchaseRequired: 'Purchase check', ProcurementException: 'Delivery and invoice check', CustomerSegment: 'Customer segment',
    RetentionRisk: 'Retention risk', PromotionRecommendation: 'Customer promotion', CustomerAction: 'Customer action', FeedbackInsight: 'Feedback insight'
  };
  return map[value || ''] || humanize(value || 'Result');
}

export function ResultDetails({ value }: { value: unknown }) {
  return <Value name="result" value={value} />;
}

import { useParams } from 'react-router-dom';
import { Empty } from '../components/Empty';
import { PageHeader } from '../components/PageHeader';
import { StatusPill } from '../components/StatusPill';
import { ResultDetails, friendlyOutputType } from '../components/ResultDetails';
import { useWorkspace } from '../context';

const labels: Record<string, { title: string; description: string }> = {
  demand: { title: 'Demand', description: 'Sales history, seasonality, event signals, forecasts and forecast quality.' },
  inventory: { title: 'Inventory', description: 'Stock position, reorder need, safety stock, slow stock and exceptions.' },
  pricing: { title: 'Pricing', description: 'Market observations, margin protection, elasticity, promotions and governed price actions.' },
  procurement: { title: 'Procurement', description: 'Supplier comparison, reliability, lead-time risk, purchase recommendations and reconciliation.' },
  'customer-engagement': { title: 'Customers', description: 'Segmentation, retention risk, promotions, next-best actions and feedback.' }
};

export function DomainPage() {
  const { domain = '' } = useParams();
  const { data } = useWorkspace();
  const meta = labels[domain] || { title: domain, description: '' };
  const caps = (data?.capabilities || []).filter((x) => x.domain === domain);
  const states = (data?.state || []).filter((x) => x.domain === domain);

  return (
    <>
      <PageHeader eyebrow="Domain" title={meta.title} description={meta.description} />

      <section className="section">
        <div className="section-head"><div><span className="eyebrow">Functions</span><h2>What this area handles</h2></div></div>
        <div className="capability-list">
          {caps.map((cap) => (
            <div className="capability-row" key={cap.capabilityId}>
              <div className="cap-id">{cap.capabilityId}</div>
              <div className="cap-main">
                <strong>{cap.name}</strong>
                <span>{cap.primaryOutput}</span>
              </div>
              <div className="cap-status">
                <StatusPill value={cap.liveStatus || cap.implementationStatus} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-head"><div><span className="eyebrow">Latest</span><h2>Results</h2></div><span className="section-count">{states.length}</span></div>
        {states.length ? (
          <div className="state-list">
            {states.map((state) => (
              <details className="state-row" key={state.id}>
                <summary>
                  <div><strong>{friendlyOutputType(state.outputType)}</strong><span>{state.entityType} · {state.entityId}</span></div>
                  <div className="domain-meta"><StatusPill value={state.riskLevel} /><span>{typeof state.confidence === 'number' ? `${Math.round(state.confidence * 100)}%` : 'Not available'}</span></div>
                </summary>
                <div className="state-details"><ResultDetails value={state.payload || {}} /></div>
              </details>
            ))}
          </div>
        ) : <Empty title="No results are available for this area yet" />}
      </section>
    </>
  );
}

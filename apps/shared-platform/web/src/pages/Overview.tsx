import { useWorkspace } from '../context';
import { Empty } from '../components/Empty';
import { PageHeader } from '../components/PageHeader';
import { StatusPill } from '../components/StatusPill';
import { Link } from 'react-router-dom';
import { friendlyEventName, friendlySource } from '../lib/display';

const domains = [
  ['demand', 'Demand', 'Forecasting and signal quality'],
  ['inventory', 'Inventory', 'Stock position and replenishment'],
  ['pricing', 'Pricing', 'Margin, market and price decisions'],
  ['procurement', 'Procurement', 'Supplier and purchase lifecycle'],
  ['customer-engagement', 'Customers', 'Retention and customer actions']
];

export function Overview() {
  const { data, loading, error, refresh } = useWorkspace();

  if (loading && !data) return <div className="loading-line">Loading workspace…</div>;
  if (error && !data) return <Empty title="Workspace API is unavailable">{error}</Empty>;
  if (!data) return null;

  const businessName = data.business.name || data.business.id;
  const reviewItems = data.recommendations.filter((x) => ['READY_FOR_REVIEW', 'READY_FOR_SECOND_REVIEW'].includes(x.status)).slice(0, 5);
  const recent = data.events.slice(0, 6);

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title={businessName}
        description="One operational view across the five business domains."
        action={
          <button className="button secondary" onClick={() => void refresh()}>
            Refresh
          </button>
        }
      />

      {!data.connected ? (
        <div className="notice">
          <strong>Workspace connection is unavailable.</strong>
          <span>Operational data cannot be loaded right now. Your saved business data has not been replaced or simulated.</span>
        </div>
      ) : null}

      {data.connected && data.analysis?.status === 'NEEDS_PROCESSING' ? (
        <div className="notice action-notice">
          <div><strong>New or changed business data is waiting to be processed.</strong><span>Run processing to refresh forecasts, stock decisions, supplier analysis, pricing and customer results.</span></div>
          <Link className="button primary" to="/process">Process data</Link>
        </div>
      ) : null}
      {data.connected && data.analysis?.status === 'FAILED' ? (
        <div className="notice error-notice">
          <div><strong>The latest processing run needs attention.</strong><span>{data.analysis.lastError || 'Your last successful results remain active until processing succeeds.'}</span></div>
          <Link className="button secondary" to="/process">Review processing</Link>
        </div>
      ) : null}

      <section className="metric-strip" aria-label="Workspace summary">
        <div><span>Needs review</span><strong>{data.summary.reviewCount}</strong></div>
        <div><span>Running now</span><strong>{data.summary.runningCount}</strong></div>
        <div><span>Failed runs</span><strong>{data.summary.failedCount}</strong></div>
        <div><span>Recent events</span><strong>{data.summary.recentEventCount}</strong></div>
      </section>

      <section className="section">
        <div className="section-head">
          <div><span className="eyebrow">Operations</span><h2>Domain status</h2></div>
        </div>
        <div className="domain-list">
          {domains.map(([key, name, description]) => {
            const caps = data.capabilities.filter((x) => x.domain === key);
            const failed = caps.some((x) => x.liveStatus === 'FAILED');
            const running = caps.some((x) => x.liveStatus === 'RUNNING');
            const waiting = caps.some((x) => x.liveStatus === 'SKIPPED' || x.liveStatus === 'IDLE');
            const status = failed ? 'FAILED' : running ? 'RUNNING' : waiting ? 'PARTIAL' : 'READY';
            const outputs = data.state.filter((x) => x.domain === key).length;
            return (
              <div className="domain-row" key={key}>
                <div>
                  <strong>{name}</strong>
                  <span>{description}</span>
                </div>
                <div className="domain-meta">
                  <span>{caps.length} capabilities</span>
                  <span>{outputs} results</span>
                  <StatusPill value={status} />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="split-grid">
        <div className="section compact">
          <div className="section-head"><div><span className="eyebrow">Decision queue</span><h2>Needs your attention</h2></div></div>
          {reviewItems.length ? reviewItems.map((item) => (
            <div className="line-item" key={item.id}>
              <div>
                <strong>{item.recommendationType || item.capabilityId || 'Recommendation'}</strong>
                <span>{item.subjectId || item.id}</span>
              </div>
              <StatusPill value={item.riskLevel || item.status} />
            </div>
          )) : <Empty title="No recommendations waiting for review" />}
        </div>

        <div className="section compact">
          <div className="section-head"><div><span className="eyebrow">Latest</span><h2>Activity</h2></div></div>
          {recent.length ? recent.map((event) => (
            <div className="line-item" key={event.id}>
              <div>
                <strong>{friendlyEventName(event.eventType)}</strong>
                <span>{friendlySource(event.sourceAgent, data.capabilities)} · {event.createdAt ? new Date(event.createdAt).toLocaleString() : 'Time unavailable'}</span>
              </div>
              <StatusPill value={event.status || 'RECORDED'} />
            </div>
          )) : <Empty title="No recent events" />}
        </div>
      </section>
    </>
  );
}

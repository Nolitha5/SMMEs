import { useEffect, useState } from 'react';
import { Play, RotateCcw } from 'lucide-react';
import { Empty } from '../components/Empty';
import { PageHeader } from '../components/PageHeader';
import { StatusPill } from '../components/StatusPill';
import { loadProcessingReadiness, processBusinessData } from '../lib/api';
import { useWorkspace } from '../context';
import type { ProcessingReadiness, ProcessingResult } from '../types';

function statusLabel(status: string) {
  if (status === 'CURRENT') return 'Up to date';
  if (status === 'NEEDS_PROCESSING') return 'Changes waiting';
  if (status === 'PROCESSING') return 'Processing';
  if (status === 'FAILED') return 'Needs attention';
  return status;
}

export function ProcessPage() {
  const { refresh } = useWorkspace();
  const [readiness, setReadiness] = useState<ProcessingReadiness | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessingResult | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try { setReadiness(await loadProcessingReadiness()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setLoading(false); }
  }

  useEffect(() => { void reload(); }, []);

  async function run() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const processed = await processBusinessData();
      setResult(processed);
      await Promise.all([reload(), refresh()]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      await reload().catch(() => undefined);
    } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader
        eyebrow="Operations"
        title="Process data"
        description="Turn saved business records into forecasts, stock decisions, supplier analysis, price recommendations and customer actions."
        action={
          <button className="button secondary" onClick={() => void reload()} disabled={loading || busy}>
            <RotateCcw size={15} /> Check readiness
          </button>
        }
      />

      {loading && !readiness ? <div className="loading-line">Checking your business data…</div> : null}
      {error ? <div className="notice error-notice"><strong>Processing needs attention.</strong><span>{error}</span></div> : null}

      {readiness ? (
        <>
          <section className="process-lead">
            <div>
              <span className="eyebrow">Analysis status</span>
              <h2>{statusLabel(readiness.analysisStatus)}</h2>
              <p>
                {readiness.analysisStatus === 'CURRENT'
                  ? 'The latest saved business data has already been processed.'
                  : 'Saved source records are ready to be analysed. Processing never invents missing business records.'}
              </p>
              <div className="process-times">
                <span>Last data change <strong>{readiness.dataUpdatedAt ? new Date(readiness.dataUpdatedAt).toLocaleString() : 'Not recorded yet'}</strong></span>
                <span>Last completed analysis <strong>{readiness.lastProcessedAt ? new Date(readiness.lastProcessedAt).toLocaleString() : 'Not processed yet'}</strong></span>
              </div>
            </div>
            <button className="button primary process-button" onClick={() => void run()} disabled={!readiness.canProcess || busy || readiness.analysisStatus === 'PROCESSING'}>
              <Play size={16} /> {busy ? 'Processing business data…' : 'Process business data'}
            </button>
          </section>

          {!readiness.canProcess ? (
            <div className="notice"><strong>Products and sales history are required first.</strong><span>Add them in Business data. Other areas can remain partial and will safely report what is missing.</span></div>
          ) : null}

          <section className="section">
            <div className="section-head"><div><span className="eyebrow">Readiness</span><h2>Five business areas</h2></div></div>
            <div className="process-domain-list">
              {readiness.domains.map((domain) => (
                <div className="process-domain-row" key={domain.key}>
                  <div className="process-domain-main">
                    <strong>{domain.label}</strong>
                    <span>{domain.detail}</span>
                    {domain.issues.length ? <small>{domain.issues.join(' ')}</small> : null}
                  </div>
                  <StatusPill value={domain.status} />
                </div>
              ))}
            </div>
          </section>

          <section className="section process-flow-section">
            <div className="section-head"><div><span className="eyebrow">Processing order</span><h2>How your records are used</h2></div></div>
            <div className="process-flow-rows">
              <div><strong>Demand</strong><span>Sales history, seasonality, promotions and local events become product forecasts.</span></div>
              <div><strong>Inventory</strong><span>Forecasts and stock counts become stock position, safety stock, reorder need and stock risk.</span></div>
              <div><strong>Procurement</strong><span>Supplier quotes and delivery history are combined with reorder needs before purchase recommendations are created.</span></div>
              <div><strong>Pricing</strong><span>Costs, margins, market observations, demand and stock risk are checked before any price recommendation reaches approval.</span></div>
              <div><strong>Customers</strong><span>Consented customer history and feedback are analysed only after product and stock context is available.</span></div>
            </div>
          </section>

          {result ? (
            <section className="section success-section">
              <div className="section-head"><div><span className="eyebrow">Complete</span><h2>Business data processed</h2></div><StatusPill value="SUCCEEDED" /></div>
              <div className="metric-strip process-summary">
                <div><span>Business areas</span><strong>{result.summary.completedDomains}</strong></div>
                <div><span>Results</span><strong>{result.summary.results}</strong></div>
                <div><span>Needs review</span><strong>{result.summary.recommendations}</strong></div>
                <div><span>Items waiting for data</span><strong>{result.summary.skippedResults}</strong></div>
              </div>
              <p className="muted">The dashboard has been refreshed. Open each business area for results and Approvals for actions that require a person to decide.</p>
            </section>
          ) : null}
        </>
      ) : !loading ? <Empty title="Processing readiness could not be loaded" /> : null}
    </>
  );
}

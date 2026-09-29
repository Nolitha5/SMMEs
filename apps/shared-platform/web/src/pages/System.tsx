import { Empty } from '../components/Empty';
import { PageHeader } from '../components/PageHeader';
import { StatusPill } from '../components/StatusPill';
import { useWorkspace } from '../context';

export function SystemPage() {
  const { data } = useWorkspace();
  const runs = data?.runs || [];
  const capNames = new Map((data?.capabilities || []).map((cap) => [cap.capabilityId, cap.name]));

  return (
    <>
      <PageHeader eyebrow="Platform" title="System" description="Workspace health and recent operational activity." />

      <section className="section">
        <div className="section-head"><div><span className="eyebrow">Workspace</span><h2>Platform status</h2></div><StatusPill value={data?.connected ? 'READY' : 'FAILED'} /></div>
        <div className="readiness">
          {(data?.backendStatus.remainingBeforeProductionDeploy || []).length ? (data?.backendStatus.remainingBeforeProductionDeploy || []).map((item, index) => (
            <div className="readiness-row" key={item}><span>{String(index + 1).padStart(2, '0')}</span><strong>Setup action required</strong></div>
          )) : <div className="readiness-row"><span>OK</span><strong>Core services are connected and ready.</strong></div>}
        </div>
      </section>

      <section className="section">
        <div className="section-head"><div><span className="eyebrow">Activity</span><h2>Recent runs</h2></div></div>
        {runs.length ? (
          <div className="table">
            <div className="table-head"><span>Capability</span><span>Domain</span><span>Status</span><span>Started</span></div>
            {runs.map((run) => (
              <div className="table-row" key={run.id}>
                <strong>{run.capabilityId === 'PROCESS' ? 'Business data processing' : (capNames.get(run.capabilityId || '') || run.capabilityId || 'Not available')}</strong>
                <span>{run.domain === 'customer-engagement' ? 'Customers' : run.domain === 'platform' ? 'Workspace' : (run.domain || 'Not available')}</span>
                <StatusPill value={run.status} />
                <span>{run.startedAt ? new Date(run.startedAt).toLocaleString() : 'Not available'}</span>
              </div>
            ))}
          </div>
        ) : <Empty title="No agent runs are available" />}
      </section>
    </>
  );
}

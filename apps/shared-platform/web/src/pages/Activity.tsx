import { Empty } from '../components/Empty';
import { PageHeader } from '../components/PageHeader';
import { StatusPill } from '../components/StatusPill';
import { useWorkspace } from '../context';

import { friendlyEventName, friendlySource } from '../lib/display';

export function ActivityPage() {
  const { data } = useWorkspace();
  const events = data?.events || [];
  const capabilities = data?.capabilities || [];

  return (
    <>
      <PageHeader eyebrow="Workspace" title="Activity" description="Recent changes and actions across the business workspace." />
      <section className="section">
        {events.length ? (
          <div className="table">
            <div className="table-head"><span>Event</span><span>Source</span><span>Status</span><span>Time</span></div>
            {events.map((event) => (
              <div className="table-row" key={event.id}>
                <strong>{friendlyEventName(event.eventType)}</strong>
                <span>{friendlySource(event.sourceAgent, capabilities)}</span>
                <StatusPill value={event.status || 'RECORDED'} />
                <span>{event.createdAt ? new Date(event.createdAt).toLocaleString() : 'Not available'}</span>
              </div>
            ))}
          </div>
        ) : <Empty title="No events have been recorded" />}
      </section>
    </>
  );
}

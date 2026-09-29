import { useMemo, useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { Empty } from '../components/Empty';
import { ResultDetails, friendlyOutputType } from '../components/ResultDetails';
import { StatusPill } from '../components/StatusPill';
import { useWorkspace } from '../context';
import { decideRecommendation } from '../lib/api';
import type { Recommendation } from '../types';

type EditableField = { key: string; label: string; type: 'number' | 'text' };

function editableFields(item: Recommendation): EditableField[] {
  if (item.capabilityId === 'P5') return [{ key: 'proposed_price', label: 'Approved selling price', type: 'number' }];
  if (item.capabilityId === 'R4') return [
    { key: 'supplier_id', label: 'Supplier ID', type: 'text' },
    { key: 'qty', label: 'Order quantity', type: 'number' },
    { key: 'unit_cost', label: 'Unit cost', type: 'number' },
    { key: 'eta_days', label: 'Expected arrival in days', type: 'number' }
  ];
  if (item.capabilityId === 'C4') return [
    { key: 'action', label: 'Action', type: 'text' },
    { key: 'channel', label: 'Channel', type: 'text' },
    { key: 'priority', label: 'Priority', type: 'text' }
  ];
  return [];
}

function actionTitle(item: Recommendation) {
  return item.recommendationType || friendlyOutputType(item.capabilityId === 'P5' ? 'PriceRecommendation' : item.capabilityId === 'R4' ? 'PurchaseRecommendation' : item.capabilityId === 'C4' ? 'CustomerAction' : 'Recommendation');
}

export function Approvals() {
  const { data, refresh } = useWorkspace();
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [reason, setReason] = useState('');
  const [editing, setEditing] = useState(false);
  const [modifiedAction, setModifiedAction] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);

  const items = useMemo(() => (data?.recommendations || []).filter((x) => ['READY_FOR_REVIEW', 'READY_FOR_SECOND_REVIEW'].includes(x.status)), [data]);

  function open(item: Recommendation) {
    setSelected(item);
    setEditing(false);
    setModifiedAction({ ...(item.action || {}) });
    setReason('');
    setError(null);
  }

  async function decide(decision: 'APPROVED' | 'MODIFIED' | 'REJECTED') {
    if (!selected) return;
    const id = selected.recommendationId || selected.id;
    setBusy(id);
    setError(null);
    try {
      await decideRecommendation(id, {
        decision,
        reason: reason.trim() || undefined,
        modifiedAction: decision === 'MODIFIED' ? modifiedAction : undefined
      });
      setSelected(null);
      setReason('');
      setEditing(false);
      setModifiedAction({});
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  }

  const fields = selected ? editableFields(selected) : [];

  return (
    <>
      <PageHeader eyebrow="Decisions" title="Approvals" description="Review business actions before they change prices, create purchase orders or become customer work items." />

      {!data?.connected ? (
        <div className="notice"><strong>Approval actions are unavailable while the workspace is offline.</strong><span>Reconnect the workspace to review or approve business actions.</span></div>
      ) : null}

      <section className="section">
        {items.length ? (
          <div className="approval-list">
            {items.map((item) => (
              <button className="approval-row" key={item.id} onClick={() => open(item)}>
                <div>
                  <span className="eyebrow">{item.status === 'READY_FOR_SECOND_REVIEW' ? 'Second review' : (item.capabilityId || item.domain || 'Action')}</span>
                  <strong>{actionTitle(item)}</strong>
                  <span>{item.subjectType || 'subject'} · {item.subjectId || item.id}</span>
                </div>
                <div className="approval-meta">
                  <StatusPill value={item.riskLevel} />
                  <span>{typeof item.confidence === 'number' ? `${Math.round(item.confidence * 100)}% confidence` : 'Confidence unavailable'}</span>
                </div>
              </button>
            ))}
          </div>
        ) : <Empty title="Nothing is waiting for review" />}
      </section>

      {selected ? (
        <div className="modal-layer" role="dialog" aria-modal="true">
          <div className="modal approval-modal">
            <div className="modal-head">
              <div><span className="eyebrow">{selected.status === 'READY_FOR_SECOND_REVIEW' ? 'Second review' : 'Decision'}</span><h2>{actionTitle(selected)}</h2><p>{selected.subjectType || 'Record'} · {selected.subjectId || selected.id}</p></div>
              <button className="text-button" onClick={() => setSelected(null)}>Close</button>
            </div>

            {selected.status === 'READY_FOR_SECOND_REVIEW' ? (
              <div className="notice"><strong>A second authorised reviewer is required.</strong><span>The person who completed the first review cannot complete this one. The second reviewer can approve or reject the reviewed action.</span></div>
            ) : null}

            <div className="approval-detail-block">
              <span className="eyebrow">Recommended action</span>
              <ResultDetails value={selected.action || {}} />
            </div>

            {editing && fields.length ? (
              <div className="approval-edit">
                <div><strong>Adjust before approval</strong><span>Only the business action fields below can be changed. The original analysis remains in the audit trail.</span></div>
                <div className="approval-edit-grid">
                  {fields.map((field) => (
                    <label className="field" key={field.key}>
                      <span>{field.label}</span>
                      <input
                        type={field.type}
                        step={field.type === 'number' ? 'any' : undefined}
                        value={String(modifiedAction[field.key] ?? '')}
                        onChange={(event) => setModifiedAction((current) => ({ ...current, [field.key]: field.type === 'number' ? Number(event.target.value) : event.target.value }))}
                      />
                    </label>
                  ))}
                </div>
              </div>
            ) : null}

            <label className="field">
              <span>Decision note</span>
              <textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Optional note for the audit trail" />
            </label>
            {error ? <div className="form-error">{error}</div> : null}
            <div className="modal-actions">
              <button className="button danger" disabled={Boolean(busy)} onClick={() => void decide('REJECTED')}>Reject</button>
              {fields.length && selected.status !== 'READY_FOR_SECOND_REVIEW' ? <button className="button secondary" disabled={Boolean(busy)} onClick={() => setEditing((value) => !value)}>{editing ? 'Cancel changes' : 'Modify'}</button> : null}
              {editing && selected.status !== 'READY_FOR_SECOND_REVIEW' ? (
                <button className="button primary" disabled={Boolean(busy)} onClick={() => void decide('MODIFIED')}>Approve changes</button>
              ) : (
                <button className="button primary" disabled={Boolean(busy)} onClick={() => void decide('APPROVED')}>Approve</button>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

type Props = { value?: string | null };

const friendly: Record<string, string> = {
  READY_FOR_REVIEW: 'Needs review',
  READY_FOR_SECOND_REVIEW: 'Second review',
  SUCCEEDED: 'Complete',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  MODIFIED: 'Approved with changes',
  RUNNING: 'Running',
  FAILED: 'Failed',
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
  IDLE: 'Ready',
  READY: 'Ready',
  RECORDED: 'Recorded',
  INTEGRATED: 'Ready',
  'INTEGRATION-BASELINE': 'Ready',
  'INTEGRATED-LIVE-SOURCE-TESTED': 'Ready',
  ACTIVE: 'Ready',
  'ACTIVE-V4': 'Ready',
  WAITING_SOURCE: 'Waiting',
  SKIPPED: 'Waiting for data',
  PARTIAL: 'Partially ready',
  NEEDS_DATA: 'Needs data',
  NEEDS_PROCESSING: 'Changes waiting',
  CURRENT: 'Up to date',
  PROCESSING: 'Processing',
  EXECUTED: 'Applied',
  NO_PURCHASE_REQUIRED: 'No purchase needed',
  NO_CHANGE: 'No change needed'
};

function displayStatus(raw: string) {
  if (friendly[raw]) return friendly[raw];
  return raw
    .replace(/\.V\d+$/i, '')
    .replace(/V\d+/gi, '')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase()) || 'Unknown';
}

export function StatusPill({ value }: Props) {
  const raw = (value || 'UNKNOWN').toUpperCase();
  const tone =
    ['FAILED', 'HIGH', 'REJECTED'].includes(raw) ? 'danger' :
    ['RUNNING', 'READY_FOR_REVIEW', 'READY_FOR_SECOND_REVIEW', 'MEDIUM', 'WAITING_SOURCE', 'PARTIAL', 'NEEDS_DATA', 'NEEDS_PROCESSING', 'PROCESSING'].includes(raw) ? 'attention' :
    ['SUCCEEDED', 'APPROVED', 'LOW', 'INTEGRATED', 'INTEGRATION-BASELINE', 'INTEGRATED-LIVE-SOURCE-TESTED', 'READY', 'IDLE', 'ACTIVE', 'ACTIVE-V4', 'CURRENT', 'EXECUTED', 'NO_PURCHASE_REQUIRED', 'NO_CHANGE'].includes(raw) ? 'good' :
    'quiet';

  return <span className={`status-pill ${tone}`}>{displayStatus(raw)}</span>;
}

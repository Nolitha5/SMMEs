export function DataValue({ value }: { value: unknown }) {
  if (value == null) return <span className="muted">Not available</span>;
  if (typeof value === 'boolean') return <span>{value ? 'Yes' : 'No'}</span>;
  if (typeof value === 'object') return <code>{JSON.stringify(value)}</code>;
  return <span>{String(value)}</span>;
}

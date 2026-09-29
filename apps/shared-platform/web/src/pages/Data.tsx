import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { Download, FileUp, Pencil, Plus, Search, X } from 'lucide-react';
import Papa from 'papaparse';
import { Empty } from '../components/Empty';
import { PageHeader } from '../components/PageHeader';
import {
  addDataRecord,
  importData,
  loadDataCatalog,
  loadDataRecords,
  updateDataRecord,
  validateDataImport
} from '../lib/api';
import type {
  BusinessDataRecord,
  DataFieldDefinition,
  DataSetDefinition,
  DataValidationIssue,
  DataValidationResult
} from '../types';

function displayValue(value: unknown) {
  if (value == null || value === '') return 'Not entered';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function fieldValueForForm(field: DataFieldDefinition, value: unknown) {
  if (value == null) return field.default ?? '';
  if (Array.isArray(value)) return value.join(', ');
  if (field.type === 'percent' && typeof value === 'number') return value * 100;
  if (field.type === 'datetime' && typeof value === 'string') {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) {
      const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
      return local.toISOString().slice(0, 16);
    }
  }
  return value;
}

function cleanForCsv(value: unknown) {
  if (value == null) return '';
  if (Array.isArray(value)) return value.join('|');
  return String(value);
}

export function DataPage() {
  const [datasets, setDatasets] = useState<DataSetDefinition[]>([]);
  const [selectedKey, setSelectedKey] = useState('products');
  const [records, setRecords] = useState<BusinessDataRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [importOpen, setImportOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<BusinessDataRecord | null | undefined>(undefined);
  const [dataChanged, setDataChanged] = useState(false);

  const selected = datasets.find((dataset) => dataset.key === selectedKey) || datasets[0];

  async function refreshCatalog() {
    const result = await loadDataCatalog();
    setDatasets(result.datasets);
    if (!result.datasets.some((item) => item.key === selectedKey) && result.datasets[0]) {
      setSelectedKey(result.datasets[0].key);
    }
  }

  async function refreshRecords(key = selectedKey) {
    setRecordsLoading(true);
    try {
      const result = await loadDataRecords(key);
      setRecords(result.records);
    } finally {
      setRecordsLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await loadDataCatalog();
        if (!active) return;
        setDatasets(result.datasets);
        const initial = result.datasets.some((item) => item.key === selectedKey) ? selectedKey : result.datasets[0]?.key;
        if (initial) {
          setSelectedKey(initial);
          const rows = await loadDataRecords(initial);
          if (active) setRecords(rows.records);
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : String(cause));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selected || loading) return;
    setSearch('');
    setError(null);
    void refreshRecords(selected.key).catch((cause) => setError(cause instanceof Error ? cause.message : String(cause)));
  }, [selectedKey]);

  const grouped = useMemo(() => {
    const map = new Map<string, DataSetDefinition[]>();
    for (const dataset of datasets) {
      const list = map.get(dataset.group) || [];
      list.push(dataset);
      map.set(dataset.group, list);
    }
    return [...map.entries()];
  }, [datasets]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return records;
    return records.filter((record) => selected?.fields.some((field) => String(record[field.name] ?? '').toLowerCase().includes(query)));
  }, [records, search, selected]);

  const visibleFields = selected?.fields.slice(0, 5) || [];

  function downloadTemplate() {
    if (!selected) return;
    const csv = `${selected.fields.map((field) => field.name).join(',')}\r\n`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${selected.key}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function afterChange() {
    setDataChanged(true);
    await Promise.all([refreshCatalog(), refreshRecords(selectedKey)]);
  }

  if (loading) return <div className="loading-line">Loading business data…</div>;
  if (error && !datasets.length) return <Empty title="Business data could not be loaded">{error}</Empty>;
  if (!selected) return <Empty title="No business data sets are available" />;

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Business data"
        description="Import real business records, add individual entries and correct existing records."
      />

      {dataChanged ? (
        <div className="notice action-notice">
          <div><strong>Your data change is saved.</strong><span>Process the business data when you are ready to refresh forecasts, stock decisions, recommendations and customer results.</span></div>
          <Link className="button primary" to="/process">Process data</Link>
        </div>
      ) : null}

      <div className="data-workspace">
        <aside className="data-menu" aria-label="Business data sets">
          {grouped.map(([group, items]) => (
            <div className="data-menu-group" key={group}>
              <span>{group}</span>
              {items.map((dataset) => (
                <button
                  key={dataset.key}
                  className={dataset.key === selected.key ? 'active' : ''}
                  onClick={() => setSelectedKey(dataset.key)}
                >
                  <strong>{dataset.label}</strong>
                  <em>{dataset.count}</em>
                </button>
              ))}
            </div>
          ))}
        </aside>

        <div className="data-main">
          <div className="data-heading">
            <div>
              <span className="eyebrow">{selected.group}</span>
              <h2>{selected.label}</h2>
              <p>{selected.description}</p>
            </div>
            <div className="data-actions">
              <button className="button secondary" onClick={downloadTemplate}><Download size={14} /> Template</button>
              <button className="button secondary" onClick={() => setImportOpen(true)}><FileUp size={14} /> Import CSV</button>
              <button className="button primary" onClick={() => setEditRecord(null)}><Plus size={14} /> Add manually</button>
            </div>
          </div>

          <div className="data-toolbar">
            <label className="search-field">
              <Search size={14} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={`Search ${selected.label.toLowerCase()}`} />
            </label>
            <span>{recordsLoading ? 'Loading…' : `${filtered.length} shown`}</span>
          </div>

          {error ? <div className="form-error data-error">{error}</div> : null}

          {recordsLoading ? <div className="loading-line">Loading records…</div> : filtered.length ? (
            <div className="data-table-wrap">
              <div className="data-table data-table-head" style={{ '--data-cols': visibleFields.length } as CSSProperties}>
                {visibleFields.map((field) => <span key={field.name}>{field.label}</span>)}
                <span />
              </div>
              {filtered.map((record) => (
                <div className="data-table data-table-row" style={{ '--data-cols': visibleFields.length } as CSSProperties} key={record.id}>
                  {visibleFields.map((field, index) => (
                    <span key={field.name} className={index === 0 ? 'primary-cell' : ''}>{displayValue(record[field.name])}</span>
                  ))}
                  <button className="row-edit" onClick={() => setEditRecord(record)} aria-label={`Edit ${record.id}`}><Pencil size={14} /> Edit</button>
                </div>
              ))}
            </div>
          ) : (
            <Empty title={`No ${selected.label.toLowerCase()} yet`}>
              Import a CSV export or add the first record manually. Nothing is generated automatically.
            </Empty>
          )}
        </div>
      </div>

      {importOpen ? (
        <ImportModal
          dataset={selected}
          onClose={() => setImportOpen(false)}
          onImported={async () => { setImportOpen(false); await afterChange(); }}
        />
      ) : null}

      {editRecord !== undefined ? (
        <RecordModal
          dataset={selected}
          record={editRecord}
          onClose={() => setEditRecord(undefined)}
          onSaved={async () => { setEditRecord(undefined); await afterChange(); }}
        />
      ) : null}
    </>
  );
}

function ImportModal({ dataset, onClose, onImported }: { dataset: DataSetDefinition; onClose: () => void; onImported: () => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState('');
  const [records, setRecords] = useState<Array<Record<string, unknown>>>([]);
  const [validation, setValidation] = useState<DataValidationResult | null>(null);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function chooseFile(file?: File) {
    if (!file) return;
    setFileName(file.name);
    setValidation(null);
    setError(null);
    Papa.parse<Record<string, unknown>>(file, {
      header: true,
      skipEmptyLines: 'greedy',
      transformHeader: (header) => header.trim(),
      complete: async (result) => {
        const issues = result.errors.map((item) => `Row ${(item.row ?? 0) + 2}: ${item.message}`);
        setParseErrors(issues);
        const rows = result.data.filter((row) => Object.values(row).some((value) => String(value ?? '').trim() !== ''));
        setRecords(rows);
        if (issues.length) return;
        setBusy(true);
        try {
          setValidation(await validateDataImport(dataset.key, rows));
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : String(cause));
        } finally {
          setBusy(false);
        }
      }
    });
  }

  async function commit() {
    setBusy(true);
    setError(null);
    try {
      await importData(dataset.key, records);
      await onImported();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-layer" role="dialog" aria-modal="true">
      <div className="modal data-modal">
        <div className="modal-head">
          <div><span className="eyebrow">Import</span><h2>{dataset.label}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>

        <div className="import-intro">
          <p>Choose a CSV exported from your existing system or spreadsheet. Matching record IDs update the existing record; new IDs are added.</p>
          <p>The file is checked before anything is written.</p>
        </div>

        <input ref={inputRef} type="file" accept=".csv,text/csv" hidden onChange={(event) => void chooseFile(event.target.files?.[0])} />
        <button className="file-picker" onClick={() => inputRef.current?.click()}>
          <FileUp size={18} />
          <div><strong>{fileName || 'Choose CSV file'}</strong><span>Use the template if your column names are different.</span></div>
        </button>

        {parseErrors.length ? <IssueList title="CSV could not be read" issues={parseErrors.map((message, index) => ({ row: index, field: '', message }))} tone="error" /> : null}
        {busy && !validation ? <div className="loading-line">Checking file…</div> : null}
        {validation ? (
          <>
            <div className="import-summary">
              <div><span>Rows</span><strong>{validation.rowCount}</strong></div>
              <div><span>Valid</span><strong>{validation.validCount}</strong></div>
              <div><span>Errors</span><strong>{validation.errors.length}</strong></div>
              <div><span>Warnings</span><strong>{validation.warnings.length}</strong></div>
            </div>
            {validation.errors.length ? <IssueList title="Fix these errors first" issues={validation.errors} tone="error" /> : null}
            {validation.warnings.length ? <IssueList title="Check these warnings" issues={validation.warnings} tone="warning" /> : null}
            {validation.preview.length ? (
              <div className="preview-block">
                <strong>Preview</strong>
                <div className="preview-scroll">
                  <table><thead><tr>{dataset.fields.slice(0, 5).map((field) => <th key={field.name}>{field.label}</th>)}</tr></thead>
                    <tbody>{validation.preview.slice(0, 5).map((row, index) => <tr key={index}>{dataset.fields.slice(0, 5).map((field) => <td key={field.name}>{displayValue(row[field.name])}</td>)}</tr>)}</tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
        {error ? <div className="form-error">{error}</div> : null}
        <div className="modal-actions">
          <button className="button secondary" onClick={onClose}>Cancel</button>
          <button className="button primary" disabled={busy || !validation?.valid || !records.length} onClick={() => void commit()}>
            {busy ? 'Importing…' : `Import ${records.length || ''} records`}
          </button>
        </div>
      </div>
    </div>
  );
}

function IssueList({ title, issues, tone }: { title: string; issues: DataValidationIssue[]; tone: 'error' | 'warning' }) {
  return (
    <div className={`issue-list ${tone}`}>
      <strong>{title}</strong>
      {issues.slice(0, 8).map((issue, index) => (
        <span key={`${issue.row}-${issue.field}-${index}`}>{issue.row ? `Row ${issue.row}${issue.field ? ` · ${issue.field}` : ''}: ` : ''}{issue.message}</span>
      ))}
      {issues.length > 8 ? <em>{issues.length - 8} more</em> : null}
    </div>
  );
}

function RecordModal({ dataset, record, onClose, onSaved }: {
  dataset: DataSetDefinition;
  record: BusinessDataRecord | null;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const editing = Boolean(record);
  const [form, setForm] = useState<Record<string, unknown>>(() => Object.fromEntries(dataset.fields.map((field) => [field.name, fieldValueForForm(field, record?.[field.name])] )));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function change(field: DataFieldDefinition, value: unknown) {
    setForm((current) => ({ ...current, [field.name]: value }));
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      if (record) await updateDataRecord(dataset.key, record.id, form);
      else await addDataRecord(dataset.key, form);
      await onSaved();
    } catch (cause) {
      const err = cause as Error & { details?: Array<{ field?: string; message?: string }> };
      const detail = Array.isArray(err.details) && err.details.length ? ` ${err.details.map((item) => `${item.field || 'field'}: ${item.message || 'invalid'}`).join(' ')}` : '';
      setError(`${err.message}${detail}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-layer" role="dialog" aria-modal="true">
      <div className="modal data-modal">
        <div className="modal-head">
          <div><span className="eyebrow">{editing ? 'Edit record' : 'New record'}</span><h2>{dataset.label}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="record-form">
          {dataset.fields.map((field) => {
            const locked = editing && field.lockedOnEdit;
            const value = form[field.name] ?? '';
            return (
              <label className="field" key={field.name}>
                <span>{field.label}{field.required ? ' *' : ''}</span>
                {field.type === 'enum' ? (
                  <select value={String(value)} disabled={locked} onChange={(event) => change(field, event.target.value)}>
                    <option value="">Select</option>
                    {(field.options || []).map((option) => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}
                  </select>
                ) : field.type === 'boolean' ? (
                  <select value={value === true || value === 'true' ? 'true' : value === false || value === 'false' ? 'false' : ''} disabled={locked} onChange={(event) => change(field, event.target.value)}>
                    <option value="">Select</option><option value="true">Yes</option><option value="false">No</option>
                  </select>
                ) : field.type === 'textarea' ? (
                  <textarea value={String(value)} disabled={locked} onChange={(event) => change(field, event.target.value)} />
                ) : (
                  <input
                    type={field.type === 'date' ? 'date' : field.type === 'datetime' ? 'datetime-local' : ['number', 'decimal', 'percent'].includes(field.type) ? 'number' : 'text'}
                    step={['number', 'decimal', 'percent'].includes(field.type) ? 'any' : undefined}
                    value={String(value)}
                    disabled={locked}
                    placeholder={field.example || undefined}
                    onChange={(event) => change(field, event.target.value)}
                  />
                )}
                {locked ? <small>Record identity cannot be changed.</small> : null}
              </label>
            );
          })}
        </div>
        {error ? <div className="form-error">{error}</div> : null}
        <div className="modal-actions">
          <button className="button secondary" onClick={onClose}>Cancel</button>
          <button className="button primary" disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Add record'}</button>
        </div>
      </div>
    </div>
  );
}

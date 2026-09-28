import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, uploadCsv } from './api.js';

function mockResponse({ ok = true, status = 200, body = {}, jsonThrows = false }) {
  return {
    ok,
    status,
    json: jsonThrows ? () => Promise.reject(new Error('not json')) : () => Promise.resolve(body),
  };
}

describe('api client — success handling', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('returns the parsed response body', async () => {
    global.fetch.mockResolvedValue(mockResponse({ body: { active_suppliers: 3 } }));
    await expect(api('/dashboard')).resolves.toEqual({ active_suppliers: 3 });
  });

  it('requests the configured API base path', async () => {
    global.fetch.mockResolvedValue(mockResponse({ body: {} }));
    await api('/data/suppliers');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/data/suppliers'),
      expect.any(Object),
    );
  });

  it('attaches the demo identity header when not in firebase auth mode', async () => {
    global.fetch.mockResolvedValue(mockResponse({ body: {} }));
    await api('/dashboard');
    const [, init] = global.fetch.mock.calls[0];
    expect(init.headers['X-Demo-User']).toBe('manager@example.com');
  });

  it('preserves caller-supplied headers and method', async () => {
    global.fetch.mockResolvedValue(mockResponse({ body: { status: 'APPROVED' } }));
    await api('/recommendations/REC-1/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: 'APPROVED' }),
    });
    const [, init] = global.fetch.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.headers['X-Demo-User']).toBe('manager@example.com');
  });
});

describe('api client — failure handling', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('throws the server-supplied detail message', async () => {
    global.fetch.mockResolvedValue(
      mockResponse({ ok: false, status: 409, body: { detail: 'Recommendation must be APPROVED or MODIFIED before execution.' } }),
    );
    await expect(api('/recommendations/REC-1/execute', { method: 'POST' })).rejects.toThrow(
      'Recommendation must be APPROVED or MODIFIED before execution.',
    );
  });

  it('falls back to a status message when the error body has no detail', async () => {
    global.fetch.mockResolvedValue(mockResponse({ ok: false, status: 500, body: {} }));
    await expect(api('/dashboard')).rejects.toThrow('Request failed (500)');
  });

  it('survives a non-JSON error body', async () => {
    global.fetch.mockResolvedValue(mockResponse({ ok: false, status: 502, jsonThrows: true }));
    await expect(api('/dashboard')).rejects.toThrow('Request failed (502)');
  });

  it('propagates network-level failures', async () => {
    global.fetch.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api('/dashboard')).rejects.toThrow('Failed to fetch');
  });
});

describe('uploadCsv', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('posts multipart form data to the collection import endpoint', async () => {
    global.fetch.mockResolvedValue(mockResponse({ body: { imported: 4, rejected: 0 } }));
    const file = new File(['supplier_id,name\nSUP-001,Ubuntu'], 'suppliers.csv', { type: 'text/csv' });

    const result = await uploadCsv('suppliers', file);

    expect(result).toEqual({ imported: 4, rejected: 0 });
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toContain('/imports/suppliers');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.body.get('file')).toBe(file);
  });

  it('surfaces import validation failures to the caller', async () => {
    global.fetch.mockResolvedValue(
      mockResponse({ ok: false, status: 400, body: { detail: 'Unsupported collection' } }),
    );
    const file = new File(['x'], 'bad.csv', { type: 'text/csv' });
    await expect(uploadCsv('nope', file)).rejects.toThrow('Unsupported collection');
  });
});

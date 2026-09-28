import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Badge from './Badge.js';

const h = React.createElement;

function renderBadge(value) {
  const { container } = render(h(Badge, { value }));
  return container.firstChild;
}

describe('Badge — risk level display', () => {
  it('renders HIGH risk with the danger tone', () => {
    expect(renderBadge('HIGH')).toHaveClass('bg-red-100', 'text-red-700');
  });

  it('renders MEDIUM risk with the warning tone', () => {
    expect(renderBadge('MEDIUM')).toHaveClass('bg-amber-100', 'text-amber-800');
  });

  it('renders LOW risk with the success tone', () => {
    expect(renderBadge('LOW')).toHaveClass('bg-emerald-100', 'text-emerald-700');
  });
});

describe('Badge — approval status display', () => {
  it('renders READY_FOR_REVIEW as pending review', () => {
    expect(renderBadge('READY_FOR_REVIEW')).toHaveClass('bg-amber-100');
  });

  it('renders APPROVED as success', () => {
    expect(renderBadge('APPROVED')).toHaveClass('bg-emerald-100');
  });

  it('renders EXECUTED as success', () => {
    expect(renderBadge('EXECUTED')).toHaveClass('bg-emerald-100');
  });

  it('renders REJECTED as danger', () => {
    expect(renderBadge('REJECTED')).toHaveClass('bg-red-100');
  });

  it('renders DRAFT with the neutral tone', () => {
    expect(renderBadge('DRAFT')).toHaveClass('bg-slate-100', 'text-slate-700');
  });
});

describe('Badge — reconciliation outcome display', () => {
  it('renders MATCH as success', () => {
    expect(renderBadge('MATCH')).toHaveClass('bg-emerald-100');
  });

  it('renders MISMATCH as danger even though it contains the substring MATCH', () => {
    const badge = renderBadge('MISMATCH');
    expect(badge).toHaveClass('bg-red-100');
    expect(badge).not.toHaveClass('bg-emerald-100');
  });

  it('renders PARTIAL as warning', () => {
    expect(renderBadge('PARTIAL_MATCH')).toHaveClass('bg-amber-100');
  });
});

describe('Badge — value handling', () => {
  it('shows the supplied label text', () => {
    render(h(Badge, { value: 'APPROVED' }));
    expect(screen.getByText('APPROVED')).toBeInTheDocument();
  });

  it('falls back to an em dash when no value is supplied', () => {
    render(h(Badge, { value: undefined }));
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('matches tone case-insensitively', () => {
    expect(renderBadge('approved')).toHaveClass('bg-emerald-100');
  });
});

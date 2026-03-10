"use client";

import Link from 'next/link';
import { useState, useTransition } from 'react';

import {
  buildExportDownloadUrl,
  getExportPreview,
  type ExportPreview,
  type ExportReportType,
} from '@/lib/api';

function createMessage(kind: 'success' | 'error', text: string) {
  return { kind, text, id: `${kind}-${Date.now()}` };
}

function formatCell(value: string | number | boolean | null): string {
  if (value === null || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

const reportCards: Array<{ value: ExportReportType; title: string; note: string }> = [
  { value: 'upcoming_rolloffs', title: 'Upcoming Roll-offs', note: 'Forecast who is due next.' },
  { value: 'upcoming_perfect_attendance', title: 'Perfect Attendance', note: 'Celebrate milestones before they sneak up on you.' },
  { value: 'point_history', title: 'Point History', note: 'Detailed ledger rows with running totals.' },
  { value: 'annual_rolloffs', title: 'Annual Roll-offs', note: 'Track auto-applied YTD reductions.' },
];

type Props = {
  initialPreview: ExportPreview;
  initialLocations: string[];
  initialReportType: ExportReportType;
  initialStartDate: string;
  initialEndDate: string;
};

export function ExportsWorkspace({
  initialPreview,
  initialLocations,
  initialReportType,
  initialStartDate,
  initialEndDate,
}: Props) {
  const [preview, setPreview] = useState(initialPreview);
  const [reportType, setReportType] = useState<ExportReportType>(initialReportType);
  const [building, setBuilding] = useState('All');
  const [startDate, setStartDate] = useState(initialStartDate);
  const [endDate, setEndDate] = useState(initialEndDate);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string; id: string } | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isPending, startTransition] = useTransition();

  const downloadOptions = { report_type: reportType, building, start_date: startDate, end_date: endDate } as const;

  async function handlePreview() {
    setIsBusy(true);
    try {
      const nextPreview = await getExportPreview(downloadOptions);
      startTransition(() => {
        setPreview(nextPreview);
        setMessage(createMessage('success', `${nextPreview.row_count} rows ready for export.`));
      });
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  const csvUrl = buildExportDownloadUrl('csv', downloadOptions);
  const pdfUrl = buildExportDownloadUrl('pdf', downloadOptions);
  const disabled = isBusy || isPending;

  return (
    <main className="page-shell">
      <section className="hero-card compact">
        <div>
          <p className="eyebrow">Exports</p>
          <h1>Reports that look like they came from a product team.</h1>
          <p className="lede">
            Preview operational reports, then download CSVs or polished PDFs with a cleaner, premium presentation
            instead of plain utility output.
          </p>
        </div>
        <div className="hero-actions">
          <a href={pdfUrl} className="secondary-link">Download premium PDF</a>
          <a href={csvUrl} className="panel-link">Download CSV</a>
          <Link href="/" className="panel-link">Back home</Link>
        </div>
      </section>

      {message ? (
        <section className={`flash-banner ${message.kind}`} key={message.id}>
          <strong>{message.kind === 'success' ? 'Ready' : 'Issue'}</strong>
          <span>{message.text}</span>
        </section>
      ) : null}

      <section className="content-grid dashboard-grid">
        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Report Setup</p>
              <h2>Choose the export lane</h2>
            </div>
          </div>
          <div className="threshold-grid export-card-grid">
            {reportCards.map((card) => (
              <button
                key={card.value}
                type="button"
                className={`threshold-card action-button ${reportType === card.value ? 'active-export-card' : ''}`}
                onClick={() => setReportType(card.value)}
              >
                <span>{card.title}</span>
                <strong>{reportType === card.value ? 'Selected' : 'Preview'}</strong>
                <small>{card.note}</small>
              </button>
            ))}
          </div>
          <form className="workspace-form export-form" onSubmit={(event) => { event.preventDefault(); void handlePreview(); }}>
            <label className="form-span-2">
              <span>Location</span>
              <select value={building} onChange={(event) => setBuilding(event.target.value)}>
                <option value="All">All</option>
                {initialLocations.map((location) => (
                  <option key={location} value={location}>{location}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Start date</span>
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label>
              <span>End date</span>
              <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            </label>
            <button type="submit" className="primary-link action-button form-span-2" disabled={disabled}>
              {disabled ? 'Refreshing...' : 'Refresh preview'}
            </button>
          </form>
        </article>

        <article className="panel pulse-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Export Snapshot</p>
              <h2>{preview.title}</h2>
            </div>
          </div>
          <div className="mini-stack">
            <div className="mini-row">
              <div>
                <strong>Rows ready</strong>
                <span>{preview.subtitle}</span>
              </div>
              <div className="mini-meta">
                <span>{preview.row_count}</span>
                <small>{preview.building === 'All' ? 'All locations' : preview.building}</small>
              </div>
            </div>
            <div className="mini-row">
              <div>
                <strong>PDF style</strong>
                <span>Navy shell, cyan highlights, crisp tables</span>
              </div>
              <div className="mini-meta">
                <span>Premium</span>
                <small>SaaS-ready</small>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Preview</p>
            <h2>{preview.title}</h2>
          </div>
          <span className="workspace-caption">{preview.subtitle}</span>
        </div>
        {preview.rows.length ? (
          <div className="table-shell export-preview-shell">
            <div className="table-head" style={{ gridTemplateColumns: `repeat(${preview.columns.length}, minmax(120px, 1fr))` }}>
              {preview.columns.map((column) => (
                <span key={column}>{column}</span>
              ))}
            </div>
            {preview.rows.slice(0, 30).map((row, index) => (
              <div key={`${preview.report_type}-${index}`} className="table-row export-preview-row" style={{ gridTemplateColumns: `repeat(${preview.columns.length}, minmax(120px, 1fr))` }}>
                {preview.columns.map((column) => (
                  <span key={column}>{formatCell(row[column] ?? null)}</span>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <p className="workspace-caption">No records match this export window yet.</p>
        )}
      </section>
    </main>
  );
}

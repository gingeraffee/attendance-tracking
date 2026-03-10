"use client";

import Link from 'next/link';
import { useState, useTransition, type ChangeEvent } from 'react';

import {
  PTO_TEMPLATE_CSV,
  buildPtoExportUrl,
  clearPtoData,
  getPtoOverview,
  importPtoRows,
  type PTOImportRow,
  type PTOOverview,
} from '@/lib/api';

function createMessage(kind: 'success' | 'error', text: string) {
  return { kind, text, id: `${kind}-${Date.now()}` };
}

function formatDateLabel(raw: string | null | undefined): string {
  if (!raw) return 'Not set';
  return new Date(`${raw}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function monthKey(raw: string): string {
  return raw.slice(0, 7);
}

function monthLabel(raw: string): string {
  return new Date(`${raw}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    year: 'numeric',
  });
}

function weekdayLabel(raw: string): string {
  return new Date(`${raw}T00:00:00`).toLocaleDateString('en-US', { weekday: 'short' });
}

function downloadTextFile(text: string, filename: string, mimeType: string) {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function normalizeHeader(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '_');
}

function parseCsv(text: string): PTOImportRow[] {
  const rows: string[][] = [];
  let current = '';
  let row: string[] = [];
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ',' && !inQuotes) {
      row.push(current);
      current = '';
      continue;
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') {
        index += 1;
      }
      row.push(current);
      current = '';
      if (row.some((cell) => cell.trim() !== '')) {
        rows.push(row);
      }
      row = [];
      continue;
    }

    current += char;
  }

  if (current || row.length) {
    row.push(current);
    if (row.some((cell) => cell.trim() !== '')) {
      rows.push(row);
    }
  }

  if (rows.length < 2) {
    throw new Error('The CSV needs a header row and at least one PTO row.');
  }

  const headers = rows[0].map(normalizeHeader);
  return rows.slice(1).map((cells) => {
    const item: Record<string, string> = {};
    headers.forEach((header, index) => {
      item[header] = (cells[index] ?? '').trim();
    });
    return item;
  });
}

type Props = {
  initialOverview: PTOOverview;
};

export function PtoWorkspace({ initialOverview }: Props) {
  const [overview, setOverview] = useState(initialOverview);
  const [building, setBuilding] = useState(initialOverview.filters.selected_building || 'All');
  const [startDate, setStartDate] = useState(initialOverview.filters.selected_start_date || '');
  const [endDate, setEndDate] = useState(initialOverview.filters.selected_end_date || '');
  const [selectedTypes, setSelectedTypes] = useState<string[]>(initialOverview.filters.selected_types.length ? initialOverview.filters.selected_types : initialOverview.filters.available_types);
  const [pendingRows, setPendingRows] = useState<PTOImportRow[]>([]);
  const [pendingFileName, setPendingFileName] = useState('');
  const [clearConfirmed, setClearConfirmed] = useState(false);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string; id: string } | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isPending, startTransition] = useTransition();

  const availableBuildings = ['All', ...overview.filters.available_buildings.filter((value) => value !== 'All')];
  const availableTypes = overview.filters.available_types;
  const queryTypes = selectedTypes.length === availableTypes.length ? [] : selectedTypes;
  const exportUrl = buildPtoExportUrl({
    building,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    types: queryTypes,
  });
  const disabled = isBusy || isPending;

  async function refreshOverview(nextOptions?: {
    building?: string;
    startDate?: string;
    endDate?: string;
    types?: string[];
    successText?: string;
  }) {
    const nextBuilding = nextOptions?.building ?? building;
    const nextStartDate = nextOptions?.startDate ?? startDate;
    const nextEndDate = nextOptions?.endDate ?? endDate;
    const nextTypes = nextOptions?.types ?? selectedTypes;
    const requestTypes = nextTypes.length === availableTypes.length ? [] : nextTypes;

    const nextOverview = await getPtoOverview({
      building: nextBuilding,
      start_date: nextStartDate || undefined,
      end_date: nextEndDate || undefined,
      types: requestTypes,
    });

    startTransition(() => {
      setOverview(nextOverview);
      setBuilding(nextOverview.filters.selected_building || 'All');
      setStartDate(nextOverview.filters.selected_start_date || '');
      setEndDate(nextOverview.filters.selected_end_date || '');
      setSelectedTypes(nextOverview.filters.selected_types.length ? nextOverview.filters.selected_types : nextOverview.filters.available_types);
      if (nextOptions?.successText) {
        setMessage(createMessage('success', nextOptions.successText));
      }
    });
  }

  async function handleRefresh() {
    setIsBusy(true);
    try {
      await refreshOverview({ successText: 'PTO analytics refreshed.' });
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleImport() {
    if (!pendingRows.length) {
      setMessage(createMessage('error', 'Choose a PTO CSV before importing.'));
      return;
    }

    setIsBusy(true);
    try {
      const result = await importPtoRows(pendingRows);
      await refreshOverview({
        successText: `Imported ${result.inserted} new PTO rows, skipped ${result.duplicate} duplicates, excluded ${result.excluded} unmatched rows, and rejected ${result.invalid} invalid rows.`,
      });
      setPendingRows([]);
      setPendingFileName('');
      setFileInputKey((value) => value + 1);
      if (result.excluded_employees.length) {
        setMessage(
          createMessage(
            'success',
            `Imported ${result.inserted} new PTO rows. Unmatched employees: ${result.excluded_employees.join(', ')}${result.excluded_employees.length >= 25 ? '...' : ''}`,
          ),
        );
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleClear() {
    if (!clearConfirmed) {
      setMessage(createMessage('error', 'Check the clear-data confirmation first.'));
      return;
    }

    setIsBusy(true);
    try {
      await clearPtoData();
      const nextOverview = await getPtoOverview();
      startTransition(() => {
        setOverview(nextOverview);
        setBuilding('All');
        setStartDate('');
        setEndDate('');
        setSelectedTypes([]);
        setPendingRows([]);
        setPendingFileName('');
        setClearConfirmed(false);
        setFileInputKey((value) => value + 1);
        setMessage(createMessage('success', 'Stored PTO data was cleared.'));
      });
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      setPendingRows([]);
      setPendingFileName('');
      return;
    }

    try {
      const text = await file.text();
      const rows = parseCsv(text);
      setPendingRows(rows);
      setPendingFileName(file.name);
      setMessage(createMessage('success', `${rows.length} PTO row${rows.length === 1 ? '' : 's'} parsed and ready to import.`));
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Could not read that CSV.';
      setPendingRows([]);
      setPendingFileName('');
      setMessage(createMessage('error', text));
    }
  }

  function toggleType(ptoType: string) {
    setSelectedTypes((current) => (
      current.includes(ptoType)
        ? current.filter((value) => value !== ptoType)
        : [...current, ptoType]
    ));
  }

  const summaryCards = [
    { label: 'Days impacted', value: overview.summary.days_impacted.toString(), hint: `${formatNumber(overview.summary.total_hours)} hours total` },
    { label: 'Employees used PTO', value: overview.summary.employees_used.toString(), hint: `${formatNumber(overview.summary.utilization_pct)}% utilization` },
    { label: 'Top PTO type', value: overview.summary.top_type || 'No data yet', hint: `${formatNumber(overview.summary.total_days)} days in view` },
    { label: 'Avg days per employee', value: formatNumber(overview.summary.avg_days_per_employee), hint: `${formatNumber(overview.summary.utilization_30d_pct)}% touched PTO in 30d` },
  ];

  return (
    <main className="page-shell">
      <section className="hero-card compact">
        <div>
          <p className="eyebrow">PTO Usage Analytics</p>
          <h1>The PTO section makes the jump with its edge intact.</h1>
          <p className="lede">
            Upload a PTO export, keep the active-roster validation, and read the story through cleaner
            filters, sharper signals, and a more product-grade layout.
          </p>
        </div>
        <div className="hero-actions">
          <button type="button" className="secondary-link action-button" onClick={() => downloadTextFile(PTO_TEMPLATE_CSV, 'pto_template.csv', 'text/csv')}>
            Download template
          </button>
          <a href={exportUrl} className="panel-link">Export filtered CSV</a>
          <Link href="/exports" className="panel-link">Open exports</Link>
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
              <p className="eyebrow">Upload + Filters</p>
              <h2>Bring in fresh PTO data, then tighten the view</h2>
            </div>
          </div>

          <div className="pto-control-stack">
            <div className="file-drop-card">
              <div>
                <strong>{pendingFileName || 'Choose a PTO CSV to stage'}</strong>
                <p>{pendingRows.length ? `${pendingRows.length} rows are ready to import.` : 'Client-side parsing keeps the upload flow snappy and predictable.'}</p>
              </div>
              <div className="file-drop-actions">
                <input key={fileInputKey} type="file" accept=".csv,text/csv" onChange={(event) => void handleFileChange(event)} />
                <button type="button" className="primary-link action-button" onClick={() => void handleImport()} disabled={disabled || !pendingRows.length}>
                  {disabled ? 'Working...' : 'Import PTO data'}
                </button>
              </div>
            </div>

            <form className="workspace-form" onSubmit={(event) => { event.preventDefault(); void handleRefresh(); }}>
              <label>
                <span>Building</span>
                <select value={building} onChange={(event) => setBuilding(event.target.value)}>
                  {availableBuildings.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Records loaded</span>
                <input value={overview.filters.total_records ? `${overview.filters.total_records} stored rows` : 'No PTO data loaded'} readOnly />
              </label>
              <label>
                <span>From</span>
                <input
                  type="date"
                  value={startDate}
                  min={overview.filters.date_min || undefined}
                  max={overview.filters.date_max || undefined}
                  onChange={(event) => setStartDate(event.target.value)}
                />
              </label>
              <label>
                <span>To</span>
                <input
                  type="date"
                  value={endDate}
                  min={overview.filters.date_min || undefined}
                  max={overview.filters.date_max || undefined}
                  onChange={(event) => setEndDate(event.target.value)}
                />
              </label>
              <div className="form-span-2 toggle-shell">
                <span className="workspace-caption">PTO Types</span>
                <div className="toggle-grid">
                  {availableTypes.map((ptoType) => {
                    const active = selectedTypes.includes(ptoType);
                    return (
                      <button
                        key={ptoType}
                        type="button"
                        className={`toggle-pill action-button ${active ? 'active' : ''}`}
                        onClick={() => toggleType(ptoType)}
                      >
                        {ptoType}
                      </button>
                    );
                  })}
                  {!availableTypes.length ? <span className="workspace-caption">Types show up after a PTO upload.</span> : null}
                </div>
              </div>
              <div className="form-span-2 form-actions">
                <button type="submit" className="secondary-link action-button" disabled={disabled}>
                  {disabled ? 'Refreshing...' : 'Refresh analytics'}
                </button>
                <button type="button" className="panel-link action-button" onClick={() => {
                  setBuilding('All');
                  setStartDate(overview.filters.date_min || '');
                  setEndDate(overview.filters.date_max || '');
                  setSelectedTypes(overview.filters.available_types);
                }} disabled={disabled}>
                  Reset filters
                </button>
              </div>
            </form>
          </div>
        </article>

        <article className="panel pulse-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Dataset Status</p>
              <h2>{overview.has_data ? 'Live PTO dataset loaded' : 'Waiting on the first PTO import'}</h2>
            </div>
          </div>
          <div className="mini-stack">
            <div className="mini-row">
              <div>
                <strong>Date window</strong>
                <span>{overview.filters.selected_start_date ? `${formatDateLabel(overview.filters.selected_start_date)} to ${formatDateLabel(overview.filters.selected_end_date)}` : 'No PTO date window yet'}</span>
              </div>
              <div className="mini-meta">
                <span>{overview.summary.total_records}</span>
                <small>records in view</small>
              </div>
            </div>
            <div className="mini-row">
              <div>
                <strong>Buildings in dataset</strong>
                <span>{overview.filters.available_buildings.length ? overview.filters.available_buildings.join(', ') : 'Bring in a PTO file to start mapping locations.'}</span>
              </div>
              <div className="mini-meta">
                <span>{overview.filters.available_buildings.length}</span>
                <small>locations</small>
              </div>
            </div>
            <div className="danger-check">
              <label className="checkbox-row">
                <input type="checkbox" checked={clearConfirmed} onChange={(event) => setClearConfirmed(event.target.checked)} />
                <span>I understand clearing PTO data removes the imported PTO dataset.</span>
              </label>
              <button type="button" className="danger-link action-button" onClick={() => void handleClear()} disabled={disabled || !overview.filters.total_records}>
                {disabled ? 'Working...' : 'Clear stored PTO data'}
              </button>
            </div>
          </div>
        </article>
      </section>

      {overview.has_data ? (
        <>
          <section className="metric-grid">
            {summaryCards.map((card) => (
              <article key={card.label} className={`metric-card ${card.label === 'Top PTO type' ? 'accent' : ''}`}>
                <span>{card.label}</span>
                <strong>{card.value}</strong>
                <small className="metric-footnote">{card.hint}</small>
              </article>
            ))}
          </section>

          <section className="content-grid dashboard-grid-secondary">
            <article className="panel panel-wide">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">PTO by Type</p>
                  <h2>Where the hours are really going</h2>
                </div>
              </div>
              <div className="bar-list">
                {overview.type_totals.map((item) => (
                  <div key={item.pto_type} className="bar-row">
                    <div className="bar-copy">
                      <strong>{item.pto_type}</strong>
                      <span>{item.category} | {formatNumber(item.days)} days</span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${Math.max(item.percentage, 6)}%`, background: item.color }} />
                    </div>
                    <div className="bar-value">
                      <strong>{formatNumber(item.hours)}h</strong>
                      <span>{formatNumber(item.percentage)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Buildings</p>
                  <h2>Which locations are carrying the load</h2>
                </div>
              </div>
              <div className="mini-stack">
                {overview.building_totals.map((item) => (
                  <div key={item.building} className="mini-row">
                    <div>
                      <strong>{item.building}</strong>
                      <span>{item.employees} employee{item.employees === 1 ? '' : 's'} with PTO</span>
                    </div>
                    <div className="mini-meta">
                      <span>{formatNumber(item.hours)}h</span>
                      <small>{formatNumber(item.days)} days</small>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="panel panel-wide">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Monthly Pulse</p>
                <h2>How PTO has been moving month to month</h2>
              </div>
              <span className="workspace-caption">Current window: {formatDateLabel(overview.filters.selected_start_date)} to {formatDateLabel(overview.filters.selected_end_date)}</span>
            </div>
            <div className="month-strip">
              {overview.monthly_trend.map((point) => (
                <article key={point.month} className="month-card">
                  <span>{point.label}</span>
                  <strong>{formatNumber(point.total_hours)}h</strong>
                  <small>{formatNumber(point.total_days)} days</small>
                  <p>{point.dominant_type || 'No dominant type'}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="content-grid dashboard-grid-secondary">
            <article className="panel panel-wide">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Top PTO Users</p>
                  <h2>Who is driving the most PTO in this view</h2>
                </div>
                <Link href="/employees" className="panel-link">Open roster</Link>
              </div>
              <div className="employee-list">
                {overview.top_users.map((employee) => (
                  <div key={`${employee.employee}-${employee.building}`} className="employee-row spotlight-row">
                    <div>
                      <strong>{employee.employee}</strong>
                      <span>{employee.building} | {employee.entries} entr{employee.entries === 1 ? 'y' : 'ies'}</span>
                    </div>
                    <div className="employee-meta">
                      <span>{formatNumber(employee.hours)}h</span>
                      <small>{formatNumber(employee.days)} days</small>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Zero PTO</p>
                  <h2>No usage recorded in this slice</h2>
                </div>
              </div>
              <div className="pill-stack">
                {overview.zero_pto_employees.length ? overview.zero_pto_employees.slice(0, 18).map((name) => (
                  <span key={name} className="name-pill">{name}</span>
                )) : <p className="workspace-caption">Everyone in scope has PTO recorded in this period.</p>}
              </div>
            </article>
          </section>

          <section className="content-grid dashboard-grid-secondary">
            <article className="panel panel-wide">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Planned vs Unplanned</p>
                  <h2>The predictability mix</h2>
                </div>
              </div>
              <div className="threshold-grid pto-category-grid">
                {overview.category_metrics.map((metric) => (
                  <article key={metric.key} className={`threshold-card pto-category-card ${metric.key}`}>
                    <span>{metric.label}</span>
                    <strong>{formatNumber(metric.percentage)}%</strong>
                    <small>{formatNumber(metric.hours)}h | {formatNumber(metric.days)} days</small>
                  </article>
                ))}
              </div>
            </article>

            <article className="panel pulse-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Pace + Burnout Signal</p>
                  <h2>How the current window is behaving</h2>
                </div>
              </div>
              <div className="mini-stack">
                <div className="mini-row">
                  <div>
                    <strong>Annualized PTO days</strong>
                    <span>At the current pace</span>
                  </div>
                  <div className="mini-meta">
                    <span>{formatNumber(overview.pace.annualized_total_days)}</span>
                    <small>total days</small>
                  </div>
                </div>
                <div className="mini-row">
                  <div>
                    <strong>Days per employee</strong>
                    <span>Annualized from this slice</span>
                  </div>
                  <div className="mini-meta">
                    <span>{formatNumber(overview.pace.annualized_per_employee_days)}</span>
                    <small>per employee</small>
                  </div>
                </div>
                <div className="mini-row">
                  <div>
                    <strong>Usage trend</strong>
                    <span>{overview.pace.trend_label}</span>
                  </div>
                  <div className="mini-meta">
                    <span>{formatNumber(Math.abs(overview.pace.trend_delta_pct))}%</span>
                    <small>{overview.pace.trend_direction}</small>
                  </div>
                </div>
                <div className="mini-row">
                  <div>
                    <strong>Low-usage employees</strong>
                    <span>Bottom usage slice in this view</span>
                  </div>
                  <div className="mini-meta">
                    <span>{overview.low_usage_employees.length}</span>
                    <small>watch list</small>
                  </div>
                </div>
              </div>
            </article>
          </section>

          <section className="panel panel-wide">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Filtered PTO Rows</p>
                <h2>The rows behind the story</h2>
              </div>
              <span className="workspace-caption">Showing the latest {overview.rows.length} rows in the filtered window</span>
            </div>
            <div className="table-shell export-preview-shell">
              <div className="table-head pto-table-head">
                <span>Employee</span>
                <span>Building</span>
                <span>Type</span>
                <span>Start</span>
                <span>End</span>
                <span>Hours</span>
              </div>
              {overview.rows.map((row, index) => (
                <div key={`${row.employee}-${row.start_date}-${index}`} className="table-row pto-table-row">
                  <div>
                    <strong>{row.employee}</strong>
                    <small>{row.employee_id ? `#${row.employee_id}` : 'No employee ID'}</small>
                  </div>
                  <span>{row.building}</span>
                  <span>{row.pto_type}</span>
                  <span>{formatDateLabel(row.start_date)}</span>
                  <span>{formatDateLabel(row.end_date)}</span>
                  <span>{formatNumber(row.hours)}h</span>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : (
        <section className="panel panel-wide empty-state-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">No PTO Dataset Yet</p>
              <h2>Upload a PTO export to light this section up</h2>
            </div>
          </div>
          <p className="lede">
            The new PTO surface is ready. Once you import a CSV, it will validate against the active employee roster,
            preserve dedupe behavior, and unlock the same kind of trend reading you liked in Streamlit.
          </p>
        </section>
      )}
    </main>
  );
}











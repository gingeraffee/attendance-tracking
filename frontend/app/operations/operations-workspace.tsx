"use client";

import Link from 'next/link';
import { useState, useTransition } from 'react';

import {
  runPerfectAttendance,
  runTwoMonthRolloffs,
  runYtdRolloffs,
  type MaintenanceJobResult,
} from '@/lib/api';

function createMessage(kind: 'success' | 'error', text: string) {
  return { kind, text, id: `${kind}-${Date.now()}` };
}

function formatCell(value: string | number | boolean | null): string {
  if (value === null || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

const jobCards = [
  {
    key: 'rolloffs',
    title: '2-Month Roll-offs',
    description: 'Removes 1 point per overdue period and resets the roll-off clock.',
  },
  {
    key: 'perfect',
    title: 'Perfect Attendance',
    description: 'Advances overdue perfect-attendance milestones without removing points.',
  },
  {
    key: 'ytd',
    title: 'YTD Roll-offs',
    description: 'Applies rolling 12-month net point reduction without shifting the main anchors.',
  },
] as const;

export function OperationsWorkspace() {
  const [runDate, setRunDate] = useState(new Date().toISOString().slice(0, 10));
  const [dryRun, setDryRun] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string; id: string } | null>(null);
  const [result, setResult] = useState<MaintenanceJobResult | null>(null);
  const [runLog, setRunLog] = useState<Array<{ job: string; dryRun: boolean; affected: number; time: string }>>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [isPending, startTransition] = useTransition();

  async function runJob(job: 'rolloffs' | 'perfect' | 'ytd') {
    if (!dryRun && !confirmed) {
      setMessage(createMessage('error', 'Confirm live mode before applying database changes.'));
      return;
    }

    setIsBusy(true);
    try {
      const payload = { run_date: runDate, dry_run: dryRun };
      const nextResult =
        job === 'rolloffs'
          ? await runTwoMonthRolloffs(payload)
          : job === 'perfect'
            ? await runPerfectAttendance(payload)
            : await runYtdRolloffs(payload);

      startTransition(() => {
        setResult(nextResult);
        setRunLog((current) => [
          {
            job: nextResult.job,
            dryRun: nextResult.dry_run,
            affected: nextResult.affected,
            time: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
          },
          ...current,
        ].slice(0, 6));
        setMessage(
          createMessage(
            'success',
            `${nextResult.dry_run ? 'Previewed' : 'Applied'} ${nextResult.job} for ${nextResult.affected} employee${nextResult.affected === 1 ? '' : 's'}.`,
          ),
        );
      });
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  const disabled = isBusy || isPending || (!dryRun && !confirmed);
  const resultColumns = result?.rows[0] ? Object.keys(result.rows[0]) : [];
  const resultGridStyle = resultColumns.length
    ? { gridTemplateColumns: `repeat(${resultColumns.length}, minmax(120px, 1fr))` }
    : undefined;

  return (
    <main className="page-shell">
      <section className="hero-card compact">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Maintenance jobs, with guardrails.</h1>
          <p className="lede">
            Preview before apply, keep a quick run log, and move the roll-off and perfect-attendance engines
            out of Streamlit without losing safety.
          </p>
        </div>
        <div className="hero-actions">
          <Link href="/" className="panel-link">Back home</Link>
          <Link href="/manage-employees" className="secondary-link">Manage employees</Link>
          <Link href="/exports" className="panel-link">Open exports</Link>
          <Link href="/employees" className="panel-link">Open roster</Link>
        </div>
      </section>

      {message ? (
        <section className={`flash-banner ${message.kind}`} key={message.id}>
          <strong>{message.kind === 'success' ? 'Saved' : 'Issue'}</strong>
          <span>{message.text}</span>
        </section>
      ) : null}

      <section className="content-grid dashboard-grid">
        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Run Controls</p>
              <h2>Pick a date, preview safely, then apply when ready</h2>
            </div>
          </div>
          <form className="workspace-form" onSubmit={(event) => event.preventDefault()}>
            <label>
              <span>Run through date</span>
              <input type="date" value={runDate} onChange={(event) => setRunDate(event.target.value)} />
            </label>
            <label>
              <span>Mode</span>
              <select value={dryRun ? 'dry' : 'live'} onChange={(event) => setDryRun(event.target.value === 'dry')}>
                <option value="dry">Dry run</option>
                <option value="live">Live apply</option>
              </select>
            </label>
            <label className="form-span-2 checkbox-row">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
                disabled={dryRun}
              />
              <span>I confirm live mode can write changes to the database.</span>
            </label>
          </form>

          <div className="job-stack">
            {jobCards.map((job) => (
              <article key={job.key} className="job-card">
                <div className="job-copy">
                  <strong>{job.title}</strong>
                  <p>{job.description}</p>
                </div>
                <button
                  type="button"
                  className="primary-link action-button"
                  onClick={() => void runJob(job.key)}
                  disabled={disabled}
                >
                  {isBusy || isPending ? 'Working...' : `Run ${job.title}`}
                </button>
              </article>
            ))}
          </div>
        </article>

        <article className="panel pulse-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Session Log</p>
              <h2>What you ran here</h2>
            </div>
          </div>
          <div className="mini-stack">
            {runLog.map((entry, index) => (
              <div key={`${entry.job}-${entry.time}-${index}`} className="mini-row">
                <div>
                  <strong>{entry.job}</strong>
                  <span>{entry.dryRun ? 'Dry run preview' : 'Live apply'}</span>
                </div>
                <div className="mini-meta">
                  <span>{entry.affected}</span>
                  <small>{entry.time}</small>
                </div>
              </div>
            ))}
            {runLog.length === 0 ? (
              <p className="workspace-caption">Run history for this session will show up here.</p>
            ) : null}
          </div>
        </article>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Latest Result</p>
            <h2>{result ? result.job : 'No job run yet'}</h2>
          </div>
          {result ? <span className="workspace-caption">{result.dry_run ? 'Preview mode' : 'Live mode'} | {result.affected} affected</span> : null}
        </div>

        {result ? (
          <>
            <div className="metric-grid compact-metrics">
              <article className="metric-card">
                <span>Affected</span>
                <strong>{result.affected}</strong>
              </article>
              <article className="metric-card alert">
                <span>5+ after run</span>
                <strong>{result.summary.employees_at_or_above_five}</strong>
              </article>
              <article className="metric-card accent">
                <span>Roll-offs upcoming</span>
                <strong>{result.summary.upcoming_rolloffs}</strong>
              </article>
              <article className="metric-card">
                <span>Perfect upcoming</span>
                <strong>{result.summary.upcoming_perfect_attendance}</strong>
              </article>
            </div>

            {result.rows.length ? (
              <div className="table-shell">
                <div className="table-head" style={resultGridStyle}>
                  {resultColumns.map((column) => (
                    <span key={column}>{column.replaceAll('_', ' ')}</span>
                  ))}
                </div>
                {result.rows.map((row, index) => (
                  <div key={`${result.job}-${index}`} className="table-row" style={resultGridStyle}>
                    {resultColumns.map((column) => (
                      <span key={column}>{formatCell(row[column] ?? null)}</span>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <p className="workspace-caption">No employees were affected for this run date.</p>
            )}
          </>
        ) : (
          <p className="workspace-caption">Choose a job above to preview results here.</p>
        )}
      </section>
    </main>
  );
}

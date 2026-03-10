"use client";

import Link from 'next/link';
import { useEffect, useState, useTransition } from 'react';

import {
  buildEmployeeHistoryPdfUrl,
  createPoint,
  deletePoint,
  recalculateEmployee,
  type EmployeeDetail,
  type MutationResult,
  type PointHistoryEntry,
  updatePoint,
} from '@/lib/api';

const REASON_OPTIONS = ['Tardy/Early Leave', 'Absence', 'No Call/No Show'];

function fmt(raw: string | null): string {
  if (!raw) return 'Not scheduled';
  return new Date(`${raw}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function createMessage(kind: 'success' | 'error', text: string) {
  return { kind, text, id: `${kind}-${Date.now()}` };
}

type Props = {
  initialEmployee: EmployeeDetail;
  initialHistory: PointHistoryEntry[];
};

export function EmployeeWorkspace({ initialEmployee, initialHistory }: Props) {
  const [employee, setEmployee] = useState(initialEmployee);
  const [history, setHistory] = useState(initialHistory);
  const [selectedPointId, setSelectedPointId] = useState<number | null>(initialHistory[0]?.id ?? null);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string; id: string } | null>(null);
  const [isPending, startTransition] = useTransition();
  const [isBusy, setIsBusy] = useState(false);

  const [newPointDate, setNewPointDate] = useState(new Date().toISOString().slice(0, 10));
  const [newPointValue, setNewPointValue] = useState('0.5');
  const [newPointReason, setNewPointReason] = useState(REASON_OPTIONS[0]);
  const [newPointNote, setNewPointNote] = useState('');
  const [newPointFlagCode, setNewPointFlagCode] = useState('');

  const selectedEntry = history.find((entry) => entry.id === selectedPointId) ?? history[0] ?? null;
  const premiumPdfUrl = buildEmployeeHistoryPdfUrl(employee.employee_id);

  const [editPointDate, setEditPointDate] = useState(selectedEntry?.point_date ?? new Date().toISOString().slice(0, 10));
  const [editPointValue, setEditPointValue] = useState(String(selectedEntry?.points ?? 0));
  const [editPointReason, setEditPointReason] = useState(selectedEntry?.reason ?? '');
  const [editPointNote, setEditPointNote] = useState(selectedEntry?.note ?? '');
  const [editPointFlagCode, setEditPointFlagCode] = useState(selectedEntry?.flag_code ?? '');

  useEffect(() => {
    if (!history.length) {
      setSelectedPointId(null);
      return;
    }

    if (!selectedPointId || !history.some((entry) => entry.id === selectedPointId)) {
      setSelectedPointId(history[0].id);
    }
  }, [history, selectedPointId]);

  useEffect(() => {
    if (!selectedEntry) return;
    setEditPointDate(selectedEntry.point_date);
    setEditPointValue(String(selectedEntry.points));
    setEditPointReason(selectedEntry.reason ?? '');
    setEditPointNote(selectedEntry.note ?? '');
    setEditPointFlagCode(selectedEntry.flag_code ?? '');
  }, [selectedEntry?.id]);

  function applyMutation(result: MutationResult, successText: string) {
    setEmployee(result.employee);
    setHistory(result.history);
    setSelectedPointId(result.history[0]?.id ?? null);
    setMessage(createMessage('success', successText));
  }

  async function runMutation(run: () => Promise<MutationResult>, successText: string) {
    setIsBusy(true);
    try {
      const result = await run();
      startTransition(() => {
        applyMutation(result, successText);
      });
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  function handleAddPoint(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runMutation(
      () => createPoint(employee.employee_id, {
        point_date: newPointDate,
        points: Number(newPointValue),
        reason: newPointReason,
        note: newPointNote || null,
        flag_code: newPointFlagCode || null,
      }),
      `Added ${Number(newPointValue).toFixed(1)} points to ${employee.first_name}'s record.`,
    );
  }

  function handleSaveEntry(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEntry) return;

    void runMutation(
      () => updatePoint(employee.employee_id, selectedEntry.id, {
        point_date: editPointDate,
        points: Number(editPointValue),
        reason: editPointReason,
        note: editPointNote || null,
        flag_code: editPointFlagCode || null,
      }),
      `Updated transaction #${selectedEntry.id}.`,
    );
  }

  function handleDeleteEntry() {
    if (!selectedEntry) return;
    void runMutation(
      () => deletePoint(employee.employee_id, selectedEntry.id),
      `Deleted transaction #${selectedEntry.id}.`,
    );
  }

  function handleRecalculate() {
    void runMutation(
      () => recalculateEmployee(employee.employee_id),
      `Recalculated balances for ${employee.first_name} ${employee.last_name}.`,
    );
  }

  return (
    <main className="page-shell">
      <section className="hero-card compact">
        <div>
          <p className="eyebrow">Employee Detail</p>
          <h1>{employee.last_name}, {employee.first_name}</h1>
          <p className="lede">
            This is the first real operations workspace in the Next.js migration:
            point edits, repair actions, and live history updates without a full app rerun.
          </p>
        </div>
        <div className="hero-actions">
          <a href={premiumPdfUrl} className="secondary-link">Download premium PDF</a>
          <button type="button" className="panel-link action-button" onClick={handleRecalculate} disabled={isBusy || isPending}>
            {isBusy || isPending ? 'Working...' : 'Recalculate record'}
          </button>
          <Link href="/exports" className="panel-link">Open exports</Link>
        </div>
      </section>

      {message ? (
        <section className={`flash-banner ${message.kind}`} key={message.id}>
          <strong>{message.kind === 'success' ? 'Saved' : 'Issue'}</strong>
          <span>{message.text}</span>
        </section>
      ) : null}

      <section className="metric-grid">
        <article className="metric-card alert">
          <span>Current points</span>
          <strong>{employee.point_total.toFixed(1)}</strong>
        </article>
        <article className="metric-card">
          <span>Last point</span>
          <strong>{fmt(employee.last_point_date)}</strong>
        </article>
        <article className="metric-card accent">
          <span>Roll-off</span>
          <strong>{fmt(employee.rolloff_date)}</strong>
        </article>
        <article className="metric-card">
          <span>Perfect attendance</span>
          <strong>{fmt(employee.perfect_attendance)}</strong>
        </article>
      </section>

      <section className="content-grid ledger-grid">
        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">New Point</p>
              <h2>Add attendance transaction</h2>
            </div>
          </div>
          <form className="workspace-form" onSubmit={handleAddPoint}>
            <label>
              <span>Date</span>
              <input type="date" value={newPointDate} onChange={(event) => setNewPointDate(event.target.value)} required />
            </label>
            <label>
              <span>Points</span>
              <select value={newPointValue} onChange={(event) => setNewPointValue(event.target.value)}>
                <option value="0.5">0.5</option>
                <option value="1">1.0</option>
                <option value="1.5">1.5</option>
              </select>
            </label>
            <label className="form-span-2">
              <span>Reason</span>
              <select value={newPointReason} onChange={(event) => setNewPointReason(event.target.value)}>
                {REASON_OPTIONS.map((reason) => (
                  <option key={reason} value={reason}>{reason}</option>
                ))}
              </select>
            </label>
            <label className="form-span-2">
              <span>Note</span>
              <input value={newPointNote} onChange={(event) => setNewPointNote(event.target.value)} placeholder="Optional note" />
            </label>
            <label className="form-span-2">
              <span>Flag code</span>
              <input value={newPointFlagCode} onChange={(event) => setNewPointFlagCode(event.target.value)} placeholder="Optional flag code" />
            </label>
            <button type="submit" className="primary-link action-button form-span-2" disabled={isBusy || isPending}>
              {isBusy || isPending ? 'Saving...' : 'Add point'}
            </button>
          </form>
        </article>

        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Edit Ledger</p>
              <h2>Repair or adjust a transaction</h2>
            </div>
          </div>

          <div className="entry-picker">
            {history.map((entry) => (
              <button
                key={entry.id}
                type="button"
                className={`entry-chip ${entry.id === selectedEntry?.id ? 'active' : ''}`}
                onClick={() => setSelectedPointId(entry.id)}
              >
                <strong>{fmt(entry.point_date)}</strong>
                <span>{entry.points >= 0 ? '+' : ''}{entry.points.toFixed(1)} | {entry.reason || 'No reason'}</span>
              </button>
            ))}
          </div>

          {selectedEntry ? (
            <form className="workspace-form" onSubmit={handleSaveEntry}>
              <label>
                <span>Date</span>
                <input type="date" value={editPointDate} onChange={(event) => setEditPointDate(event.target.value)} required />
              </label>
              <label>
                <span>Points</span>
                <input type="number" step="0.5" value={editPointValue} onChange={(event) => setEditPointValue(event.target.value)} required />
              </label>
              <label className="form-span-2">
                <span>Reason</span>
                <input value={editPointReason} onChange={(event) => setEditPointReason(event.target.value)} required />
              </label>
              <label className="form-span-2">
                <span>Note</span>
                <input value={editPointNote} onChange={(event) => setEditPointNote(event.target.value)} placeholder="Optional note" />
              </label>
              <label className="form-span-2">
                <span>Flag code</span>
                <input value={editPointFlagCode} onChange={(event) => setEditPointFlagCode(event.target.value)} placeholder="Optional flag code" />
              </label>
              <div className="form-span-2 form-actions">
                <button type="submit" className="primary-link action-button" disabled={isBusy || isPending}>
                  {isPending ? 'Saving...' : 'Save transaction'}
                </button>
                <button type="button" className="danger-link action-button" onClick={handleDeleteEntry} disabled={isBusy || isPending}>
                  Delete transaction
                </button>
              </div>
              <p className="workspace-caption">
                Running total after this entry: <strong>{selectedEntry.point_total.toFixed(1)} pts</strong>
              </p>
            </form>
          ) : (
            <p className="workspace-caption">No point history exists for this employee yet.</p>
          )}
        </article>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">History</p>
            <h2>Recent point ledger</h2>
          </div>
        </div>
        <div className="table-shell history-shell">
          <div className="table-head five-col">
            <span>Date</span>
            <span>Points</span>
            <span>Reason</span>
            <span>Note</span>
            <span>Running total</span>
          </div>
          {history.map((entry) => (
            <div key={entry.id} className="table-row five-col history-row">
              <span>{fmt(entry.point_date)}</span>
              <span>{entry.points.toFixed(1)}</span>
              <span>{entry.reason || 'No reason'}</span>
              <span>{entry.note || 'No note'}</span>
              <span>{entry.point_total.toFixed(1)}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

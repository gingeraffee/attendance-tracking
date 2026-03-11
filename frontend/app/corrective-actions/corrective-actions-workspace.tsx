"use client";

import Link from 'next/link';
import { useEffect, useState, useTransition } from 'react';

import {
  getCorrectiveActions,
  updateCorrectiveActionDate,
  type CorrectiveActionEmployee,
  type CorrectiveActionOverview,
} from '@/lib/api';

function createMessage(kind: 'success' | 'error', text: string) {
  return { kind, text, id: `${kind}-${Date.now()}` };
}

function formatDateLabel(raw: string | null): string {
  if (!raw) return 'Not logged';
  return new Date(`${raw}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const tierOrder = ['termination', 'written_warning', 'verbal_warning', 'verbal_coaching'];

const tierColors: Record<string, string> = {
  termination: 'termination',
  written_warning: 'written-warning',
  verbal_warning: 'verbal-warning',
  verbal_coaching: 'verbal-coaching',
};

type Props = {
  initialOverview: CorrectiveActionOverview;
};

export function CorrectiveActionsWorkspace({ initialOverview }: Props) {
  const [overview, setOverview] = useState(initialOverview);
  const [editingId, setEditingId] = useState<number | null>(initialOverview.employees[0]?.employee_id ?? null);
  const [warningDate, setWarningDate] = useState(new Date().toISOString().slice(0, 10));
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string; id: string } | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isPending, startTransition] = useTransition();

  const selectedEmployee = overview.employees.find((employee) => employee.employee_id === editingId) ?? overview.employees[0] ?? null;

  useEffect(() => {
    if (!selectedEmployee) return;
    setWarningDate(selectedEmployee.point_warning_date ?? new Date().toISOString().slice(0, 10));
  }, [selectedEmployee?.employee_id]);

  useEffect(() => {
    if (!overview.employees.length) {
      setEditingId(null);
      return;
    }

    if (!editingId || !overview.employees.some((employee) => employee.employee_id === editingId)) {
      setEditingId(overview.employees[0].employee_id);
    }
  }, [editingId, overview.employees]);

  async function refreshOverview(successText?: string) {
    const refreshed = await getCorrectiveActions();
    startTransition(() => {
      setOverview(refreshed);
      if (successText) {
        setMessage(createMessage('success', successText));
      }
    });
  }

  async function handleSaveWarningDate() {
    if (!selectedEmployee) return;
    setIsBusy(true);
    try {
      const updated = await updateCorrectiveActionDate(selectedEmployee.employee_id, warningDate);
      await refreshOverview(`Saved warning date for ${updated.first_name} ${updated.last_name}.`);
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRefresh() {
    setIsBusy(true);
    try {
      await refreshOverview('Corrective action list refreshed.');
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-card compact">
        <div>
          <p className="eyebrow">Corrective Action</p>
          <h1>Threshold tracking, without the spreadsheet vibe.</h1>
          <p className="lede">
            Employees at disciplinary thresholds are grouped by action tier, and warning dates can be logged
            in place without leaving the roster flow.
          </p>
        </div>
        <div className="hero-actions">
          <button type="button" className="secondary-link action-button" onClick={handleRefresh} disabled={isBusy || isPending}>
            {isBusy || isPending ? 'Working...' : 'Refresh list'}
          </button>
          <Link href="/" className="panel-link">Back home</Link>
          <Link href="/exports" className="panel-link">Open exports</Link>
          <Link href="/employees?bucket=5-6" className="panel-link">Open risk roster</Link>
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
          <span>Flagged employees</span>
          <strong>{overview.total_flagged}</strong>
        </article>
        {overview.tiers.slice(0, 3).map((tier) => (
          <article key={tier.key} className="metric-card">
            <span>{tier.label}</span>
            <strong>{tier.count}</strong>
          </article>
        ))}
      </section>

      {selectedEmployee ? (
        <section className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Warning Date</p>
              <h2>{selectedEmployee.last_name}, {selectedEmployee.first_name}</h2>
            </div>
            <Link href={`/employees/${selectedEmployee.employee_id}`} className="panel-link">Open ledger</Link>
          </div>
          <form className="workspace-form corrective-form" onSubmit={(event) => {
            event.preventDefault();
            void handleSaveWarningDate();
          }}>
            <label>
              <span>Warning date</span>
              <input type="date" value={warningDate} onChange={(event) => setWarningDate(event.target.value)} />
            </label>
            <label>
              <span>Tier</span>
              <input value={`${selectedEmployee.tier_label} | ${selectedEmployee.point_total.toFixed(1)} pts`} readOnly />
            </label>
            <label>
              <span>Last positive point</span>
              <input value={formatDateLabel(selectedEmployee.last_positive_point_date)} readOnly />
            </label>
            <label>
              <span>Saved warning</span>
              <input value={formatDateLabel(selectedEmployee.point_warning_date)} readOnly />
            </label>
            <button type="submit" className="primary-link action-button form-span-2" disabled={isBusy || isPending}>
              {isBusy || isPending ? 'Saving...' : 'Save warning date'}
            </button>
          </form>
        </section>
      ) : null}

      {overview.total_flagged === 0 ? (
        <section className="panel panel-wide">
          <p className="workspace-caption">No active employees are currently at or above the 5.0 point threshold.</p>
        </section>
      ) : (
        <section className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Tiered Queue</p>
              <h2>Work the list from highest urgency down</h2>
            </div>
          </div>
          <div className="corrective-stack">
            {tierOrder.map((tierKey) => {
              const tier = overview.tiers.find((entry) => entry.key === tierKey);
              const employees = overview.employees.filter((employee) => employee.tier_key === tierKey);
              if (!tier || employees.length === 0) return null;

              return (
                <section key={tierKey} className="corrective-tier-section">
                  <div className="corrective-tier-header">
                    <div>
                      <p className="eyebrow">{tier.label}</p>
                      <h2>{employees[0].tier_range} points</h2>
                    </div>
                    <span className="workspace-caption">{tier.count} flagged</span>
                  </div>
                  <div className="corrective-list">
                    {employees.map((employee) => (
                      <button
                        key={employee.employee_id}
                        type="button"
                        className={`corrective-row ${tierColors[employee.tier_key]} ${employee.employee_id === selectedEmployee?.employee_id ? 'active' : ''}`}
                        onClick={() => setEditingId(employee.employee_id)}
                      >
                        <div className="corrective-row-main">
                          <strong>{employee.last_name}, {employee.first_name}</strong>
                          <span>#{employee.employee_id} | {employee.location || 'Unassigned'}</span>
                        </div>
                        <div className="corrective-row-meta">
                          <span>{employee.point_total.toFixed(1)} pts</span>
                          <small>Last point {formatDateLabel(employee.last_positive_point_date)}</small>
                        </div>
                        <div className="corrective-row-meta">
                          <span>Warning {formatDateLabel(employee.point_warning_date)}</span>
                          <small>{employee.tier_label}</small>
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        </section>
      )}
    </main>
  );
}

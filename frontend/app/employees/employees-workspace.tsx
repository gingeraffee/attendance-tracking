"use client";

import Link from 'next/link';
import { useDeferredValue, useState, useTransition } from 'react';

import { getEmployees, recalculateAll, type EmployeeSummary } from '@/lib/api';

function createMessage(kind: 'success' | 'error', text: string) {
  return { kind, text, id: `${kind}-${Date.now()}` };
}

function matchesEmployee(employee: EmployeeSummary, query: string): boolean {
  if (!query) return true;
  const haystack = [
    employee.first_name,
    employee.last_name,
    employee.location,
    String(employee.employee_id),
    `${employee.first_name} ${employee.last_name}`,
    `${employee.last_name}, ${employee.first_name}`,
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(query);
}

function matchesBucket(employee: EmployeeSummary, bucket: string): boolean {
  const points = employee.point_total;
  switch (bucket) {
    case 'gt1':
      return points > 1.0;
    case '1-4':
      return points >= 1.0 && points <= 4.5;
    case '5-6':
      return points >= 5.0 && points <= 6.5;
    case '7':
      return points >= 7.0;
    default:
      return true;
  }
}

type Props = {
  initialEmployees: EmployeeSummary[];
  initialQuery?: string;
  initialBuilding?: string;
  initialBucket?: string;
};

export function EmployeesWorkspace({
  initialEmployees,
  initialQuery = '',
  initialBuilding = 'All',
  initialBucket = 'all',
}: Props) {
  const [employees, setEmployees] = useState(initialEmployees);
  const [query, setQuery] = useState(initialQuery);
  const [building, setBuilding] = useState(initialBuilding);
  const [bucket, setBucket] = useState(initialBucket);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string; id: string } | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isPending, startTransition] = useTransition();
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  const values = new Set<string>();
  for (const employee of employees) {
    const location = employee.location?.trim();
    if (location) {
      values.add(location);
    }
  }

  const buildings = ['All', ...Array.from(values).sort((left, right) => left.localeCompare(right))];
  const bucketOptions = [
    { value: 'all', label: 'All points' },
    { value: 'gt1', label: '>1.0 point' },
    { value: '1-4', label: '1.0-4.5 pts' },
    { value: '5-6', label: '5.0-6.5 pts' },
    { value: '7', label: '7.0+ pts' },
  ];

  const visibleEmployees = employees.filter((employee) => {
    const matchesBuilding = building === 'All' || employee.location === building;
    return matchesBuilding && matchesBucket(employee, bucket) && matchesEmployee(employee, deferredQuery);
  });

  const highPointCount = visibleEmployees.filter((employee) => employee.point_total >= 5).length;
  const cleanSlateCount = visibleEmployees.filter((employee) => employee.point_total === 0).length;

  async function refreshEmployees() {
    const refreshed = await getEmployees({
      q: query,
      building,
    });
    startTransition(() => {
      setEmployees(refreshed);
    });
  }

  async function handleRecalculateAll() {
    setIsBusy(true);
    try {
      const summary = await recalculateAll();
      const refreshed = await getEmployees({ q: query, building });
      startTransition(() => {
        setEmployees(refreshed);
        setMessage(
          createMessage(
            'success',
            `Recalculated ${summary.total_employees} employees. ${summary.employees_at_or_above_five} are currently at or above 5.0 points.`,
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

  async function handleRefreshRoster() {
    setIsBusy(true);
    try {
      await refreshEmployees();
      setMessage(createMessage('success', 'Roster refreshed from the API.'));
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
          <p className="eyebrow">Employee Workspace</p>
          <h1>Roster operations, with actual control.</h1>
          <p className="lede">
            Search the roster, jump into an employee ledger, and trigger a full balance repair pass
            without waiting on a Streamlit rerun cycle.
          </p>
        </div>
        <div className="hero-actions">
          <button type="button" className="secondary-link action-button" onClick={handleRecalculateAll} disabled={isBusy || isPending}>
            {isBusy || isPending ? 'Working...' : 'Recalculate everyone'}
          </button>
          <button type="button" className="panel-link action-button" onClick={handleRefreshRoster} disabled={isBusy || isPending}>
            {isBusy || isPending ? 'Working...' : 'Refresh roster'}
          </button>
          <Link href="/manage-employees" className="panel-link">Manage employees</Link>
          <Link href="/" className="panel-link">Back home</Link>
        </div>
      </section>

      {message ? (
        <section className={`flash-banner ${message.kind}`} key={message.id}>
          <strong>{message.kind === 'success' ? 'Saved' : 'Issue'}</strong>
          <span>{message.text}</span>
        </section>
      ) : null}

      <section className="metric-grid">
        <article className="metric-card">
          <span>Visible employees</span>
          <strong>{visibleEmployees.length}</strong>
        </article>
        <article className="metric-card accent">
          <span>Locations in view</span>
          <strong>{building === 'All' ? buildings.length - 1 : 1}</strong>
        </article>
        <article className="metric-card alert">
          <span>At or above 5 points</span>
          <strong>{highPointCount}</strong>
        </article>
        <article className="metric-card">
          <span>Clean slates</span>
          <strong>{cleanSlateCount}</strong>
        </article>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Roster</p>
            <h2>Find the right employee fast</h2>
          </div>
        </div>

        <form className="workspace-form" onSubmit={(event) => event.preventDefault()}>
          <label className="form-span-2">
            <span>Search by name, ID, or location</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Try Nicole, 1042, or Irving"
            />
          </label>
          <label>
            <span>Location</span>
            <select value={building} onChange={(event) => setBuilding(event.target.value)}>
              {buildings.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Threshold</span>
            <select value={bucket} onChange={(event) => setBucket(event.target.value)}>
              {bucketOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
        </form>

        <div className="table-shell">
          <div className="table-head">
            <span>Employee</span>
            <span>Location</span>
            <span>Points</span>
            <span>Details</span>
          </div>
          {visibleEmployees.map((employee) => (
            <div key={employee.employee_id} className="table-row">
              <div>
                <strong>{employee.last_name}, {employee.first_name}</strong>
                <small>#{employee.employee_id}</small>
              </div>
              <span>{employee.location || 'Unassigned'}</span>
              <span>{employee.point_total.toFixed(1)}</span>
              <Link href={`/employees/${employee.employee_id}`} className="row-link">Open</Link>
            </div>
          ))}
          {visibleEmployees.length === 0 ? (
            <div className="table-row">
              <div>
                <strong>No employees match this filter yet.</strong>
                <small>Try a broader search or switch a filter back to All.</small>
              </div>
              <span>-</span>
              <span>-</span>
              <span>-</span>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}

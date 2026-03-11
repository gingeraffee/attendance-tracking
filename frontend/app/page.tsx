import Link from 'next/link';

import { getDashboardDetail } from '@/lib/api';

function formatDateLabel(raw: string | null): string {
  if (!raw) return 'Not scheduled';
  return new Date(`${raw}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function employeeLabel(firstName: string, lastName: string): string {
  return `${lastName}, ${firstName}`;
}

const bucketLinks = [
  { key: 'above_one', label: '>1.0 Point', hint: 'Early warning lane', query: 'gt1' },
  { key: 'one_to_four', label: '1.0-4.5 Pts', hint: 'Watch closely', query: '1-4' },
  { key: 'five_to_six', label: '5.0-6.5 Pts', hint: 'At-risk now', query: '5-6' },
  { key: 'seven_plus', label: '7.0+ Pts', hint: 'Highest urgency', query: '7' },
] as const;

export default async function HomePage() {
  const dashboard = await getDashboardDetail();

  return (
    <main className="page-shell">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Attendance Control</p>
          <h1>The new control center is starting to feel real.</h1>
          <p className="lede">
            Fast operational reads, direct routes into the roster, and a cleaner base for everything
            Streamlit made harder than it needed to be, including the PTO analytics surface.
          </p>
        </div>
        <div className="hero-actions">
          <Link href="/employees" className="primary-link">Open employee workspace</Link>
          <Link href="/manage-employees" className="secondary-link">Manage employees</Link>
          <Link href="/pto" className="panel-link">Open PTO analytics</Link>
          <Link href="/exports" className="panel-link">Open exports</Link>
          <Link href="/operations" className="panel-link">Open operations</Link>
        </div>
      </section>

      <section className="metric-grid">
        <article className="metric-card">
          <span>Active employees</span>
          <strong>{dashboard.summary.active_employees}</strong>
        </article>
        <article className="metric-card alert">
          <span>At or above 5 points</span>
          <strong>{dashboard.summary.employees_at_or_above_five}</strong>
        </article>
        <article className="metric-card accent">
          <span>Roll-offs in 30 days</span>
          <strong>{dashboard.summary.upcoming_rolloffs}</strong>
        </article>
        <article className="metric-card">
          <span>Perfect due in 30 days</span>
          <strong>{dashboard.summary.upcoming_perfect_attendance}</strong>
        </article>
      </section>

      <section className="content-grid dashboard-grid">
        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Threshold Lanes</p>
              <h2>Jump straight into the right risk bucket</h2>
            </div>
          </div>
          <div className="threshold-grid">
            {bucketLinks.map((bucket) => (
              <Link
                key={bucket.key}
                href={`/employees?bucket=${bucket.query}`}
                className={`threshold-card ${bucket.query === '5-6' || bucket.query === '7' ? 'risk' : ''}`}
              >
                <span>{bucket.label}</span>
                <strong>{dashboard.bucket_counts[bucket.key]}</strong>
                <small>{bucket.hint}</small>
              </Link>
            ))}
          </div>
        </article>

        <article className="panel pulse-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Live Pulse</p>
              <h2>What changed recently</h2>
            </div>
          </div>
          <div className="pulse-list">
            <div className="pulse-row">
              <span>Points added in 24h</span>
              <strong>{dashboard.pulse.points_added_24h}</strong>
            </div>
            <div className="pulse-row">
              <span>Points added in 7d</span>
              <strong>{dashboard.pulse.points_added_7d}</strong>
            </div>
            <div className="pulse-row">
              <span>Roll-offs due in 7d</span>
              <strong>{dashboard.pulse.rolloffs_due_7d}</strong>
            </div>
            <div className="pulse-row">
              <span>Perfect attendance due in 7d</span>
              <strong>{dashboard.pulse.perfect_due_7d}</strong>
            </div>
          </div>
        </article>
      </section>

      <section className="content-grid dashboard-grid-secondary">
        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">At-Risk Now</p>
              <h2>Employees already in the red zone</h2>
            </div>
            <Link href="/corrective-actions" className="panel-link">Open corrective actions</Link>
          </div>
          <div className="employee-list">
            {dashboard.at_risk_employees.map((employee) => (
              <Link key={employee.employee_id} href={`/employees/${employee.employee_id}`} className="employee-row spotlight-row">
                <div>
                  <strong>{employeeLabel(employee.first_name, employee.last_name)}</strong>
                  <span>{employee.location || 'Unassigned location'}</span>
                </div>
                <div className="employee-meta">
                  <span>{employee.point_total.toFixed(1)} pts</span>
                  <small>Roll-off {formatDateLabel(employee.rolloff_date)}</small>
                </div>
              </Link>
            ))}
            {dashboard.at_risk_employees.length === 0 ? (
              <p className="workspace-caption">No active employees are at or above 5.0 points right now.</p>
            ) : null}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Upcoming Roll-Offs</p>
              <h2>Closest relief window</h2>
            </div>
            <Link href="/operations" className="panel-link">Run maintenance</Link>
          </div>
          <div className="mini-stack">
            {dashboard.upcoming_rolloffs.map((employee) => (
              <Link key={employee.employee_id} href={`/employees/${employee.employee_id}`} className="mini-row">
                <div>
                  <strong>{employeeLabel(employee.first_name, employee.last_name)}</strong>
                  <span>{employee.location || 'Unassigned location'}</span>
                </div>
                <div className="mini-meta">
                  <span>{formatDateLabel(employee.rolloff_date)}</span>
                  <small>{employee.point_total.toFixed(1)} pts</small>
                </div>
              </Link>
            ))}
            {dashboard.upcoming_rolloffs.length === 0 ? (
              <p className="workspace-caption">No roll-offs are due in the next 30 days.</p>
            ) : null}
          </div>
        </article>
      </section>

      <section className="content-grid dashboard-grid-secondary">
        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Perfect Attendance</p>
              <h2>Recognition coming up</h2>
            </div>
            <Link href="/operations" className="panel-link">Advance dates</Link>
          </div>
          <div className="mini-stack">
            {dashboard.upcoming_perfect_attendance.map((employee) => (
              <Link key={employee.employee_id} href={`/employees/${employee.employee_id}`} className="mini-row">
                <div>
                  <strong>{employeeLabel(employee.first_name, employee.last_name)}</strong>
                  <span>{employee.location || 'Unassigned location'}</span>
                </div>
                <div className="mini-meta">
                  <span>{formatDateLabel(employee.perfect_attendance)}</span>
                  <small>{employee.point_total.toFixed(1)} pts</small>
                </div>
              </Link>
            ))}
            {dashboard.upcoming_perfect_attendance.length === 0 ? (
              <p className="workspace-caption">No perfect attendance milestones are due in the next 30 days.</p>
            ) : null}
          </div>
        </article>

        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Recent Activity</p>
              <h2>Latest point entries across the roster</h2>
            </div>
            <Link href="/exports" className="panel-link">Open exports</Link>
          </div>
          <div className="table-shell history-shell">
            <div className="table-head five-col recent-head">
              <span>Date</span>
              <span>Employee</span>
              <span>Points</span>
              <span>Reason</span>
              <span>Note</span>
            </div>
            {dashboard.recent_activity.map((entry, index) => (
              <Link key={`${entry.employee_id}-${entry.point_date}-${index}`} href={`/employees/${entry.employee_id}`} className="table-row five-col history-row recent-row">
                <span>{formatDateLabel(entry.point_date)}</span>
                <span>{employeeLabel(entry.first_name, entry.last_name)}</span>
                <span>{entry.points.toFixed(1)}</span>
                <span>{entry.reason || 'No reason'}</span>
                <span>{entry.note || 'No note'}</span>
              </Link>
            ))}
            {dashboard.recent_activity.length === 0 ? (
              <p className="workspace-caption">No recent point activity was found.</p>
            ) : null}
          </div>
        </article>
      </section>
    </main>
  );
}

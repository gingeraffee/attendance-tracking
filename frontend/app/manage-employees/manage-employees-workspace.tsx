"use client";

import Link from 'next/link';
import { useEffect, useState, useTransition } from 'react';

import {
  createEmployee,
  deleteEmployee,
  getEmployees,
  updateEmployee,
  type EmployeeSummary,
} from '@/lib/api';

function createMessage(kind: 'success' | 'error', text: string) {
  return { kind, text, id: `${kind}-${Date.now()}` };
}

type Props = {
  initialEmployees: EmployeeSummary[];
};

export function ManageEmployeesWorkspace({ initialEmployees }: Props) {
  const [employees, setEmployees] = useState(initialEmployees);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(initialEmployees[0]?.employee_id ?? null);
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string; id: string } | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isPending, startTransition] = useTransition();

  const [newEmployeeId, setNewEmployeeId] = useState('');
  const [newFirstName, setNewFirstName] = useState('');
  const [newLastName, setNewLastName] = useState('');
  const [newStartDate, setNewStartDate] = useState('');
  const [newLocation, setNewLocation] = useState('');

  const selectedEmployee = employees.find((employee) => employee.employee_id === selectedEmployeeId) ?? employees[0] ?? null;
  const [editFirstName, setEditFirstName] = useState(selectedEmployee?.first_name ?? '');
  const [editLastName, setEditLastName] = useState(selectedEmployee?.last_name ?? '');
  const [editStartDate, setEditStartDate] = useState(selectedEmployee?.start_date ?? '');
  const [editLocation, setEditLocation] = useState(selectedEmployee?.location ?? '');
  const [editIsActive, setEditIsActive] = useState(selectedEmployee?.is_active ?? true);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);

  useEffect(() => {
    if (!employees.length) {
      setSelectedEmployeeId(null);
      return;
    }
    if (!selectedEmployeeId || !employees.some((employee) => employee.employee_id === selectedEmployeeId)) {
      setSelectedEmployeeId(employees[0].employee_id);
    }
  }, [employees, selectedEmployeeId]);

  useEffect(() => {
    if (!selectedEmployee) return;
    setEditFirstName(selectedEmployee.first_name);
    setEditLastName(selectedEmployee.last_name);
    setEditStartDate(selectedEmployee.start_date ?? '');
    setEditLocation(selectedEmployee.location);
    setEditIsActive(selectedEmployee.is_active);
    setDeleteConfirmed(false);
  }, [selectedEmployee?.employee_id]);

  async function refreshEmployees(successText?: string, nextSelectedId?: number | null) {
    const refreshed = await getEmployees();
    startTransition(() => {
      setEmployees(refreshed);
      if (typeof nextSelectedId === 'number') {
        setSelectedEmployeeId(nextSelectedId);
      }
      if (successText) {
        setMessage(createMessage('success', successText));
      }
    });
  }

  async function handleAddEmployee(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    try {
      const created = await createEmployee({
        employee_id: Number(newEmployeeId),
        first_name: newFirstName,
        last_name: newLastName,
        start_date: newStartDate,
        location: newLocation || null,
      });
      setNewEmployeeId('');
      setNewFirstName('');
      setNewLastName('');
      setNewStartDate('');
      setNewLocation('');
      await refreshEmployees(`Added employee #${created.employee_id}.`, created.employee_id);
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSaveEmployee(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEmployee) return;
    setIsBusy(true);
    try {
      const updated = await updateEmployee(selectedEmployee.employee_id, {
        first_name: editFirstName,
        last_name: editLastName,
        start_date: editStartDate || null,
        location: editLocation || null,
        is_active: editIsActive,
      });
      await refreshEmployees(`Saved changes for #${updated.employee_id}.`, updated.employee_id);
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleDeleteEmployee() {
    if (!selectedEmployee || !deleteConfirmed) return;
    const deletedId = selectedEmployee.employee_id;
    setIsBusy(true);
    try {
      await deleteEmployee(deletedId);
      await refreshEmployees(`Deleted employee #${deletedId}.`, null);
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Something went wrong.';
      setMessage(createMessage('error', text));
    } finally {
      setIsBusy(false);
    }
  }

  const activeCount = employees.filter((employee) => employee.is_active).length;
  const inactiveCount = employees.length - activeCount;

  return (
    <main className="page-shell">
      <section className="hero-card compact">
        <div>
          <p className="eyebrow">Manage Employees</p>
          <h1>Onboard, update, archive, or remove people cleanly.</h1>
          <p className="lede">
            This ports the core employee admin workflow out of Streamlit: add new employees, edit their profile,
            toggle active status, and permanently delete records only behind an explicit confirmation.
          </p>
        </div>
        <div className="hero-actions">
          <Link href="/employees" className="secondary-link">Open roster</Link>
          <Link href="/operations" className="panel-link">Open operations</Link>
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
          <span>Total employees</span>
          <strong>{employees.length}</strong>
        </article>
        <article className="metric-card accent">
          <span>Active</span>
          <strong>{activeCount}</strong>
        </article>
        <article className="metric-card">
          <span>Inactive</span>
          <strong>{inactiveCount}</strong>
        </article>
        <article className="metric-card alert">
          <span>Ready to manage</span>
          <strong>{selectedEmployee ? 1 : 0}</strong>
        </article>
      </section>

      <section className="content-grid dashboard-grid-secondary">
        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Add Employee</p>
              <h2>Create a clean new record</h2>
            </div>
          </div>
          <form className="workspace-form" onSubmit={handleAddEmployee}>
            <label>
              <span>Employee #</span>
              <input type="number" min="1" value={newEmployeeId} onChange={(event) => setNewEmployeeId(event.target.value)} required />
            </label>
            <label>
              <span>Building</span>
              <input value={newLocation} onChange={(event) => setNewLocation(event.target.value)} placeholder="Optional location" />
            </label>
            <label>
              <span>First name</span>
              <input value={newFirstName} onChange={(event) => setNewFirstName(event.target.value)} required />
            </label>
            <label>
              <span>Last name</span>
              <input value={newLastName} onChange={(event) => setNewLastName(event.target.value)} required />
            </label>
            <label>
              <span>Hire / start date</span>
              <input type="date" value={newStartDate} onChange={(event) => setNewStartDate(event.target.value)} required />
            </label>
            <button type="submit" className="primary-link action-button form-span-2" disabled={isBusy || isPending}>
              {isBusy || isPending ? 'Saving...' : 'Add employee'}
            </button>
          </form>
          <p className="workspace-caption">Employee number must be unique. Perfect attendance seeds from the hire date right away; roll-off stays blank until points exist.</p>
        </article>

        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Edit Employee</p>
              <h2>Adjust status or profile details</h2>
            </div>
          </div>

          <div className="entry-picker manage-picker">
            {employees.map((employee) => (
              <button
                key={employee.employee_id}
                type="button"
                className={`entry-chip ${employee.employee_id === selectedEmployee?.employee_id ? 'active' : ''}`}
                onClick={() => setSelectedEmployeeId(employee.employee_id)}
              >
                <strong>#{employee.employee_id} {employee.last_name}, {employee.first_name}</strong>
                <span>{employee.location || 'Unassigned'} | {employee.is_active ? 'Active' : 'Inactive'}</span>
              </button>
            ))}
          </div>

          {selectedEmployee ? (
            <form className="workspace-form" onSubmit={handleSaveEmployee}>
              <label>
                <span>First name</span>
                <input value={editFirstName} onChange={(event) => setEditFirstName(event.target.value)} required />
              </label>
              <label>
                <span>Last name</span>
                <input value={editLastName} onChange={(event) => setEditLastName(event.target.value)} required />
              </label>
              <label>
                <span>Hire / start date</span>
                <input type="date" value={editStartDate} onChange={(event) => setEditStartDate(event.target.value)} required />
              </label>
              <label>
                <span>Building</span>
                <input value={editLocation} onChange={(event) => setEditLocation(event.target.value)} placeholder="Optional location" />
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={editIsActive} onChange={(event) => setEditIsActive(event.target.checked)} />
                <span>Active employee</span>
              </label>
              <div className="form-span-2 form-actions">
                <button type="submit" className="primary-link action-button" disabled={isBusy || isPending}>
                  {isBusy || isPending ? 'Saving...' : 'Save changes'}
                </button>
                <Link href={`/employees/${selectedEmployee.employee_id}`} className="panel-link">Open ledger</Link>
              </div>
            </form>
          ) : (
            <p className="workspace-caption">No employee record is selected yet.</p>
          )}
        </article>
      </section>

      <section className="panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Danger Zone</p>
            <h2>Permanently delete an employee and all point history</h2>
          </div>
        </div>
        {selectedEmployee ? (
          <div className="danger-zone">
            <p className="workspace-caption">This removes employee #{selectedEmployee.employee_id} and every related point history row. This cannot be undone.</p>
            <label className="checkbox-row danger-check">
              <input type="checkbox" checked={deleteConfirmed} onChange={(event) => setDeleteConfirmed(event.target.checked)} />
              <span>I understand this permanently deletes the employee record.</span>
            </label>
            <button type="button" className="danger-link action-button" onClick={handleDeleteEmployee} disabled={!deleteConfirmed || isBusy || isPending}>
              Delete employee
            </button>
          </div>
        ) : (
          <p className="workspace-caption">Select an employee above to unlock delete controls.</p>
        )}
      </section>
    </main>
  );
}

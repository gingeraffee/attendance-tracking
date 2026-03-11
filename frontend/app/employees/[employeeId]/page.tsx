import { notFound } from 'next/navigation';

import { getEmployee, getEmployeeHistory } from '@/lib/api';

import { EmployeeWorkspace } from './employee-workspace';

export default async function EmployeeDetailPage({ params }: { params: Promise<{ employeeId: string }> }) {
  const { employeeId } = await params;
  const numericId = Number(employeeId);
  if (Number.isNaN(numericId)) {
    notFound();
  }

  try {
    const [employee, history] = await Promise.all([
      getEmployee(numericId),
      getEmployeeHistory(numericId),
    ]);

    return <EmployeeWorkspace initialEmployee={employee} initialHistory={history} />;
  } catch {
    notFound();
  }
}

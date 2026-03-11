import { ManageEmployeesWorkspace } from './manage-employees-workspace';

import { getEmployees } from '@/lib/api';

export default async function ManageEmployeesPage() {
  const employees = await getEmployees();

  return <ManageEmployeesWorkspace initialEmployees={employees} />;
}

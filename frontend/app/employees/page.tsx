import { EmployeesWorkspace } from './employees-workspace';

import { getEmployees } from '@/lib/api';

type PageProps = {
  searchParams?: Promise<{
    q?: string;
    building?: string;
    bucket?: string;
  }>;
};

export default async function EmployeesPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const employees = await getEmployees({
    q: params.q,
    building: params.building,
  });

  return (
    <EmployeesWorkspace
      initialEmployees={employees}
      initialQuery={params.q ?? ''}
      initialBuilding={params.building ?? 'All'}
      initialBucket={params.bucket ?? 'all'}
    />
  );
}

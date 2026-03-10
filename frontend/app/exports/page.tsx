import { ExportsWorkspace } from './exports-workspace';

import { getEmployees, getExportPreview, type ExportReportType } from '@/lib/api';

const defaultReport: ExportReportType = 'upcoming_rolloffs';

export default async function ExportsPage() {
  const today = new Date();
  const startDate = today.toISOString().slice(0, 10);
  const endDate = new Date(today.getTime() + 60 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

  const [preview, employees] = await Promise.all([
    getExportPreview({ report_type: defaultReport, building: 'All', start_date: startDate, end_date: endDate }),
    getEmployees(),
  ]);

  const locations = Array.from(new Set(employees.map((employee) => employee.location).filter(Boolean))).sort((left, right) => left.localeCompare(right));

  return (
    <ExportsWorkspace
      initialPreview={preview}
      initialLocations={locations}
      initialReportType={defaultReport}
      initialStartDate={startDate}
      initialEndDate={endDate}
    />
  );
}

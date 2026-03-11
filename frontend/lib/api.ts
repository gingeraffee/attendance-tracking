const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

export type DashboardSummary = {
  total_employees: number;
  active_employees: number;
  employees_at_or_above_five: number;
  upcoming_rolloffs: number;
  upcoming_perfect_attendance: number;
};

export type DashboardPulse = {
  points_added_24h: number;
  points_added_7d: number;
  rolloffs_due_7d: number;
  perfect_due_7d: number;
};

export type DashboardBucketCounts = {
  above_one: number;
  one_to_four: number;
  five_to_six: number;
  seven_plus: number;
};

export type DashboardEmployeeSpotlight = {
  employee_id: number;
  first_name: string;
  last_name: string;
  location: string;
  point_total: number;
  rolloff_date: string | null;
  perfect_attendance: string | null;
  last_point_date: string | null;
};

export type DashboardRecentActivity = {
  employee_id: number;
  first_name: string;
  last_name: string;
  location: string;
  point_date: string;
  points: number;
  reason: string | null;
  note: string | null;
};

export type DashboardDetail = {
  summary: DashboardSummary;
  pulse: DashboardPulse;
  bucket_counts: DashboardBucketCounts;
  at_risk_employees: DashboardEmployeeSpotlight[];
  upcoming_rolloffs: DashboardEmployeeSpotlight[];
  upcoming_perfect_attendance: DashboardEmployeeSpotlight[];
  recent_activity: DashboardRecentActivity[];
};

export type CorrectiveActionEmployee = {
  employee_id: number;
  first_name: string;
  last_name: string;
  location: string;
  point_total: number;
  last_positive_point_date: string | null;
  point_warning_date: string | null;
  tier_key: string;
  tier_label: string;
  tier_range: string;
};

export type CorrectiveActionTierCount = {
  key: string;
  label: string;
  count: number;
};

export type CorrectiveActionOverview = {
  total_flagged: number;
  tiers: CorrectiveActionTierCount[];
  employees: CorrectiveActionEmployee[];
};

export type ExportReportType = 'point_history' | 'upcoming_rolloffs' | 'upcoming_perfect_attendance' | 'annual_rolloffs';

export type ExportPreview = {
  report_type: ExportReportType;
  title: string;
  subtitle: string;
  columns: string[];
  rows: Array<Record<string, string | number | boolean | null>>;
  row_count: number;
  start_date: string;
  end_date: string;
  building: string;
};

export type ExportPreviewOptions = {
  report_type: ExportReportType;
  building?: string;
  start_date?: string;
  end_date?: string;
};

export type EmployeeSummary = {
  employee_id: number;
  first_name: string;
  last_name: string;
  location: string;
  start_date: string | null;
  point_total: number;
  rolloff_date: string | null;
  perfect_attendance: string | null;
  is_active: boolean;
};

export type EmployeeCreatePayload = {
  employee_id: number;
  first_name: string;
  last_name: string;
  start_date: string;
  location?: string | null;
};

export type EmployeeUpdatePayload = {
  first_name: string;
  last_name: string;
  start_date?: string | null;
  location?: string | null;
  is_active: boolean;
};

export type EmployeeDetail = EmployeeSummary & {
  last_point_date: string | null;
  point_warning_date: string | null;
};

export type PointHistoryEntry = {
  id: number;
  point_date: string;
  points: number;
  reason: string | null;
  note: string | null;
  flag_code: string | null;
  point_total: number;
};

export type PointMutationPayload = {
  point_date: string;
  points: number;
  reason: string;
  note?: string | null;
  flag_code?: string | null;
};

export type MutationResult = {
  employee: EmployeeDetail;
  history: PointHistoryEntry[];
};

export type MaintenanceRunPayload = {
  run_date: string;
  dry_run: boolean;
};

export type MaintenanceJobResult = {
  job: string;
  dry_run: boolean;
  affected: number;
  rows: Array<Record<string, string | number | boolean | null>>;
  summary: DashboardSummary;
};

export type GetEmployeesOptions = {
  q?: string;
  building?: string;
};

export type PTOFilters = {
  available_buildings: string[];
  available_types: string[];
  selected_building: string;
  selected_types: string[];
  selected_start_date: string | null;
  selected_end_date: string | null;
  date_min: string | null;
  date_max: string | null;
  total_records: number;
};

export type PTOSummary = {
  total_records: number;
  total_hours: number;
  total_days: number;
  days_impacted: number;
  employees_used: number;
  utilization_pct: number;
  top_type: string | null;
  avg_days_per_employee: number;
  utilization_30d_pct: number;
};

export type PTOTypeTotal = {
  pto_type: string;
  hours: number;
  days: number;
  percentage: number;
  color: string;
  category: string;
};

export type PTOMonthlyTrendPoint = {
  month: string;
  label: string;
  total_hours: number;
  total_days: number;
  dominant_type: string | null;
};

export type PTOBuildingTotal = {
  building: string;
  hours: number;
  days: number;
  employees: number;
};

export type PTOEmployeeUsage = {
  employee_id: number | null;
  employee: string;
  building: string;
  hours: number;
  days: number;
  entries: number;
};

export type PTOCategoryMetric = {
  key: string;
  label: string;
  hours: number;
  days: number;
  percentage: number;
};

export type PTOPaceSummary = {
  annualized_total_days: number;
  annualized_per_employee_days: number;
  trend_delta_pct: number;
  trend_direction: string;
  trend_label: string;
};

export type PTORow = {
  employee_id: number | null;
  employee: string;
  building: string;
  pto_type: string;
  start_date: string;
  end_date: string;
  hours: number;
  days: number;
};

export type PTOOverview = {
  has_data: boolean;
  filters: PTOFilters;
  summary: PTOSummary;
  type_totals: PTOTypeTotal[];
  monthly_trend: PTOMonthlyTrendPoint[];
  building_totals: PTOBuildingTotal[];
  top_users: PTOEmployeeUsage[];
  low_usage_employees: PTOEmployeeUsage[];
  zero_pto_employees: string[];
  category_metrics: PTOCategoryMetric[];
  pace: PTOPaceSummary;
  rows: PTORow[];
};

export type PTOImportRow = {
  employee_id?: number | string | null;
  last_name?: string | null;
  first_name?: string | null;
  building?: string | null;
  pto_type?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  date?: string | null;
  hours?: number | string | null;
};

export type PTOImportResult = {
  inserted: number;
  duplicate: number;
  total: number;
  excluded: number;
  invalid: number;
  excluded_employees: string[];
};

export type PTOOverviewOptions = {
  start_date?: string;
  end_date?: string;
  building?: string;
  types?: string[];
};

export const PTO_TEMPLATE_CSV = [
  'employee_id,last_name,first_name,building,pto_type,start_date,end_date,hours',
  '1042,Doe,Jordan,Irving,Vacation,2026-02-10,2026-02-12,24',
  '1177,Nguyen,Avery,Dallas,Absence (Sick),2026-02-18,2026-02-18,8',
  '1383,Ramirez,Taylor,Irving,Floating Holiday,2026-03-03,2026-03-03,8',
].join('\n');

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: 'no-store',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Ignore JSON parse failures and keep the default message.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

function buildEmployeesQuery(options?: GetEmployeesOptions): string {
  const params = new URLSearchParams();
  const query = options?.q?.trim();
  const building = options?.building?.trim();

  if (query) {
    params.set('q', query);
  }
  if (building && building !== 'All') {
    params.set('building', building);
  }

  const serialized = params.toString();
  return serialized ? `?${serialized}` : '';
}

function buildExportQuery(options: ExportPreviewOptions): string {
  const params = new URLSearchParams();
  params.set('report_type', options.report_type);
  if (options.building && options.building !== 'All') {
    params.set('building', options.building);
  }
  if (options.start_date) {
    params.set('start_date', options.start_date);
  }
  if (options.end_date) {
    params.set('end_date', options.end_date);
  }
  return params.toString();
}

function buildPtoQuery(options?: PTOOverviewOptions): string {
  const params = new URLSearchParams();
  if (options?.building && options.building !== 'All') {
    params.set('building', options.building);
  }
  if (options?.start_date) {
    params.set('start_date', options.start_date);
  }
  if (options?.end_date) {
    params.set('end_date', options.end_date);
  }
  if (options?.types?.length) {
    params.set('types', options.types.join(','));
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : '';
}

function runMaintenanceJob(path: string, payload: MaintenanceRunPayload): Promise<MaintenanceJobResult> {
  return fetchJson(path, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getExportPreview(options: ExportPreviewOptions): Promise<ExportPreview> {
  return fetchJson(`/api/v1/exports/preview?${buildExportQuery(options)}`);
}

export function buildExportDownloadUrl(format: 'csv' | 'pdf', options: ExportPreviewOptions): string {
  return `${API_BASE}/api/v1/exports/download.${format}?${buildExportQuery(options)}`;
}

export function buildEmployeeHistoryPdfUrl(employeeId: number): string {
  return `${API_BASE}/api/v1/exports/employee-history/${employeeId}.pdf`;
}

export function buildPtoExportUrl(options?: PTOOverviewOptions): string {
  return `${API_BASE}/api/v1/pto/export.csv${buildPtoQuery(options)}`;
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return fetchJson('/api/v1/attendance/dashboard');
}

export function getDashboardDetail(): Promise<DashboardDetail> {
  return fetchJson('/api/v1/attendance/dashboard/detail');
}

export function getCorrectiveActions(): Promise<CorrectiveActionOverview> {
  return fetchJson('/api/v1/attendance/corrective-actions');
}

export function updateCorrectiveActionDate(employeeId: number, pointWarningDate: string): Promise<CorrectiveActionEmployee> {
  return fetchJson(`/api/v1/attendance/corrective-actions/${employeeId}`, {
    method: 'PATCH',
    body: JSON.stringify({ point_warning_date: pointWarningDate }),
  });
}

export function createEmployee(payload: EmployeeCreatePayload): Promise<EmployeeDetail> {
  return fetchJson('/api/v1/attendance/employees', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateEmployee(employeeId: number, payload: EmployeeUpdatePayload): Promise<EmployeeDetail> {
  return fetchJson(`/api/v1/attendance/employees/${employeeId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteEmployee(employeeId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/attendance/employees/${employeeId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Ignore JSON parse failures and keep the default message.
    }
    throw new Error(detail);
  }
}

export function getEmployees(options?: GetEmployeesOptions): Promise<EmployeeSummary[]> {
  return fetchJson(`/api/v1/attendance/employees${buildEmployeesQuery(options)}`);
}

export function getEmployee(employeeId: number): Promise<EmployeeDetail> {
  return fetchJson(`/api/v1/attendance/employees/${employeeId}`);
}

export function getEmployeeHistory(employeeId: number): Promise<PointHistoryEntry[]> {
  return fetchJson(`/api/v1/attendance/employees/${employeeId}/history?limit=100`);
}

export function createPoint(employeeId: number, payload: PointMutationPayload): Promise<MutationResult> {
  return fetchJson(`/api/v1/attendance/employees/${employeeId}/points`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updatePoint(employeeId: number, pointId: number, payload: PointMutationPayload): Promise<MutationResult> {
  return fetchJson(`/api/v1/attendance/employees/${employeeId}/points/${pointId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deletePoint(employeeId: number, pointId: number): Promise<MutationResult> {
  return fetchJson(`/api/v1/attendance/employees/${employeeId}/points/${pointId}`, {
    method: 'DELETE',
  });
}

export function recalculateEmployee(employeeId: number): Promise<MutationResult> {
  return fetchJson(`/api/v1/attendance/employees/${employeeId}/recalculate`, {
    method: 'POST',
  });
}

export function recalculateAll(): Promise<DashboardSummary> {
  return fetchJson('/api/v1/attendance/recalculate', {
    method: 'POST',
  });
}

export function runTwoMonthRolloffs(payload: MaintenanceRunPayload): Promise<MaintenanceJobResult> {
  return runMaintenanceJob('/api/v1/attendance/maintenance/rolloffs', payload);
}

export function runPerfectAttendance(payload: MaintenanceRunPayload): Promise<MaintenanceJobResult> {
  return runMaintenanceJob('/api/v1/attendance/maintenance/perfect-attendance', payload);
}

export function runYtdRolloffs(payload: MaintenanceRunPayload): Promise<MaintenanceJobResult> {
  return runMaintenanceJob('/api/v1/attendance/maintenance/ytd-rolloffs', payload);
}

export function getPtoOverview(options?: PTOOverviewOptions): Promise<PTOOverview> {
  return fetchJson(`/api/v1/pto${buildPtoQuery(options)}`);
}

export function importPtoRows(rows: PTOImportRow[]): Promise<PTOImportResult> {
  return fetchJson('/api/v1/pto/import', {
    method: 'POST',
    body: JSON.stringify({ rows }),
  });
}

export function clearPtoData(): Promise<{ ok: boolean }> {
  return fetchJson('/api/v1/pto/clear', {
    method: 'DELETE',
  });
}

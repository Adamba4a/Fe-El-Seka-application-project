const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface FinancialTrendPoint {
  date: string;
  value: string;
}

export interface SponsoredGroupCommission {
  group_id: string;
  group_name: string;
  commission_egp: string;
  rides: number;
}

export interface FinancialReport {
  range: { start: string; end: string };
  commission_collected_egp: string;
  sponsored_commission_collected_egp: string;
  sponsored_commission_by_group: SponsoredGroupCommission[];
  admin_credits_egp: string;
  admin_debits_egp: string;
  net_revenue_egp: string;
  trend: {
    metric: "commission_collected_egp";
    granularity: "day" | "week";
    points: FinancialTrendPoint[];
  };
}

export interface DriverBalanceItem {
  driver_id: string;
  display_name: string;
  balance_egp: string;
  reserved_egp: string;
  available_egp: string;
  sponsored_earnings_egp: string;
  is_at_risk: boolean;
}

export interface DriverBalancesResponse {
  items: DriverBalanceItem[];
}

export async function getReport(token: string, start: string, end: string): Promise<FinancialReport> {
  const params = new URLSearchParams({ start, end });
  const res = await fetch(`${base}/api/admin/financial/report?${params}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export function getReportExportUrl(start: string, end: string): string {
  const params = new URLSearchParams({ start, end });
  return `${base}/api/admin/financial/report/export?${params}`;
}

export async function getDriverBalances(token: string): Promise<DriverBalancesResponse> {
  const res = await fetch(`${base}/api/admin/financial/drivers/balances`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

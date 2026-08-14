const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type Period = "today" | "7d" | "30d" | "90d";

export interface TrendPoint {
  date: string;
  value: number | string;
}

export interface TrendSeries {
  metric: "rides_completed" | "commission_collected_egp";
  granularity: "day" | "week";
  points: TrendPoint[];
}

export interface DashboardOverview {
  period: Period;
  users_by_role: { passenger: number; driver: number; admin: number };
  rides_created: number;
  rides_completed: number;
  commission_collected_egp: string;
  pending_verifications: number;
  open_reports: number;
  drivers_at_or_below_zero: number;
  pending_topups: number;
  trends: {
    rides_completed: TrendSeries;
    commission_collected_egp: TrendSeries;
  };
}

export async function getDashboardOverview(
  token: string,
  period: Period,
): Promise<DashboardOverview> {
  const res = await fetch(`${base}/api/admin/dashboard/overview?period=${period}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

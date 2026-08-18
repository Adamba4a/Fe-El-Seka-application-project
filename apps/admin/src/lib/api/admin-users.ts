const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type UserRole = "passenger" | "driver" | "admin";
export type VerificationStatus = "unverified" | "pending_review" | "verified" | "rejected" | "suspended";

export interface UserListItem {
  user_id: string;
  display_name: string;
  email: string;
  role: UserRole;
  verification_status: VerificationStatus;
  created_at: string;
}

export interface UserListResponse {
  total: number;
  page: number;
  items: UserListItem[];
}

export interface UserListParams {
  q?: string;
  role?: UserRole;
  status?: VerificationStatus;
  page?: number;
}

export interface RideSummary {
  ride_id: string;
  status: string;
  created_at: string;
}

export interface BookingSummary {
  booking_id: string;
  status: string;
  created_at: string;
}

export interface RatingItem {
  stars: number;
  comment: string | null;
  created_at: string;
}

export interface ReportSummary {
  report_id: string;
  status: string;
  created_at: string;
}

export interface LedgerEntrySummary {
  id: string;
  type: string;
  amount_egp: string;
  created_at: string;
}

export interface UserDetail {
  profile: {
    user_id: string;
    display_name: string;
    email: string;
    phone_number: string | null;
    role: UserRole;
    verification_status: VerificationStatus;
    created_at: string;
    is_admin_role: boolean;
    profile_photo_signed_url: string | null;
  };
  rides: RideSummary[];
  bookings: BookingSummary[];
  ratings_received: {
    rating_avg: number;
    rating_count: number;
    items: RatingItem[];
  };
  reports: {
    filed_by_user: ReportSummary[];
    filed_against_user: ReportSummary[];
  };
  wallet?: {
    balance_egp: string;
    available_egp: string;
    recent_ledger: LedgerEntrySummary[];
  };
}

export async function list(token: string, params: UserListParams = {}): Promise<UserListResponse> {
  const search = new URLSearchParams({ page: String(params.page ?? 1), limit: "20" });
  if (params.q) search.set("q", params.q);
  if (params.role) search.set("role", params.role);
  if (params.status) search.set("status", params.status);
  const res = await fetch(`${base}/api/admin/users/?${search}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getDetail(token: string, userId: string): Promise<UserDetail> {
  const res = await fetch(`${base}/api/admin/users/${userId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function suspend(token: string, userId: string, reason: string): Promise<{ new_status: string }> {
  const res = await fetch(`${base}/api/admin/users/${userId}/suspend`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reinstate(token: string, userId: string): Promise<{ new_status: string }> {
  const res = await fetch(`${base}/api/admin/users/${userId}/reinstate`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

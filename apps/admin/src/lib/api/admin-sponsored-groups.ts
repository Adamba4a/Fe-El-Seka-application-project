const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface SponsoredGroupSummary {
  id: string;
  name: string;
  type: string;
  description: string;
  route_tags: string[];
  member_count: number;
  is_sponsored: boolean;
  funded_balance_egp: string;
  dashboard_contact_user_id: string | null;
}

export interface AddFundsResponse {
  group_id: string;
  new_funded_balance_egp: string;
}

export interface GroupMember {
  id: string;
  user_id: string;
  display_name: string;
  role: "owner" | "member";
  joined_at: string;
}

export interface DashboardContactResponse {
  group_id: string;
  dashboard_contact_user_id: string;
}

export async function createOrUpgrade(
  token: string,
  domain: string,
  fundedBalanceEgp: string,
  requestedGroupType: "company" | "university",
  name?: string,
): Promise<SponsoredGroupSummary> {
  const res = await fetch(`${base}/api/admin/sponsored-groups`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      domain,
      funded_balance_egp: fundedBalanceEgp,
      requested_group_type: requestedGroupType,
      name: name || undefined,
    }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function addFunds(
  token: string,
  groupId: string,
  amountEgp: string,
): Promise<AddFundsResponse> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}/add-funds`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ amount_egp: amountEgp }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function listMembers(token: string, groupId: string): Promise<GroupMember[]> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}/members`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function setDashboardContact(
  token: string,
  groupId: string,
  userId: string,
): Promise<DashboardContactResponse> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}/dashboard-contact`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

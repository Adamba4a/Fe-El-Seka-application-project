const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

// FastAPI wraps our own HTTPException payloads as {"detail": {error, message}},
// but a Pydantic model_post_init validation failure (e.g. an invalid sponsor
// domain) produces {"detail": [{"msg": "Value error, ...", ...}]} instead — a
// list, not an object. Callers used to do `err?.detail?.message`, which is
// undefined for that second shape, so every validation rejection silently fell
// back to a generic "Failed to ..." message instead of the actual reason.
async function parseErrorResponse(res: Response): Promise<{ error?: string; message?: string }> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return { message: res.statusText || `Request failed with status ${res.status}` };
  }
  const detail = body && typeof body === "object" ? (body as any).detail : undefined;
  if (Array.isArray(detail)) {
    const msg = typeof detail[0]?.msg === "string" ? detail[0].msg.replace(/^Value error,\s*/, "") : undefined;
    return { error: "validation_error", message: msg };
  }
  if (detail && typeof detail === "object") {
    return detail as { error?: string; message?: string };
  }
  return body as { error?: string; message?: string };
}

export interface SponsoredGroupSummary {
  id: string;
  name: string;
  description: string;
  route_tags: string[];
  member_count: number;
  is_sponsored: boolean;
  funded_balance_egp: string;
  dashboard_contact_user_id: string | null;
  sponsor_domains: string[];
}

export interface SponsorDomainsResponse {
  group_id: string;
  domains: string[];
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

export interface DeleteSponsoredGroupResponse {
  group_id: string;
  cleared_funded_balance_egp: string;
}

export interface UnsponsorGroupResponse {
  group_id: string;
  is_sponsored: boolean;
  cleared_funded_balance_egp: string;
}

export async function listSponsoredGroups(token: string): Promise<SponsoredGroupSummary[]> {
  const res = await fetch(`${base}/api/admin/sponsored-groups`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function createOrUpgrade(
  token: string,
  domains: string[],
  fundedBalanceEgp: string,
  name?: string,
): Promise<SponsoredGroupSummary> {
  const res = await fetch(`${base}/api/admin/sponsored-groups`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      domains,
      funded_balance_egp: fundedBalanceEgp,
      name: name || undefined,
    }),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function addSponsorDomain(
  token: string,
  groupId: string,
  domain: string,
): Promise<SponsorDomainsResponse> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}/domains`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ domain }),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function removeSponsorDomain(
  token: string,
  groupId: string,
  domain: string,
): Promise<SponsorDomainsResponse> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}/domains/${encodeURIComponent(domain)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await parseErrorResponse(res);
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
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function listMembers(token: string, groupId: string): Promise<GroupMember[]> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}/members`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function deleteSponsoredGroup(
  token: string,
  groupId: string,
): Promise<DeleteSponsoredGroupResponse> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function unsponsorGroup(
  token: string,
  groupId: string,
): Promise<UnsponsorGroupResponse> {
  const res = await fetch(`${base}/api/admin/sponsored-groups/${groupId}/unsponsor`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await parseErrorResponse(res);
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
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

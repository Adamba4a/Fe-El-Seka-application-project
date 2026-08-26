import type {
  CreateGroupPayload,
  DomainVerificationConfirmPayload,
  DomainVerificationConfirmResponse,
  DomainVerificationRequestPayload,
  DomainVerificationRequestResponse,
  Group,
  GroupDetail,
  GroupListResponse,
  InviteLinkResponse,
  Membership,
  RideListResponse,
} from "@fe-el-seka/shared";

import { env } from "../env";

const base = env.apiUrl;

// FastAPI's default HTTPException handler wraps our {error, message} dict under
// a "detail" key ({"detail": {"error": ..., "message": ...}}) — unwrap it so
// callers can check err.error / err.message directly.
async function parseErrorResponse(res: Response): Promise<{ error?: string; message?: string }> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return { message: res.statusText || `Request failed with status ${res.status}` };
  }
  if (body && typeof body === "object" && "detail" in body && typeof body.detail === "object") {
    return body.detail as { error?: string; message?: string };
  }
  return body as { error?: string; message?: string };
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export interface SearchGroupsParams {
  q?: string;
  type?: string;
  route_tag?: string;
  limit?: number;
  offset?: number;
}

export async function createGroup(token: string, payload: CreateGroupPayload): Promise<Group> {
  const res = await fetch(`${base}/api/groups`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function searchGroups(
  token: string,
  params: SearchGroupsParams = {}
): Promise<GroupListResponse> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.type) query.set("type", params.type);
  if (params.route_tag) query.set("route_tag", params.route_tag);
  if (params.limit) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));

  const res = await fetch(`${base}/api/groups?${query.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getGroup(token: string, groupId: string): Promise<GroupDetail> {
  const res = await fetch(`${base}/api/groups/${groupId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getMyGroups(token: string): Promise<Group[]> {
  const res = await fetch(`${base}/api/groups/mine`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getGroupRides(token: string, groupId: string): Promise<RideListResponse> {
  const res = await fetch(`${base}/api/groups/${groupId}/rides`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function getInviteLink(token: string, groupId: string): Promise<InviteLinkResponse> {
  const res = await fetch(`${base}/api/groups/${groupId}/invite-link`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function resolveInviteToken(token: string, inviteToken: string): Promise<GroupDetail> {
  const res = await fetch(`${base}/api/groups/join/${inviteToken}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function joinGroup(token: string, groupId: string): Promise<Membership> {
  const res = await fetch(`${base}/api/groups/${groupId}/join`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function requestDomainVerification(
  token: string,
  payload: DomainVerificationRequestPayload
): Promise<DomainVerificationRequestResponse> {
  const res = await fetch(`${base}/api/groups/domain-verification/request`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

export async function confirmDomainVerification(
  token: string,
  payload: DomainVerificationConfirmPayload
): Promise<DomainVerificationConfirmResponse> {
  const res = await fetch(`${base}/api/groups/domain-verification/confirm`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseErrorResponse(res);
  return res.json();
}

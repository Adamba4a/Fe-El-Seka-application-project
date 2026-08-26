export type GroupType = "general" | "company" | "university";

export interface Group {
  id: string;
  name: string;
  type: GroupType;
  description: string | null;
  route_tags: string[];
  member_count: number;
}

export interface GroupDetail extends Group {
  is_member: boolean;
  is_owner: boolean;
}

export interface GroupListResponse {
  items: Group[];
  total: number;
}

export interface CreateGroupPayload {
  name: string;
  description?: string;
  route_tags?: string[];
}

export interface InviteLinkResponse {
  invite_token: string;
  invite_url: string;
}

export interface Membership {
  id: string;
  group_id: string;
  user_id: string;
  role: "owner" | "member";
  joined_at: string;
}

export type DomainGroupType = "company" | "university";

export interface DomainVerificationRequestPayload {
  email: string;
  requested_group_type: DomainGroupType;
}

export interface DomainVerificationRequestResponse {
  verification_id: string;
  expires_in_seconds: number;
}

export interface DomainVerificationConfirmPayload {
  verification_id: string;
  code: string;
}

export interface DomainVerificationConfirmResponse {
  membership: Membership;
  group: Group;
}

export interface GroupMember {
  id: string;
  user_id: string;
  display_name: string;
  role: "owner" | "member";
  joined_at: string;
}

export interface TransferOwnershipPayload {
  new_owner_user_id: string;
}

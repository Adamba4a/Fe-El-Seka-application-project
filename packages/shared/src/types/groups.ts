export interface Group {
  id: string;
  name: string;
  description: string | null;
  route_tags: string[];
  member_count: number;
  is_sponsored: boolean;
  funded_balance_egp: string;
  dashboard_contact_user_id: string | null;
  sponsor_domains: string[];
}

export interface GroupDetail extends Group {
  is_member: boolean;
  is_owner: boolean;
  is_domain_verified: boolean;
  is_dashboard_contact: boolean;
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

export interface DomainVerificationRequestPayload {
  email: string;
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

export interface SponsorshipActivityItem {
  type: "SPONSORED_RIDE_CREDIT" | "SPONSORED_RIDE_REVERSAL";
  amount_egp: string;
  ride_id: string;
  booking_id: string;
  created_at: string;
  driver_name: string | null;
  passenger_name: string | null;
  origin_address: string | null;
  destination_address: string | null;
}

export interface SponsorshipDashboard {
  funded_balance_egp: string;
  member_count: number;
  recent_activity: SponsorshipActivityItem[];
}

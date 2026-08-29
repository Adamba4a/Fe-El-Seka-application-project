export interface OrgAccessRequestBody {
  email: string;
}

export interface OrgAccessRequestResponse {
  verification_id: string;
  expires_in_seconds: number;
}

export interface OrgAccessConfirmBody {
  verification_id: string;
  code: string;
}

export interface OrgAccessConfirmResponse {
  org_verified_at: string;
  org_verified_domain: string;
}

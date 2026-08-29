from pydantic import BaseModel


class OrgAccessRequest(BaseModel):
    email: str


class OrgAccessRequestResponse(BaseModel):
    verification_id: str
    expires_in_seconds: int


class OrgAccessConfirm(BaseModel):
    verification_id: str
    code: str


class OrgAccessConfirmResponse(BaseModel):
    org_verified_at: str
    org_verified_domain: str

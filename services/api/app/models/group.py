from typing import Literal

from pydantic import BaseModel

GroupType = Literal["general", "company", "university"]
DomainGroupType = Literal["company", "university"]


class CreateGroupRequest(BaseModel):
    name: str
    description: str | None = None
    route_tags: list[str] = []

    def model_post_init(self, __context) -> None:
        name = (self.name or "").strip()
        if not (3 <= len(name) <= 80):
            raise ValueError("name must be between 3 and 80 characters")
        self.name = name
        if len(self.route_tags) > 10:
            raise ValueError("route_tags accepts at most 10 tags")
        for tag in self.route_tags:
            if len(tag) > 40:
                raise ValueError("each route_tag must be 40 characters or fewer")


class GroupSummary(BaseModel):
    id: str
    name: str
    type: GroupType
    description: str | None
    route_tags: list[str]
    member_count: int


class GroupListResponse(BaseModel):
    items: list[GroupSummary]
    total: int


class GroupDetailResponse(GroupSummary):
    is_member: bool
    is_owner: bool


class InviteLinkResponse(BaseModel):
    invite_token: str
    invite_url: str


class MembershipResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    role: Literal["owner", "member"]
    joined_at: str


class DomainVerificationRequest(BaseModel):
    email: str
    requested_group_type: DomainGroupType


class DomainVerificationRequestResponse(BaseModel):
    verification_id: str
    expires_in_seconds: int


class DomainVerificationConfirm(BaseModel):
    verification_id: str
    code: str


class DomainVerificationConfirmResponse(BaseModel):
    membership: MembershipResponse
    group: GroupSummary


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: str

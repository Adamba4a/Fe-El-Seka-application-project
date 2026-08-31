import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

# A real email domain always has at least one dot (name.tld) — this catches
# the common admin mistake of entering the company name ("adam") instead of
# its actual email domain ("adam.com"), which would otherwise sit in the
# eligible-domains list forever silently rejecting every real employee email.
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def _validate_domain(domain: str) -> str:
    domain = domain.strip().lower()
    if not _DOMAIN_RE.match(domain):
        raise ValueError(
            f"'{domain}' isn't a valid email domain — it must look like a real domain "
            "with a TLD, e.g. 'company.com', not just 'company'."
        )
    return domain


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
    description: str | None
    route_tags: list[str]
    member_count: int
    is_sponsored: bool = False
    funded_balance_egp: Decimal = Decimal("0.00")
    dashboard_contact_user_id: str | None = None
    sponsor_domains: list[str] = []


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


class GroupMemberResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    role: Literal["owner", "member"]
    joined_at: str


class SponsoredGroupCreateRequest(BaseModel):
    domains: list[str]
    name: str | None = None
    funded_balance_egp: Decimal

    def model_post_init(self, __context) -> None:
        domains = [d.strip().lower() for d in self.domains if d.strip()]
        if not domains:
            raise ValueError("domains must include at least one domain")
        self.domains = [_validate_domain(d) for d in domains]


class AddFundsRequest(BaseModel):
    amount_egp: Decimal


class AddFundsResponse(BaseModel):
    group_id: str
    new_funded_balance_egp: Decimal


class AddSponsorDomainRequest(BaseModel):
    domain: str

    def model_post_init(self, __context) -> None:
        self.domain = _validate_domain(self.domain)


class SponsorDomainsResponse(BaseModel):
    group_id: str
    domains: list[str]


class DashboardContactRequest(BaseModel):
    user_id: str


class DashboardContactResponse(BaseModel):
    group_id: str
    dashboard_contact_user_id: str


class SponsorshipActivityItem(BaseModel):
    type: Literal["SPONSORED_RIDE_CREDIT", "SPONSORED_RIDE_REVERSAL"]
    amount_egp: Decimal
    ride_id: str
    booking_id: str
    created_at: str


class SponsorshipDashboardResponse(BaseModel):
    funded_balance_egp: Decimal
    member_count: int
    recent_activity: list[SponsorshipActivityItem]

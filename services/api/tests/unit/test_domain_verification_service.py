from __future__ import annotations

import pytest

from app.services.domain_verification_service import _get_domain_blocklist

DEFAULT_BLOCKLISTED_DOMAINS = [
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "protonmail.com",
]


class _FakeConn:
    """No platform_settings override row — forces the default blocklist."""

    async def fetchval(self, query, *args):
        return None


class TestDomainBlocklist:
    @pytest.mark.parametrize("domain", DEFAULT_BLOCKLISTED_DOMAINS)
    async def test_default_blocklist_rejects_every_personal_provider(self, domain):
        blocklist = await _get_domain_blocklist(_FakeConn())
        assert domain in blocklist

    async def test_non_blocklisted_domain_not_rejected(self):
        blocklist = await _get_domain_blocklist(_FakeConn())
        assert "my-university.edu" not in blocklist
        assert "acme-corp.com" not in blocklist

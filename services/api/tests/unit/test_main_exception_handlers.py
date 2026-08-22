from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.main import http_exception_handler, not_found_handler


def _body(response):
    return json.loads(response.body)


@pytest.mark.asyncio
class TestHttpExceptionHandler:
    async def test_flattens_dict_detail_to_top_level(self):
        exc = HTTPException(
            status_code=409,
            detail={
                "error": "duplicate_payment_reference",
                "message": "This payment reference has already been submitted.",
            },
        )

        response = await http_exception_handler(None, exc)

        assert response.status_code == 409
        assert _body(response) == {
            "error": "duplicate_payment_reference",
            "message": "This payment reference has already been submitted.",
        }

    async def test_wraps_plain_string_detail(self):
        exc = HTTPException(status_code=400, detail="Bad request")

        response = await http_exception_handler(None, exc)

        assert response.status_code == 400
        assert _body(response) == {"error": "http_error", "message": "Bad request"}


@pytest.mark.asyncio
class TestNotFoundHandler:
    async def test_preserves_dict_detail_from_explicit_404_raise(self):
        exc = HTTPException(status_code=404, detail={"error": "not_found", "message": "Ride not found"})

        response = await not_found_handler(None, exc)

        assert response.status_code == 404
        assert _body(response) == {"error": "not_found", "message": "Ride not found"}

    async def test_falls_back_to_generic_message_for_unrouted_requests(self):
        exc = StarletteHTTPException(status_code=404, detail="Not Found")

        response = await not_found_handler(None, exc)

        assert response.status_code == 404
        assert _body(response) == {"error": "not_found", "message": "Resource not found"}

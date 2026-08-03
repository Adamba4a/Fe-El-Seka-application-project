from __future__ import annotations

import uuid

import pytest

from app.services import model_lifecycle_service as svc


# ── _decide_promotion: pure promotion-margin gating logic ───────────────────


class TestDecidePromotion:
    def test_no_champion_yet_is_always_candidate(self):
        status, margin = svc._decide_promotion(
            evaluation_score=0.60, champion_evaluation_score=None, promotion_margin=0.02
        )
        assert status == "candidate"
        assert margin == 0.60

    def test_beats_champion_by_at_least_margin_is_candidate(self):
        status, margin = svc._decide_promotion(
            evaluation_score=0.82, champion_evaluation_score=0.80, promotion_margin=0.02
        )
        assert status == "candidate"
        assert margin == pytest.approx(0.02)

    def test_below_margin_is_rejected(self):
        status, margin = svc._decide_promotion(
            evaluation_score=0.81, champion_evaluation_score=0.80, promotion_margin=0.02
        )
        assert status == "rejected"
        assert margin == pytest.approx(0.01)

    def test_worse_than_champion_is_rejected(self):
        status, margin = svc._decide_promotion(
            evaluation_score=0.70, champion_evaluation_score=0.80, promotion_margin=0.02
        )
        assert status == "rejected"
        assert margin == pytest.approx(-0.10)

    def test_exactly_at_margin_boundary_is_candidate(self):
        status, margin = svc._decide_promotion(
            evaluation_score=0.80, champion_evaluation_score=0.75, promotion_margin=0.05
        )
        assert status == "candidate"
        assert margin == pytest.approx(0.05)


# ── evaluate_and_register_candidate (mocked DB + ai_client + config) ────────


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakeConn:
    def __init__(self, champion_row=None, model_type_row=None):
        self._champion_row = champion_row
        self._model_type_row = model_type_row
        self.executed: list[tuple] = []

    async def fetchrow(self, query, *args):
        if "promotion_status = 'champion'" in query:
            return self._champion_row
        return self._model_type_row

    async def execute(self, query, *args):
        self.executed.append((query, args))


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


@pytest.mark.asyncio
class TestEvaluateAndRegisterCandidate:
    async def test_no_champion_registers_as_candidate_and_advances_to_shadow(self, monkeypatch):
        conn = _FakeConn(champion_row=None, model_type_row={"model_type": "match_score", "storage_version": "v1"})
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc, "get_continuous_learning_config", lambda: {"promotion_margin": 0.02}
        )

        shadow_calls = []

        async def _fake_advance(model_version_id):
            shadow_calls.append(model_version_id)

        monkeypatch.setattr(svc, "advance_to_shadow", _fake_advance)

        result = await svc.evaluate_and_register_candidate(
            "match_score", uuid.uuid4(), "v1", 0.75
        )

        assert result["promotion_status"] == "candidate"
        assert len(shadow_calls) == 1
        insert_calls = [c for c in conn.executed if "INSERT INTO" in c[0]]
        assert len(insert_calls) == 1
        assert insert_calls[0][1][4] == "candidate"  # promotion_status param

    async def test_beats_champion_registers_as_candidate(self, monkeypatch):
        conn = _FakeConn(champion_row={"id": uuid.uuid4(), "evaluation_score": 0.80})
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc, "get_continuous_learning_config", lambda: {"promotion_margin": 0.02}
        )

        shadow_calls = []

        async def _fake_advance(model_version_id):
            shadow_calls.append(model_version_id)

        monkeypatch.setattr(svc, "advance_to_shadow", _fake_advance)

        result = await svc.evaluate_and_register_candidate(
            "match_score", uuid.uuid4(), "v2", 0.83
        )

        assert result["promotion_status"] == "candidate"
        assert result["comparison_margin"] == pytest.approx(0.03)
        assert len(shadow_calls) == 1

    async def test_below_margin_registers_as_rejected_and_never_advances_to_shadow(self, monkeypatch):
        conn = _FakeConn(champion_row={"id": uuid.uuid4(), "evaluation_score": 0.80})
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc, "get_continuous_learning_config", lambda: {"promotion_margin": 0.02}
        )

        shadow_calls = []

        async def _fake_advance(model_version_id):
            shadow_calls.append(model_version_id)

        monkeypatch.setattr(svc, "advance_to_shadow", _fake_advance)

        result = await svc.evaluate_and_register_candidate(
            "match_score", uuid.uuid4(), "v3", 0.805
        )

        assert result["promotion_status"] == "rejected"
        assert shadow_calls == []
        insert_calls = [c for c in conn.executed if "INSERT INTO" in c[0]]
        assert insert_calls[0][1][4] == "rejected"


# ── advance_to_shadow (mocked DB + ai_client) ────────────────────────────────


@pytest.mark.asyncio
class TestAdvanceToShadow:
    async def test_sets_shadow_status_and_activates_candidate_in_ai_service(self, monkeypatch):
        model_version_id = uuid.uuid4()
        conn = _FakeConn(model_type_row={"model_type": "match_score", "storage_version": "v2"})
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        activate_calls = []

        async def _fake_activate(model_type, storage_version):
            activate_calls.append((model_type, storage_version))

        monkeypatch.setattr(svc.ai_client, "activate_shadow_candidate", _fake_activate)

        await svc.advance_to_shadow(model_version_id)

        update_calls = [c for c in conn.executed if "UPDATE" in c[0]]
        assert len(update_calls) == 1
        assert update_calls[0][1][0] == model_version_id
        assert activate_calls == [("match_score", "v2")]

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

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


# ── shadow burn-in, rollout progression, promotion (T026) ───────────────────


def _record(calls):
    async def _inner(*args, **kwargs):
        calls.append(args)
        return None

    return _inner


class _FakeTransactionCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc_info):
        return False


class _FakeConnMulti:
    """Routes fetchrow()/fetch() calls by matching a distinctive substring in
    the query text against the caller-supplied maps — needed because T031-T033
    each issue several different queries over the same connection, which the
    single-shape _FakeConn above can't express."""

    def __init__(self, fetchrow_by_key=None, fetch_by_key=None):
        self._fetchrow_by_key = fetchrow_by_key or {}
        self._fetch_by_key = fetch_by_key or {}
        self.executed: list[tuple] = []

    async def fetchrow(self, query, *args):
        for key, value in self._fetchrow_by_key.items():
            if key in query:
                return value
        raise AssertionError(f"Unmatched fetchrow query: {query}")

    async def fetch(self, query, *args):
        for key, value in self._fetch_by_key.items():
            if key in query:
                return value
        raise AssertionError(f"Unmatched fetch query: {query}")

    async def execute(self, query, *args):
        self.executed.append((query, args))

    def transaction(self):
        return _FakeTransactionCtx()


@pytest.mark.asyncio
class TestCheckShadowBurninDue:
    async def test_returns_versions_past_burnin_window(self, monkeypatch):
        due_row = {
            "id": uuid.uuid4(),
            "model_type": "match_score",
            "storage_version": "v5",
            "shadow_started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        conn = _FakeConnMulti(fetch_by_key={"promotion_status = 'shadow'": [due_row]})
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(svc, "get_continuous_learning_config", lambda: {"shadow_burnin_hours": 168})

        result = await svc.check_shadow_burnin_due()

        assert result == [due_row]


@pytest.mark.asyncio
class TestGenerateShadowComparisonReport:
    async def test_favorable_advances_to_partial_rollout(self, monkeypatch):
        model_version_id = uuid.uuid4()
        candidate_row = {
            "model_type": "match_score",
            "storage_version": "v5",
            "shadow_started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        champion_row = {"id": uuid.uuid4()}
        stats_row = {"sample_size": 20, "agreement_rate": 0.9, "outcome_alignment_rate": 0.6}

        conn = _FakeConnMulti(
            fetchrow_by_key={
                "shadow_started_at FROM public.model_versions": candidate_row,
                "promotion_status = 'champion'": champion_row,
                "WITH windowed AS": stats_row,
            }
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc,
            "get_continuous_learning_config",
            lambda: {
                "shadow_min_agreement_rate": 0.5,
                "shadow_min_outcome_alignment_rate": 0.5,
                "rollout_step_pcts": [5, 25, 50, 100],
            },
        )
        discard_calls: list[tuple] = []
        monkeypatch.setattr(svc.ai_client, "discard_candidate", _record(discard_calls))

        result = await svc.generate_shadow_comparison_report(model_version_id)

        assert result["favorable"] is True
        assert discard_calls == []
        insert_calls = [c for c in conn.executed if "INSERT INTO public.shadow_comparisons" in c[0]]
        assert len(insert_calls) == 1
        rollout_calls = [c for c in conn.executed if "partial_rollout" in c[0]]
        assert len(rollout_calls) == 1
        assert rollout_calls[0][1][0] == model_version_id
        assert rollout_calls[0][1][1] == 5

    async def test_unfavorable_retires_and_discards_candidate(self, monkeypatch):
        model_version_id = uuid.uuid4()
        candidate_row = {
            "model_type": "match_score",
            "storage_version": "v5",
            "shadow_started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        stats_row = {"sample_size": 20, "agreement_rate": 0.3, "outcome_alignment_rate": None}

        conn = _FakeConnMulti(
            fetchrow_by_key={
                "shadow_started_at FROM public.model_versions": candidate_row,
                "promotion_status = 'champion'": None,
                "WITH windowed AS": stats_row,
            }
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc,
            "get_continuous_learning_config",
            lambda: {
                "shadow_min_agreement_rate": 0.5,
                "shadow_min_outcome_alignment_rate": 0.5,
                "rollout_step_pcts": [5, 25, 50, 100],
            },
        )
        discard_calls: list[tuple] = []
        monkeypatch.setattr(svc.ai_client, "discard_candidate", _record(discard_calls))

        result = await svc.generate_shadow_comparison_report(model_version_id)

        assert result["favorable"] is False
        assert discard_calls == [("match_score",)]
        retire_calls = [c for c in conn.executed if "'retired'" in c[0]]
        assert len(retire_calls) == 1


@pytest.mark.asyncio
class TestCheckRolloutProgression:
    async def test_rollback_when_candidate_underperforms_champion(self, monkeypatch):
        model_version_id = uuid.uuid4()
        rollout_row = {
            "id": model_version_id,
            "model_type": "match_score",
            "storage_version": "v5",
            "rollout_pct": 5.0,
            "rollout_step_started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        perf_rows = [
            {"served_variant": "candidate", "total": 20, "accepted": 2},
            {"served_variant": "champion", "total": 20, "accepted": 10},
        ]
        conn = _FakeConnMulti(
            fetch_by_key={
                "promotion_status = 'partial_rollout'": [rollout_row],
                "WITH scoped AS": perf_rows,
            }
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc,
            "get_continuous_learning_config",
            lambda: {"rollback_margin": 0.05, "rollout_step_hold_hours": 24, "rollout_step_pcts": [5, 25, 50, 100]},
        )
        promote_calls: list[tuple] = []
        monkeypatch.setattr(svc, "advance_to_champion", _record(promote_calls))

        await svc.check_rollout_progression()

        retire_calls = [c for c in conn.executed if "'retired'" in c[0] and "rollout_pct = 0" in c[0]]
        assert len(retire_calls) == 1
        assert promote_calls == []

    async def test_advances_to_next_step_after_hold_elapsed(self, monkeypatch):
        model_version_id = uuid.uuid4()
        old_start = datetime.now(timezone.utc) - timedelta(hours=48)
        rollout_row = {
            "id": model_version_id,
            "model_type": "match_score",
            "storage_version": "v5",
            "rollout_pct": 5.0,
            "rollout_step_started_at": old_start,
        }
        perf_rows = [
            {"served_variant": "candidate", "total": 20, "accepted": 10},
            {"served_variant": "champion", "total": 20, "accepted": 10},
        ]
        conn = _FakeConnMulti(
            fetch_by_key={
                "promotion_status = 'partial_rollout'": [rollout_row],
                "WITH scoped AS": perf_rows,
            }
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc,
            "get_continuous_learning_config",
            lambda: {"rollback_margin": 0.05, "rollout_step_hold_hours": 24, "rollout_step_pcts": [5, 25, 50, 100]},
        )
        promote_calls: list[tuple] = []
        monkeypatch.setattr(svc, "advance_to_champion", _record(promote_calls))

        await svc.check_rollout_progression()

        step_calls = [
            c for c in conn.executed if "rollout_step_started_at = now()" in c[0] and "'retired'" not in c[0]
        ]
        assert len(step_calls) == 1
        assert step_calls[0][1] == (model_version_id, 25)
        assert promote_calls == []

    async def test_advances_to_champion_at_final_step(self, monkeypatch):
        model_version_id = uuid.uuid4()
        old_start = datetime.now(timezone.utc) - timedelta(hours=48)
        rollout_row = {
            "id": model_version_id,
            "model_type": "match_score",
            "storage_version": "v5",
            "rollout_pct": 100.0,
            "rollout_step_started_at": old_start,
        }
        perf_rows = [
            {"served_variant": "candidate", "total": 20, "accepted": 10},
            {"served_variant": "champion", "total": 20, "accepted": 10},
        ]
        conn = _FakeConnMulti(
            fetch_by_key={
                "promotion_status = 'partial_rollout'": [rollout_row],
                "WITH scoped AS": perf_rows,
            }
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc,
            "get_continuous_learning_config",
            lambda: {"rollback_margin": 0.05, "rollout_step_hold_hours": 24, "rollout_step_pcts": [5, 25, 50, 100]},
        )
        promote_calls: list[tuple] = []
        monkeypatch.setattr(svc, "advance_to_champion", _record(promote_calls))

        await svc.check_rollout_progression()

        assert promote_calls == [(model_version_id,)]


@pytest.mark.asyncio
class TestAdvanceToChampion:
    async def test_retires_old_champion_and_promotes_new_one(self, monkeypatch):
        model_version_id = uuid.uuid4()
        version_row = {"model_type": "match_score", "storage_version": "v9"}

        conn = _FakeConnMulti(
            fetchrow_by_key={"model_type, storage_version FROM public.model_versions": version_row}
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        promote_calls: list[tuple] = []

        async def _fake_promote(model_type, storage_version):
            promote_calls.append((model_type, storage_version))

        monkeypatch.setattr(svc.ai_client, "promote_model", _fake_promote)

        await svc.advance_to_champion(model_version_id)

        assert promote_calls == [("match_score", "v9")]
        retire_old = [
            c
            for c in conn.executed
            if "promotion_status = 'champion'" in c[0] and "SET promotion_status = 'retired'" in c[0]
        ]
        assert len(retire_old) == 1
        set_new_champion = [c for c in conn.executed if "SET promotion_status = 'champion'" in c[0]]
        assert len(set_new_champion) == 1
        assert set_new_champion[0][1] == (model_version_id,)


class TestGetRoutingDecision:
    def test_no_cache_entry_always_champion(self, monkeypatch):
        monkeypatch.setattr(svc, "_rollout_cache", {})

        result = svc.get_routing_decision("match_score")

        assert result == {"variant": "champion", "candidate_storage_version": None}

    def test_cache_entry_below_roll_selects_candidate(self, monkeypatch):
        monkeypatch.setattr(
            svc, "_rollout_cache", {"match_score": {"storage_version": "v5", "rollout_pct": 50.0}}
        )
        monkeypatch.setattr(svc.random, "random", lambda: 0.1)

        result = svc.get_routing_decision("match_score")

        assert result == {"variant": "candidate", "candidate_storage_version": "v5"}

    def test_cache_entry_above_roll_selects_champion(self, monkeypatch):
        monkeypatch.setattr(
            svc, "_rollout_cache", {"match_score": {"storage_version": "v5", "rollout_pct": 50.0}}
        )
        monkeypatch.setattr(svc.random, "random", lambda: 0.9)

        result = svc.get_routing_decision("match_score")

        assert result == {"variant": "champion", "candidate_storage_version": None}

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import ai_client as ai_client_module
from app.services import dataset_pipeline_service, model_lifecycle_service, retraining_scheduler_service
from app.services import storage_service as storage_service_module


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakeTransactionCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


class _FakeConnMulti:
    """Shared in-memory stand-in for the DB connection across the whole
    pipeline (dataset_pipeline_service -> model_lifecycle_service via
    retraining_scheduler_service). Routes fetchrow()/fetch() by matching a
    distinctive substring of the query text — the same convention already
    used by the unit test suites for these services. fetchrow_by_key/
    fetch_by_key are mutated mid-test as later steps need canned responses
    keyed on the model_version_id the earlier steps generated."""

    def __init__(self, fetchrow_by_key=None, fetch_by_key=None):
        self.fetchrow_by_key = fetchrow_by_key or {}
        self.fetch_by_key = fetch_by_key or {}
        self.executed: list[tuple] = []

    async def fetchrow(self, query, *args):
        for key, value in self.fetchrow_by_key.items():
            if key in query:
                return value
        raise AssertionError(f"Unmatched fetchrow query: {query}")

    async def fetch(self, query, *args):
        for key, value in self.fetch_by_key.items():
            if key in query:
                return value
        raise AssertionError(f"Unmatched fetch query: {query}")

    async def execute(self, query, *args):
        self.executed.append((query, args))

    def transaction(self):
        return _FakeTransactionCtx()


def _seeded_join_rows(now: datetime) -> list[dict]:
    """Three fully-completed, highly-rated match events — real _JOIN_QUERY
    already aggregates per match_event/search_session server-side, so the
    fake just returns rows in that already-grouped shape."""
    rows = []
    for _ in range(3):
        rows.append({
            "match_event_id": uuid.uuid4(),
            "search_id": uuid.uuid4(),
            "passenger_id": uuid.uuid4(),
            "driver_id": uuid.uuid4(),
            "match_event_created_at": now - timedelta(days=1),
            "feature_vector": {"overlap_pct": 80, "pickup_walk_m": 200, "dropoff_walk_m": 300},
            "passenger_origin_lat": 30.0131, "passenger_origin_lng": 31.2089,
            "passenger_dest_lat": 30.0626, "passenger_dest_lng": 31.3462,
            "desired_departure_at": now,
            "driver_origin_lat": 30.0131, "driver_origin_lng": 31.2089,
            "driver_dest_lat": 30.0626, "driver_dest_lng": 31.3462,
            "passenger_verification_status": "verified",
            "driver_verification_status": "verified",
            "passenger_suspended_by_report": False,
            "driver_suspended_by_report": False,
            "transitions": ["requested", "accepted", "completed"],
            "rating_stars": 5,
            "passenger_training_valid_from": None,
            "driver_training_valid_from": None,
        })
    return rows


@pytest.mark.asyncio
async def test_seeded_events_flow_through_snapshot_retrain_promotion_rollout_and_rollback(monkeypatch):
    now = datetime.now(timezone.utc)

    conn = _FakeConnMulti(
        fetchrow_by_key={
            # _cadence_elapsed(): no prior model_versions row for match_score yet.
            "SELECT created_at FROM public.model_versions": None,
            # evaluate_and_register_candidate() / generate_shadow_comparison_report():
            # no champion for the entire scenario (never reaches advance_to_champion).
            "promotion_status = 'champion'": None,
            # advance_to_shadow()
            "SELECT model_type, storage_version FROM public.model_versions WHERE id = $1": {
                "model_type": "match_score", "storage_version": "v1",
            },
            # generate_shadow_comparison_report()'s candidate fetch
            "storage_version, shadow_started_at FROM public.model_versions WHERE id = $1": {
                "model_type": "match_score", "storage_version": "v1",
                "shadow_started_at": now - timedelta(hours=200),
            },
            # burn-in stats: strong agreement -> favorable
            "WITH windowed AS": {"sample_size": 40, "agreement_rate": 0.92, "outcome_alignment_rate": 0.7},
        },
        fetch_by_key={
            # dataset_pipeline_service._JOIN_QUERY (count_eligible_rows + generate_dataset_snapshot)
            "JOIN public.rides r ON r.id = me.candidate_ride_id": _seeded_join_rows(now),
        },
    )
    pool = _FakePool(conn)

    monkeypatch.setattr(dataset_pipeline_service, "get_pool", lambda: pool)
    monkeypatch.setattr(model_lifecycle_service, "get_pool", lambda: pool)
    monkeypatch.setattr(retraining_scheduler_service, "get_pool", lambda: pool)

    monkeypatch.setattr(
        retraining_scheduler_service, "get_continuous_learning_config",
        lambda: {"retraining_cadence_hours": 168, "min_dataset_size": 1},
    )
    monkeypatch.setattr(
        model_lifecycle_service, "get_continuous_learning_config",
        lambda: {
            "promotion_margin": 0.02,
            "shadow_min_agreement_rate": 0.5,
            "shadow_min_outcome_alignment_rate": 0.5,
            "rollout_step_pcts": [5, 25, 50, 100],
            "rollback_margin": 0.05,
            "rollout_step_hold_hours": 24,
        },
    )

    upload_calls: list[tuple] = []
    monkeypatch.setattr(
        storage_service_module, "upload_file",
        lambda bucket, path, data, content_type: upload_calls.append((bucket, path, content_type)),
    )

    retrain_calls: list[tuple] = []

    async def _fake_retrain_model(model_type, storage_path, snapshot_id):
        retrain_calls.append((model_type, storage_path, snapshot_id))
        return {"status": "trained", "storage_version": "v1", "evaluation_score": 0.75}

    activate_calls: list[tuple] = []

    async def _fake_activate_shadow_candidate(model_type, storage_version):
        activate_calls.append((model_type, storage_version))

    monkeypatch.setattr(ai_client_module, "retrain_model", _fake_retrain_model)
    monkeypatch.setattr(ai_client_module, "activate_shadow_candidate", _fake_activate_shadow_candidate)

    # ── Step 1: dataset snapshot -> mock retrain -> promotion decision ──────
    await retraining_scheduler_service._attempt_retrain("match_score")

    assert upload_calls == [("training-datasets", upload_calls[0][1], "application/octet-stream")]
    assert len(retrain_calls) == 1
    assert retrain_calls[0][0] == "match_score"
    assert activate_calls == [("match_score", "v1")]

    insert_version_call = next(
        c for c in conn.executed if "INSERT INTO public.model_versions" in c[0]
    )
    model_version_id = insert_version_call[1][0]
    assert insert_version_call[1][4] == "candidate"  # no champion yet -> always candidate

    shadow_update_calls = [
        c for c in conn.executed
        if "SET promotion_status = 'shadow'" in c[0]
    ]
    assert len(shadow_update_calls) == 1
    assert shadow_update_calls[0][1] == (model_version_id,)

    # ── Step 2: shadow burn-in comparison -> favorable -> partial_rollout ───
    report = await model_lifecycle_service.generate_shadow_comparison_report(model_version_id)
    assert report["favorable"] is True

    rollout_calls = [c for c in conn.executed if "SET promotion_status = 'partial_rollout'" in c[0]]
    assert len(rollout_calls) == 1
    assert rollout_calls[0][1] == (model_version_id, 5)

    # ── Step 3: rollout progression sees the candidate underperforming ──────
    #    the champion -> automatic rollback (FR-012), reusing rollback_version().
    conn.fetch_by_key["promotion_status = 'partial_rollout'"] = [{
        "id": model_version_id,
        "model_type": "match_score",
        "storage_version": "v1",
        "rollout_pct": 5.0,
        "rollout_step_started_at": now - timedelta(hours=1),
    }]
    conn.fetch_by_key["WITH scoped AS"] = [
        {"served_variant": "candidate", "total": 20, "accepted": 2},
        {"served_variant": "champion", "total": 20, "accepted": 15},
    ]

    await model_lifecycle_service.check_rollout_progression()

    rollback_calls = [
        c for c in conn.executed
        if "SET promotion_status = 'retired', rollout_pct = 0" in c[0]
    ]
    assert len(rollback_calls) == 1
    assert rollback_calls[0][1] == (model_version_id,)

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import dataset_pipeline_service as svc


def _row(**overrides):
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    base = {
        "match_event_id": uuid.uuid4(),
        "search_id": uuid.uuid4(),
        "passenger_id": uuid.uuid4(),
        "driver_id": uuid.uuid4(),
        "match_event_created_at": now,
        "feature_vector": {
            "overlap_pct": 80.0,
            "pickup_walk_m": 200.0,
            "dropoff_walk_m": 150.0,
        },
        "passenger_origin_lat": 30.05,
        "passenger_origin_lng": 31.24,
        "passenger_dest_lat": 30.06,
        "passenger_dest_lng": 31.25,
        "desired_departure_at": now,
        "driver_origin_lat": 30.04,
        "driver_origin_lng": 31.23,
        "driver_dest_lat": 30.07,
        "driver_dest_lng": 31.26,
        "passenger_verification_status": "verified",
        "driver_verification_status": "verified",
        "passenger_suspended_by_report": False,
        "driver_suspended_by_report": False,
        "transitions": [],
        "rating_stars": None,
    }
    base.update(overrides)
    return base


# ── FR-002 labeling hierarchy ────────────────────────────────────────────────


class TestSignalStrengthTier:
    def test_completed_highly_rated(self):
        assert svc._signal_strength_tier(["requested", "accepted", "completed"], 5) == "completed_highly_rated"

    def test_completed_but_below_rating_threshold_is_unrated_tier(self):
        assert svc._signal_strength_tier(["completed"], 3) == "completed_unrated"

    def test_completed_with_no_rating_is_unrated_tier(self):
        assert svc._signal_strength_tier(["completed"], None) == "completed_unrated"

    def test_accepted_not_completed_is_booked_not_completed(self):
        assert svc._signal_strength_tier(["requested", "accepted"], None) == "booked_not_completed"

    def test_cancellation_folds_into_booked_not_completed_not_a_negative(self):
        # A cancelled booking still expressed intent — never an automatic negative.
        assert svc._signal_strength_tier(["requested", "cancelled"], None) == "booked_not_completed"

    def test_cancellation_after_acceptance_still_booked_not_completed(self):
        assert svc._signal_strength_tier(["requested", "accepted", "cancelled"], None) == "booked_not_completed"

    def test_shown_not_booked_when_only_requested(self):
        assert svc._signal_strength_tier(["requested"], None) == "shown_not_booked"

    def test_shown_not_booked_when_no_transitions_at_all(self):
        assert svc._signal_strength_tier([], None) == "shown_not_booked"

    def test_rejected_without_acceptance_is_shown_not_booked(self):
        assert svc._signal_strength_tier(["requested", "rejected"], None) == "shown_not_booked"


# ── FR-003 fraud/suspension exclusion ────────────────────────────────────────


class TestIsExcluded:
    def test_included_when_both_verified(self):
        assert svc._is_excluded(_row()) is False

    def test_excluded_when_passenger_suspended(self):
        assert svc._is_excluded(_row(passenger_verification_status="suspended")) is True

    def test_excluded_when_driver_suspended(self):
        assert svc._is_excluded(_row(driver_verification_status="suspended")) is True

    def test_excluded_when_passenger_rejected(self):
        assert svc._is_excluded(_row(passenger_verification_status="rejected")) is True

    def test_excluded_when_passenger_has_suspend_report(self):
        assert svc._is_excluded(_row(passenger_suspended_by_report=True)) is True

    def test_excluded_when_driver_has_suspend_report(self):
        assert svc._is_excluded(_row(driver_suspended_by_report=True)) is True

    def test_pending_review_status_not_excluded(self):
        assert svc._is_excluded(_row(passenger_verification_status="pending_review")) is False


# ── FR-004 retention-window exclusion ────────────────────────────────────────


class TestRetentionWindow:
    def test_recent_row_within_window(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        row = _row(match_event_created_at=now - timedelta(days=1))
        assert svc._within_retention_window(row, now) is True

    def test_row_older_than_retention_window_excluded(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        row = _row(match_event_created_at=now - timedelta(days=svc._DATA_RETENTION_DAYS + 1))
        assert svc._within_retention_window(row, now) is False

    def test_row_exactly_at_boundary_is_included(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        row = _row(match_event_created_at=now - timedelta(days=svc._DATA_RETENTION_DAYS))
        assert svc._within_retention_window(row, now) is True


# ── _process_rows integration of exclusion + labeling ────────────────────────


class TestProcessRows:
    def test_mixed_batch_excludes_and_labels_correctly(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        rows = [
            _row(transitions=["completed"], rating_stars=5),  # included, completed_highly_rated
            _row(passenger_verification_status="suspended"),  # excluded: fraud/suspension
            _row(match_event_created_at=now - timedelta(days=svc._DATA_RETENTION_DAYS + 10)),  # excluded: retention
            _row(transitions=["requested", "cancelled"]),  # included, booked_not_completed
        ]

        included, excluded_count, summary = svc._process_rows(rows, now)

        assert len(included) == 2
        assert excluded_count == 2
        assert summary == {"fraud_or_suspension": 1, "retention_window": 1}
        tiers = {r["signal_strength_tier"] for r in included}
        assert tiers == {"completed_highly_rated", "booked_not_completed"}

    def test_feature_vector_unit_conversion(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        rows = [_row(feature_vector={"overlap_pct": 60.0, "pickup_walk_m": 400.0, "dropoff_walk_m": 250.0})]

        included, _, _ = svc._process_rows(rows, now)

        assert included[0]["overlap_ratio"] == pytest.approx(0.6)
        assert included[0]["pickup_detour_km"] == pytest.approx(0.4)
        assert included[0]["dropoff_distance_km"] == pytest.approx(0.25)

    def test_match_prob_and_label_follow_tier(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        rows = [_row(transitions=["completed"], rating_stars=5)]

        included, _, _ = svc._process_rows(rows, now)

        assert included[0]["match_prob"] == 0.95
        assert included[0]["match_label"] == 1


# ── FR-004 anonymization ──────────────────────────────────────────────────────


class TestAnonymize:
    def test_only_allowlisted_columns_survive(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        included, _, _ = svc._process_rows([_row()], now)

        anonymized = svc._anonymize(included)

        assert set(anonymized[0].keys()) == set(svc._PARQUET_COLUMNS)
        assert "_match_event_created_at" not in anonymized[0]
        # passenger_id/driver_id retained only as opaque UUIDs, per
        # contracts/dataset-pipeline.md step 5 — no other identifying fields.
        assert anonymized[0]["passenger_id"] is not None
        assert anonymized[0]["driver_id"] is not None


# ── generate_dataset_snapshot / get_labeled_row_count (mocked DB + storage) ──


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakeConn:
    def __init__(self, fetch_rows=None, fetchrow_result=None):
        self._fetch_rows = fetch_rows or []
        self._fetchrow_result = fetchrow_result
        self.executed_params: list[tuple] = []

    async def fetch(self, query, *args):
        return self._fetch_rows

    async def execute(self, query, *args):
        self.executed_params.append(args)

    async def fetchrow(self, query, *args):
        return self._fetchrow_result


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


@pytest.mark.asyncio
class TestGenerateDatasetSnapshot:
    async def test_upload_failure_prevents_dataset_snapshots_insert(self, monkeypatch):
        conn = _FakeConn(fetch_rows=[_row(transitions=["completed"], rating_stars=5)])
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        def _boom(*args, **kwargs):
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(svc.storage_service, "upload_file", _boom)

        with pytest.raises(RuntimeError):
            await svc.generate_dataset_snapshot("match_score")

        assert conn.executed_params == []

    async def test_successful_run_uploads_then_inserts_snapshot_row(self, monkeypatch):
        conn = _FakeConn(fetch_rows=[_row(transitions=["completed"], rating_stars=5)])
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        uploaded = {}

        def _capture_upload(bucket, path, data, content_type):
            uploaded["bucket"] = bucket
            uploaded["path"] = path
            return path

        monkeypatch.setattr(svc.storage_service, "upload_file", _capture_upload)

        result = await svc.generate_dataset_snapshot("match_score")

        assert uploaded["bucket"] == "training-datasets"
        assert result["row_count"] == 1
        assert result["excluded_count"] == 0
        assert len(conn.executed_params) == 1
        assert conn.executed_params[0][1] == "match_score"  # model_type param


@pytest.mark.asyncio
class TestCountEligibleRows:
    async def test_counts_included_rows_without_uploading(self, monkeypatch):
        conn = _FakeConn(fetch_rows=[
            _row(transitions=["completed"], rating_stars=5),
            _row(transitions=["completed"], rating_stars=5),
        ])
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        def _boom(*args, **kwargs):
            raise AssertionError("count_eligible_rows must not touch Storage")

        monkeypatch.setattr(svc.storage_service, "upload_file", _boom)

        count = await svc.count_eligible_rows()

        assert count == 2
        assert conn.executed_params == []  # no dataset_snapshots insert either

    async def test_excludes_suspended_rows_from_count(self, monkeypatch):
        conn = _FakeConn(fetch_rows=[
            _row(transitions=["completed"], rating_stars=5),
            _row(transitions=["completed"], rating_stars=5, passenger_verification_status="suspended"),
        ])
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        count = await svc.count_eligible_rows()

        assert count == 1


@pytest.mark.asyncio
class TestGetLabeledRowCount:
    async def test_returns_row_count_for_existing_snapshot(self, monkeypatch):
        conn = _FakeConn(fetchrow_result={"row_count": 42})
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        count = await svc.get_labeled_row_count("match_score", uuid.uuid4())

        assert count == 42

    async def test_returns_zero_when_snapshot_missing(self, monkeypatch):
        conn = _FakeConn(fetchrow_result=None)
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        count = await svc.get_labeled_row_count("match_score", uuid.uuid4())

        assert count == 0

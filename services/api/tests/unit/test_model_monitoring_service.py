from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import model_monitoring_service as svc

# ── _aggregate_by_zone: pure per-search-row -> per-zone metric grouping ─────


class TestAggregateByZone:
    def test_groups_rows_by_nearest_zone_and_computes_rates(self):
        # Exact Maadi / Nasr City centroids, per app/utils/zone_lookup.py CAIRO_ZONES
        maadi_rows = [
            {"origin_lat": 30.0131, "origin_lng": 31.2089, "predicted_score": 0.8, "accepted": True, "completed": True},
            {
                "origin_lat": 30.0131,
                "origin_lng": 31.2089,
                "predicted_score": 0.6,
                "accepted": False,
                "completed": False,
            },
        ]
        nasr_city_rows = [
            {
                "origin_lat": 30.0626,
                "origin_lng": 31.3462,
                "predicted_score": 0.9,
                "accepted": True,
                "completed": False,
            },
        ]

        result = svc._aggregate_by_zone(maadi_rows + nasr_city_rows)

        assert result["Maadi"]["sample_size"] == 2
        assert result["Maadi"]["prediction_distribution"] == pytest.approx(0.7)
        assert result["Maadi"]["acceptance_rate"] == pytest.approx(0.5)
        assert result["Maadi"]["completion_rate"] == pytest.approx(0.5)

        assert result["Nasr City"]["sample_size"] == 1
        assert result["Nasr City"]["acceptance_rate"] == pytest.approx(1.0)
        assert result["Nasr City"]["completion_rate"] == pytest.approx(0.0)

    def test_skips_rows_missing_origin_coordinates(self):
        rows = [{"origin_lat": None, "origin_lng": None, "predicted_score": 0.8, "accepted": True, "completed": True}]

        result = svc._aggregate_by_zone(rows)

        assert result == {}

    def test_empty_input_returns_empty_dict(self):
        assert svc._aggregate_by_zone([]) == {}


# ── _alert_raised: pure baseline-margin comparison ───────────────────────────


class TestAlertRaised:
    def test_no_baseline_yet_never_alerts(self):
        assert svc._alert_raised(0.9, None, 0.1) is False

    def test_no_value_never_alerts(self):
        assert svc._alert_raised(None, 0.5, 0.1) is False

    def test_within_margin_does_not_alert(self):
        assert svc._alert_raised(0.55, 0.5, 0.1) is False

    def test_at_margin_boundary_alerts(self):
        assert svc._alert_raised(0.6, 0.5, 0.1) is True

    def test_beyond_margin_alerts(self):
        assert svc._alert_raised(0.2, 0.5, 0.1) is True

    def test_degradation_in_either_direction_alerts(self):
        assert svc._alert_raised(0.8, 0.5, 0.1) is True


# ── _spot_audit_due: pure cadence gating with early-window halving ──────────


class TestSpotAuditDue:
    def test_never_sampled_before_is_always_due(self):
        now = datetime(2026, 8, 4, tzinfo=timezone.utc)
        anchor_at = now - timedelta(hours=1)
        assert svc._spot_audit_due(anchor_at, None, 24, 72, now) is True

    def test_within_normal_cadence_window_not_due(self):
        now = datetime(2026, 8, 4, tzinfo=timezone.utc)
        anchor_at = now - timedelta(hours=200)  # outside early window
        last_sampled_at = now - timedelta(hours=5)
        assert svc._spot_audit_due(anchor_at, last_sampled_at, 24, 72, now) is False

    def test_normal_cadence_elapsed_is_due(self):
        now = datetime(2026, 8, 4, tzinfo=timezone.utc)
        anchor_at = now - timedelta(hours=200)
        last_sampled_at = now - timedelta(hours=25)
        assert svc._spot_audit_due(anchor_at, last_sampled_at, 24, 72, now) is True

    def test_early_window_halves_cadence(self):
        now = datetime(2026, 8, 4, tzinfo=timezone.utc)
        anchor_at = now - timedelta(hours=10)  # within 72h early window
        last_sampled_at = now - timedelta(hours=13)  # < 24h (normal) but >= 12h (halved)
        assert svc._spot_audit_due(anchor_at, last_sampled_at, 24, 72, now) is True

    def test_within_halved_early_window_cadence_not_due(self):
        now = datetime(2026, 8, 4, tzinfo=timezone.utc)
        anchor_at = now - timedelta(hours=10)
        last_sampled_at = now - timedelta(hours=5)
        assert svc._spot_audit_due(anchor_at, last_sampled_at, 24, 72, now) is False


# ── run_hourly_aggregation (mocked DB + config) ──────────────────────────────


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
    """Routes fetchrow()/fetch() calls by matching a distinctive substring in
    the query text — mirrors the convention already established in
    test_model_lifecycle_service.py."""

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
class TestRunHourlyAggregation:
    async def test_inserts_metric_rows_and_flags_alert_when_beyond_baseline(self, monkeypatch):
        champion_id = uuid.uuid4()
        champion_row = {"id": champion_id, "storage_version": "v3"}
        raw_rows = [
            {
                "origin_lat": 29.9602,
                "origin_lng": 31.2569,
                "predicted_score": 0.2,
                "accepted": False,
                "completed": False,
            },
        ]

        conn = _FakeConnMulti(
            fetchrow_by_key={
                "promotion_status = 'champion'": champion_row,
                "promotion_status = 'partial_rollout'": None,
                "AVG(value)": {"baseline": 0.9},  # far from measured 0.0 acceptance_rate -> alert
            },
            fetch_by_key={"FROM public.match_events me": raw_rows},
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc, "get_continuous_learning_config",
            lambda: {"monitoring_interval_hours": 1, "alert_baseline_margin": 0.1},
        )

        await svc.run_hourly_aggregation("match_score")

        insert_calls = [c for c in conn.executed if "INSERT INTO public.model_monitoring_metrics" in c[0]]
        assert len(insert_calls) == 3  # prediction_distribution, acceptance_rate, completion_rate
        alert_flags = {c[1][3]: c[1][8] for c in insert_calls}  # metric_type -> alert_raised
        assert alert_flags["acceptance_rate"] is True  # 0.0 vs baseline 0.9, margin 0.1
        assert alert_flags["completion_rate"] is True  # 0.0 vs baseline 0.9

    async def test_no_champion_or_rollout_is_a_noop(self, monkeypatch):
        conn = _FakeConnMulti(
            fetchrow_by_key={
                "promotion_status = 'champion'": None,
                "promotion_status = 'partial_rollout'": None,
            },
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc, "get_continuous_learning_config",
            lambda: {"monitoring_interval_hours": 1, "alert_baseline_margin": 0.1},
        )

        await svc.run_hourly_aggregation("match_score")

        assert conn.executed == []


# ── record_spot_audit_samples (mocked DB + config) ───────────────────────────


@pytest.mark.asyncio
class TestRecordSpotAuditSamples:
    async def test_samples_due_champion_and_inserts_unreviewed_audits(self, monkeypatch):
        champion_id = uuid.uuid4()
        champion_row = {
            "id": champion_id, "storage_version": "v3",
            "promoted_at": datetime.now(timezone.utc) - timedelta(hours=500),
        }
        match_event_rows = [{"id": uuid.uuid4()}, {"id": uuid.uuid4()}]

        conn = _FakeConnMulti(
            fetchrow_by_key={
                "promotion_status = 'champion'": champion_row,
                "promotion_status = 'partial_rollout'": None,
                "MAX(sampled_at)": {"last_sampled_at": None},
            },
            fetch_by_key={"FROM public.match_events": match_event_rows},
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc, "get_continuous_learning_config",
            lambda: {
                "spot_audit_sample_size": 10,
                "spot_audit_frequency_hours": 24,
                "spot_audit_early_window_hours": 72,
            },
        )

        await svc.record_spot_audit_samples()

        insert_calls = [c for c in conn.executed if "INSERT INTO public.model_spot_audits" in c[0]]
        # the fake connection routes purely by query text (not bind params), so
        # both _MODEL_TYPES ("match_score", "ride_ranker") resolve to the same
        # champion_row here: 2 model_types x 2 sampled match_events = 4 inserts
        assert len(insert_calls) == 4
        for call in insert_calls:
            assert call[1][1] == champion_id  # model_version_id param

    async def test_not_due_skips_sampling(self, monkeypatch):
        champion_id = uuid.uuid4()
        champion_row = {
            "id": champion_id, "storage_version": "v3",
            "promoted_at": datetime.now(timezone.utc) - timedelta(hours=500),
        }

        conn = _FakeConnMulti(
            fetchrow_by_key={
                "promotion_status = 'champion'": champion_row,
                "promotion_status = 'partial_rollout'": None,
                "MAX(sampled_at)": {"last_sampled_at": datetime.now(timezone.utc) - timedelta(hours=1)},
            },
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)
        monkeypatch.setattr(
            svc, "get_continuous_learning_config",
            lambda: {
                "spot_audit_sample_size": 10,
                "spot_audit_frequency_hours": 24,
                "spot_audit_early_window_hours": 72,
            },
        )

        await svc.record_spot_audit_samples()

        assert conn.executed == []


# ── apply_spot_audit_finding (mocked DB) ─────────────────────────────────────


@pytest.mark.asyncio
class TestApplySpotAuditFinding:
    async def test_records_finding_without_rollback(self, monkeypatch):
        spot_audit_id = uuid.uuid4()
        model_version_id = uuid.uuid4()
        reviewer_admin_id = uuid.uuid4()

        conn = _FakeConnMulti(
            fetchrow_by_key={
                "FROM public.model_spot_audits WHERE id": {"model_version_id": model_version_id},
            },
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        rollback_calls: list[tuple] = []

        async def _fake_rollback(mv_id, conn=None):
            rollback_calls.append((mv_id, conn))

        monkeypatch.setattr(svc.model_lifecycle_service, "rollback_version", _fake_rollback)

        await svc.apply_spot_audit_finding(spot_audit_id, reviewer_admin_id, "looks fine", False)

        update_calls = [c for c in conn.executed if "UPDATE public.model_spot_audits" in c[0]]
        assert len(update_calls) == 1
        assert update_calls[0][1] == (reviewer_admin_id, "looks fine", False, spot_audit_id)
        assert rollback_calls == []

    async def test_trigger_rollback_calls_rollback_version_with_same_connection(self, monkeypatch):
        spot_audit_id = uuid.uuid4()
        model_version_id = uuid.uuid4()
        reviewer_admin_id = uuid.uuid4()

        conn = _FakeConnMulti(
            fetchrow_by_key={
                "FROM public.model_spot_audits WHERE id": {"model_version_id": model_version_id},
            },
        )
        pool = _FakePool(conn)
        monkeypatch.setattr(svc, "get_pool", lambda: pool)

        rollback_calls: list[tuple] = []

        async def _fake_rollback(mv_id, conn=None):
            rollback_calls.append((mv_id, conn))

        monkeypatch.setattr(svc.model_lifecycle_service, "rollback_version", _fake_rollback)

        await svc.apply_spot_audit_finding(spot_audit_id, reviewer_admin_id, "bad match", True)

        assert rollback_calls == [(model_version_id, conn)]

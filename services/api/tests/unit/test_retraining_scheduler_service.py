from __future__ import annotations

import uuid

import pytest

from app.services import retraining_scheduler_service as svc


@pytest.mark.asyncio
class TestAttemptRetrain:
    async def test_skips_when_cadence_not_elapsed(self, monkeypatch):
        monkeypatch.setattr(svc, "get_continuous_learning_config", lambda: {
            "retraining_cadence_hours": 168, "min_dataset_size": 500,
        })
        monkeypatch.setattr(svc, "_cadence_elapsed", _async_return(False))

        count_calls = []
        monkeypatch.setattr(
            svc.dataset_pipeline_service, "count_eligible_rows",
            _async_return_recording(count_calls, 999),
        )

        await svc._attempt_retrain("match_score")

        assert count_calls == []  # never even checked row count

    async def test_below_min_dataset_size_never_generates_full_snapshot(self, monkeypatch):
        monkeypatch.setattr(svc, "get_continuous_learning_config", lambda: {
            "retraining_cadence_hours": 168, "min_dataset_size": 500,
        })
        monkeypatch.setattr(svc, "_cadence_elapsed", _async_return(True))
        monkeypatch.setattr(svc.dataset_pipeline_service, "count_eligible_rows", _async_return(10))

        def _boom(*args, **kwargs):
            raise AssertionError("generate_dataset_snapshot must not run below min_dataset_size")

        monkeypatch.setattr(svc.dataset_pipeline_service, "generate_dataset_snapshot", _boom)

        await svc._attempt_retrain("match_score")  # no exception -> pre-check short-circuited

    async def test_above_threshold_runs_full_pipeline_and_registers_candidate(self, monkeypatch):
        monkeypatch.setattr(svc, "get_continuous_learning_config", lambda: {
            "retraining_cadence_hours": 168, "min_dataset_size": 500,
        })
        monkeypatch.setattr(svc, "_cadence_elapsed", _async_return(True))
        monkeypatch.setattr(svc.dataset_pipeline_service, "count_eligible_rows", _async_return(600))

        snapshot_id = uuid.uuid4()
        monkeypatch.setattr(
            svc.dataset_pipeline_service, "generate_dataset_snapshot",
            _async_return(
                {
                    "snapshot_id": snapshot_id,
                    "storage_path": "match_score/x/dataset.parquet",
                    "row_count": 600,
                }
            ),
        )
        monkeypatch.setattr(
            svc.ai_client, "retrain_model",
            _async_return({"status": "trained", "storage_version": "v9", "evaluation_score": 0.71}),
        )

        register_calls = []
        monkeypatch.setattr(
            svc.model_lifecycle_service, "evaluate_and_register_candidate",
            _async_return_recording(register_calls, None),
        )

        await svc._attempt_retrain("match_score")

        assert register_calls == [("match_score", snapshot_id, "v9", 0.71)]

    async def test_gate_failed_does_not_register_candidate(self, monkeypatch):
        monkeypatch.setattr(svc, "get_continuous_learning_config", lambda: {
            "retraining_cadence_hours": 168, "min_dataset_size": 500,
        })
        monkeypatch.setattr(svc, "_cadence_elapsed", _async_return(True))
        monkeypatch.setattr(svc.dataset_pipeline_service, "count_eligible_rows", _async_return(600))
        monkeypatch.setattr(
            svc.dataset_pipeline_service, "generate_dataset_snapshot",
            _async_return({"snapshot_id": uuid.uuid4(), "storage_path": "p", "row_count": 600}),
        )
        monkeypatch.setattr(
            svc.ai_client, "retrain_model",
            _async_return({"status": "gate_failed", "reason": "auc_roc_below_threshold"}),
        )

        def _boom(*args, **kwargs):
            raise AssertionError("evaluate_and_register_candidate must not run on gate_failed")

        monkeypatch.setattr(svc.model_lifecycle_service, "evaluate_and_register_candidate", _boom)

        await svc._attempt_retrain("match_score")  # no exception -> handled as a no-op


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner


def _async_return_recording(calls, value):
    async def _inner(*args, **kwargs):
        calls.append(args)
        return value
    return _inner

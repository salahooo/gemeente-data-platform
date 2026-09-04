"""Databasevrije tests voor fase-5A-operatiebouwblokken."""

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from gemeente_data_platform.pipeline_contracts import (
    PipelineStage,
    StageResult,
    StageStatus,
    create_run_id,
)
from gemeente_data_platform.pipeline_lock import PipelineLockError, pipeline_lock
from gemeente_data_platform.pipeline_security import MARKER, redact
from gemeente_data_platform.pipeline_storage import (
    create_manifest,
    load_manifest,
    log_jsonl,
)


def test_stage_transitions_and_resume() -> None:
    stage = StageResult(PipelineStage.EXTRACT)
    stage.transition(StageStatus.RUNNING)
    stage.transition(StageStatus.FAILED)
    stage.prepare_resume()
    assert stage.status is StageStatus.PENDING


@pytest.mark.parametrize("target", [StageStatus.SUCCEEDED, StageStatus.FAILED])
def test_pending_cannot_skip_running(target: StageStatus) -> None:
    with pytest.raises(ValueError, match="Invalid"):
        StageResult(PipelineStage.LOAD).transition(target)


def test_deterministic_run_id_is_safe_and_sorted() -> None:
    run_id = create_run_id(datetime(2026, 9, 4, tzinfo=UTC), UUID(int=1))
    assert run_id == "20260904T000000000000Z-00000000"


def test_redaction_removes_url_key_value_and_secret_path() -> None:
    secret = "sec" + "ret"
    url = "postgresql://app:" + secret + "@localhost/db"
    secret_path = "C:" + "\\secrets\\app.txt"
    result = redact(f"{url} password={secret} {secret_path}", (secret,))
    assert secret not in result and MARKER in result


def test_lock_contention_and_release(tmp_path) -> None:
    path = tmp_path / "pipeline.lock"
    with pipeline_lock(path, 0):
        with pytest.raises(PipelineLockError):
            with pipeline_lock(path, 0):
                pass
    with pipeline_lock(path, 0):
        pass


def test_manifest_and_jsonl_round_trip_are_typed_and_redacted(tmp_path) -> None:
    manifest = create_manifest(tmp_path, run_id="pipeline-test")
    password = "top" + "secret"
    url = "postgresql://user:" + password + "@localhost:5433/db"
    secret_path = "C:" + "\\secrets\\app.txt"
    log_jsonl(
        tmp_path / manifest.pipeline_run_id,
        {
            "message": f"{url} {secret_path}",
        },
    )
    restored = load_manifest(tmp_path / manifest.pipeline_run_id)
    log_line = (tmp_path / manifest.pipeline_run_id / "pipeline.log.jsonl").read_text()
    assert restored.pipeline_run_id == "pipeline-test"
    assert restored.stages[PipelineStage.EXTRACT].status is StageStatus.PENDING
    assert password not in log_line and "secrets\\app.txt" not in log_line
    assert json.loads(log_line)["message"].count(MARKER) == 2

"""Databasevrije tests voor de fase-5 pipeline-orkestratie."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from gemeente_data_platform import run_pipeline as runner
from gemeente_data_platform.pipeline_contracts import PipelineStage, StageStatus
from gemeente_data_platform.pipeline_storage import create_manifest, load_manifest


def _args(**overrides: object) -> Namespace:
    values = {
        "dry_run": False,
        "start_at": "extract",
        "stop_after": None,
        "resume": None,
        "raw_run": None,
        "processed_run": None,
    }
    values.update(overrides)
    return Namespace(**values)


def _roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner.settings, "pipeline_root", tmp_path / "runs")
    monkeypatch.setattr(runner.settings, "pipeline_runtime_root", tmp_path / "runtime")
    monkeypatch.setattr(runner.settings, "pipeline_lock_timeout_seconds", 0)


def test_dry_run_has_no_external_operation_and_persists_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _roots(monkeypatch, tmp_path)
    monkeypatch.setattr(
        runner,
        "_stage_operation",
        lambda *_: pytest.fail("dry run called an external operation"),
    )
    manifest = runner.run_pipeline(_args(dry_run=True))
    assert manifest.status == "dry-run"
    assert all(
        stage.status is StageStatus.SKIPPED for stage in manifest.stages.values()
    )
    stored = load_manifest(tmp_path / "runs" / manifest.pipeline_run_id)
    assert stored.pipeline_run_id == manifest.pipeline_run_id


def test_stage_failure_is_persisted_and_resume_starts_at_failed_stage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _roots(monkeypatch, tmp_path)
    calls: list[PipelineStage] = []

    def operation(_manifest, _args, stage: PipelineStage):
        calls.append(stage)
        if stage is PipelineStage.TRANSFORM and calls.count(stage) == 1:
            raise RuntimeError("password=not-for-logs")
        return {"artifact": stage.value}

    monkeypatch.setattr(runner, "_stage_operation", operation)
    with pytest.raises(runner.PipelineExecutionError):
        runner.run_pipeline(_args(stop_after="transform"))
    run_id = next((tmp_path / "runs").iterdir()).name
    failed = load_manifest(tmp_path / "runs" / run_id)
    assert failed.stages[PipelineStage.EXTRACT].status is StageStatus.SUCCEEDED
    assert failed.stages[PipelineStage.TRANSFORM].status is StageStatus.FAILED
    assert "not-for-logs" not in failed.stages[PipelineStage.TRANSFORM].error_message

    monkeypatch.setattr(runner, "_verify_stage_artifacts", lambda *_: None)
    resumed = runner.run_pipeline(_args(resume=run_id, stop_after="transform"))
    assert resumed.stages[PipelineStage.EXTRACT].status is StageStatus.SUCCEEDED
    assert resumed.stages[PipelineStage.TRANSFORM].status is StageStatus.SUCCEEDED
    assert calls == [
        PipelineStage.EXTRACT,
        PipelineStage.TRANSFORM,
        PipelineStage.TRANSFORM,
    ]


def test_resume_rejects_changed_successful_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _roots(monkeypatch, tmp_path)
    root = tmp_path / "runs"
    manifest = create_manifest(root, run_id="resume-artifact")
    for predecessor in (
        PipelineStage.EXTRACT,
        PipelineStage.TRANSFORM,
        PipelineStage.MIGRATE,
        PipelineStage.LOAD,
    ):
        manifest.stages[predecessor].transition(StageStatus.SKIPPED)
    stage = manifest.stages[PipelineStage.VALIDATE]
    stage.transition(StageStatus.RUNNING)
    stage.outputs = {
        "validation_report": str(tmp_path / "missing.json"),
        "validation_report_checksum": "x",
    }
    stage.transition(StageStatus.SUCCEEDED)
    from gemeente_data_platform.pipeline_storage import write_manifest

    write_manifest(root / manifest.pipeline_run_id, manifest)
    with pytest.raises(runner.PipelineExecutionError, match="artifact verification"):
        runner.run_pipeline(_args(resume=manifest.pipeline_run_id))


def test_cli_returns_stage_failure_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runner,
        "run_pipeline",
        lambda _: (_ for _ in ()).throw(runner.PipelineExecutionError("failed")),
    )
    with pytest.raises(SystemExit) as result:
        runner.main(["--dry-run"])
    assert result.value.code == 4


def test_later_start_requires_explicit_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _roots(monkeypatch, tmp_path)
    with pytest.raises(runner.PipelineExecutionError, match="--raw-run"):
        runner.run_pipeline(_args(start_at="transform", stop_after="transform"))

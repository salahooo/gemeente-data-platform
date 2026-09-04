"""Veilige CLI-orkestratie voor de volledige CBS-naar-PostgreSQL-keten."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from gemeente_data_platform.cbs_client import CbsClient
from gemeente_data_platform.config import PROJECT_ROOT, settings
from gemeente_data_platform.database import create_database_engine
from gemeente_data_platform.database_loader import load_processed_run, load_snapshot
from gemeente_data_platform.database_validator import validate_database_snapshot
from gemeente_data_platform.pipeline_contracts import (
    PipelineManifest,
    PipelineStage,
    StageStatus,
)
from gemeente_data_platform.pipeline_lock import PipelineLockError, pipeline_lock
from gemeente_data_platform.pipeline_security import redact
from gemeente_data_platform.pipeline_storage import (
    create_manifest,
    load_manifest,
    log_jsonl,
    run_directory,
    write_manifest,
)
from gemeente_data_platform.population_extraction import extract_population
from gemeente_data_platform.processed_pipeline import transform_raw_run
from gemeente_data_platform.processed_storage import load_raw_run
from gemeente_data_platform.raw_storage import sha256_file, write_json_atomically


class PipelineExecutionError(RuntimeError):
    """Een fase kon niet betrouwbaar worden uitgevoerd of hervat."""


class PipelineEventLogger:
    """Schrijf één redacted event naar console én run-specifieke JSONL."""

    def __init__(self, directory: Path, run_id: str) -> None:
        self.directory = directory
        self.run_id = run_id
        self.logger = logging.getLogger("gemeente_data_platform.pipeline")
        self.logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        self.logger.addHandler(handler)
        self.logger.setLevel(settings.log_level)
        self.logger.propagate = False

    def event(self, level: int, event: str, message: str, **details: object) -> None:
        safe_message = redact(message)
        record = {
            "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": logging.getLevelName(level),
            "event": event,
            "pipeline_run_id": self.run_id,
            "message": safe_message,
            **details,
        }
        log_jsonl(self.directory, record)
        self.logger.log(level, "%s | run=%s | %s", event, self.run_id, safe_message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parseer expliciete, reproduceerbare pipelinebesturing."""
    names = [stage.value for stage in PipelineStage]
    parser = argparse.ArgumentParser(
        description="Voer de CBS data pipeline end-to-end uit."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Maak alleen een plan; geen CBS, migratie of datamutatie.",
    )
    parser.add_argument(
        "--start-at", choices=names, default=PipelineStage.EXTRACT.value
    )
    parser.add_argument("--stop-after", choices=names)
    parser.add_argument("--resume", metavar="PIPELINE_RUN_ID")
    parser.add_argument(
        "--raw-run", help="Expliciete raw run voor starten bij transform."
    )
    parser.add_argument(
        "--processed-run",
        help="Expliciete processed run voor starten bij migrate, load of validate.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Voer de pipeline uit en geef voorspelbare non-zero exitcodes terug."""
    try:
        manifest = run_pipeline(parse_args(argv))
    except PipelineLockError as exc:
        print(f"PIPELINE LOCK ERROR: {redact(str(exc))}", file=sys.stderr)
        raise SystemExit(3) from exc
    except PipelineExecutionError as exc:
        print(f"PIPELINE ERROR: {redact(str(exc))}", file=sys.stderr)
        raise SystemExit(4) from exc
    except (ValueError, OSError) as exc:
        print(f"PIPELINE CONFIGURATION ERROR: {redact(str(exc))}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"Pipeline {manifest.status} | pipeline-run-id={manifest.pipeline_run_id}")


def run_pipeline(args: argparse.Namespace) -> PipelineManifest:
    """Orkestreer fasen en persisteer elke toestandsovergang atomair."""
    start = PipelineStage(args.start_at)
    stop = PipelineStage(args.stop_after) if args.stop_after else PipelineStage.VALIDATE
    stages = list(PipelineStage)
    if stages.index(stop) < stages.index(start):
        raise ValueError("--stop-after must not precede --start-at.")
    root = _project_path(settings.pipeline_root)
    runtime_root = _project_path(settings.pipeline_runtime_root)
    root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    with pipeline_lock(
        runtime_root / "pipeline.lock", settings.pipeline_lock_timeout_seconds
    ):
        if args.resume:
            directory = run_directory(root, args.resume)
            manifest = load_manifest(directory)
            if manifest.dry_run:
                raise ValueError(
                    "A dry-run manifest cannot be resumed as a writing run."
                )
            manifest.resume_history.append(
                {"resumed_at_utc": _utc_now(), "requested_start_at": start.value}
            )
        else:
            manifest = create_manifest(root, dry_run=args.dry_run)
            directory = run_directory(root, manifest.pipeline_run_id)
        events = PipelineEventLogger(directory, manifest.pipeline_run_id)
        events.event(
            logging.INFO, "pipeline_started", "Pipeline started", dry_run=args.dry_run
        )
        try:
            if args.dry_run:
                _mark_dry_run(manifest, directory, events, start, stop)
            else:
                if args.resume:
                    _resume_successes(manifest, directory, events)
                else:
                    _prepare_initial_inputs(manifest, directory, events, args, start)
                _execute_selected(manifest, directory, events, args, start, stop)
            _set_pipeline_status(manifest, stop)
            write_manifest(directory, manifest)
            events.event(
                logging.INFO, "pipeline_finished", f"Pipeline {manifest.status}"
            )
            return manifest
        except Exception as exc:
            manifest.status = "failed"
            write_manifest(directory, manifest)
            events.event(
                logging.ERROR,
                "pipeline_failed",
                redact(str(exc)),
                error_type=type(exc).__name__,
            )
            if isinstance(exc, PipelineExecutionError):
                raise
            raise PipelineExecutionError(redact(str(exc))) from exc


def _prepare_initial_inputs(
    manifest: PipelineManifest,
    directory: Path,
    events: PipelineEventLogger,
    args: argparse.Namespace,
    start: PipelineStage,
) -> None:
    """Leg externe artifacts vast wanneer een eerdere fase wordt overgeslagen."""
    if start is PipelineStage.EXTRACT:
        return
    if start is PipelineStage.TRANSFORM:
        if not args.raw_run:
            raise ValueError("--raw-run is required when --start-at transform.")
        raw = load_raw_run(_raw_path(args.raw_run))
        _skip(
            manifest,
            directory,
            events,
            PipelineStage.EXTRACT,
            "external raw run",
            raw_directory=str(raw.directory),
            raw_manifest_checksum=sha256_file(raw.directory / "manifest.json"),
        )
        return
    if not args.processed_run:
        raise ValueError("--processed-run is required when starting after transform.")
    processed = _processed_run(args.processed_run)
    for stage in (PipelineStage.EXTRACT, PipelineStage.TRANSFORM):
        _skip(
            manifest,
            directory,
            events,
            stage,
            "external processed run",
            processed_directory=str(processed.directory),
            processed_manifest_checksum=sha256_file(
                processed.directory / "manifest.json"
            ),
        )
    for stage in PipelineStage:
        if list(PipelineStage).index(stage) >= list(PipelineStage).index(start):
            break
        _skip(manifest, directory, events, stage, "external prerequisite")


def _execute_selected(
    manifest: PipelineManifest,
    directory: Path,
    events: PipelineEventLogger,
    args: argparse.Namespace,
    start: PipelineStage,
    stop: PipelineStage,
) -> None:
    for stage in list(PipelineStage)[
        list(PipelineStage).index(start) : list(PipelineStage).index(stop) + 1
    ]:
        result = manifest.stages[stage]
        if result.status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}:
            continue
        if result.status is StageStatus.FAILED:
            result.prepare_resume()
        _run_stage(manifest, directory, events, args, stage)


def _run_stage(
    manifest: PipelineManifest,
    directory: Path,
    events: PipelineEventLogger,
    args: argparse.Namespace,
    stage: PipelineStage,
) -> None:
    result = manifest.stages[stage]
    result.transition(StageStatus.RUNNING)
    write_manifest(directory, manifest)
    events.event(
        logging.INFO, "stage_started", f"Starting {stage.value}", stage=stage.value
    )
    try:
        outputs = _stage_operation(manifest, args, stage)
    except Exception as exc:
        result.error_category = type(exc).__name__
        result.error_message = redact(str(exc))
        result.transition(StageStatus.FAILED)
        write_manifest(directory, manifest)
        events.event(
            logging.ERROR, "stage_failed", result.error_message, stage=stage.value
        )
        raise
    result.outputs = {key: str(value) for key, value in outputs.items()}
    result.transition(StageStatus.SUCCEEDED)
    write_manifest(directory, manifest)
    events.event(
        logging.INFO,
        "stage_succeeded",
        f"Finished {stage.value}",
        stage=stage.value,
        outputs=result.outputs,
    )


def _stage_operation(
    manifest: PipelineManifest, args: argparse.Namespace, stage: PipelineStage
) -> dict[str, object]:
    if stage is PipelineStage.EXTRACT:
        summary = extract_population(CbsClient.from_settings(settings), settings)
        return {
            "raw_directory": summary.output_directory,
            "raw_manifest_checksum": sha256_file(
                summary.output_directory / "manifest.json"
            ),
        }
    if stage is PipelineStage.TRANSFORM:
        raw_selector = (
            manifest.stages[PipelineStage.EXTRACT].outputs.get("raw_directory")
            or args.raw_run
        )
        if not raw_selector:
            raise PipelineExecutionError(
                "No validated raw artifact is available for transform."
            )
        summary = transform_raw_run(
            settings.cbs_dataset_code, raw_run_selector=raw_selector
        )
        return {
            "processed_directory": summary.output_directory,
            "processed_manifest_checksum": sha256_file(
                summary.output_directory / "manifest.json"
            ),
        }
    if stage is PipelineStage.MIGRATE:
        _migrate_to_head()
        return {"alembic_revision": _database_revision()}
    processed = _manifest_processed_run(manifest, args)
    if stage is PipelineStage.LOAD:
        state = load_snapshot(
            create_database_engine(),
            processed,
            pipeline_run_id=manifest.pipeline_run_id,
        )
        return {
            "processed_directory": processed.directory,
            "processed_manifest_checksum": sha256_file(
                processed.directory / "manifest.json"
            ),
            "load_result": state,
        }
    if stage is PipelineStage.VALIDATE:
        report = validate_database_snapshot(create_database_engine(), processed)
        report_path = (
            run_directory(
                _project_path(settings.pipeline_root), manifest.pipeline_run_id
            )
            / "database_validation.json"
        )
        write_json_atomically(report, report_path)
        return {
            "validation_report": report_path,
            "validation_report_checksum": sha256_file(report_path),
            "processed_directory": processed.directory,
        }
    raise AssertionError(f"Unknown pipeline stage: {stage}")


def _resume_successes(
    manifest: PipelineManifest, directory: Path, events: PipelineEventLogger
) -> None:
    """Controleer persistente artifacts vóór een geslaagde fase wordt overgeslagen."""
    for stage in PipelineStage:
        result = manifest.stages[stage]
        if result.status is StageStatus.SUCCEEDED:
            try:
                _verify_stage_artifacts(stage, result.outputs)
            except Exception as exc:
                raise PipelineExecutionError(
                    f"Cannot resume: {stage.value} artifact verification failed: {exc}"
                ) from exc
            events.event(
                logging.INFO,
                "stage_resume_skipped",
                f"Verified successful {stage.value}",
                stage=stage.value,
            )
        elif result.status is StageStatus.FAILED:
            result.prepare_resume()
            write_manifest(directory, manifest)
            return
        elif result.status is StageStatus.PENDING:
            return


def _verify_stage_artifacts(stage: PipelineStage, outputs: dict[str, str]) -> None:
    if stage is PipelineStage.EXTRACT:
        directory = Path(outputs["raw_directory"])
        load_raw_run(directory)
        expected = outputs.get("raw_manifest_checksum")
        if expected != sha256_file(directory / "manifest.json"):
            raise ValueError("raw manifest checksum changed")
    elif stage is PipelineStage.TRANSFORM:
        directory = Path(outputs["processed_directory"])
        load_processed_run(directory)
        expected = outputs.get("processed_manifest_checksum")
        if expected != sha256_file(directory / "manifest.json"):
            raise ValueError("processed manifest checksum changed")
    elif stage is PipelineStage.VALIDATE:
        report = Path(outputs["validation_report"])
        if not report.is_file() or outputs.get(
            "validation_report_checksum"
        ) != sha256_file(report):
            raise ValueError("database validation report checksum changed")


def _mark_dry_run(
    manifest: PipelineManifest,
    directory: Path,
    events: PipelineEventLogger,
    start: PipelineStage,
    stop: PipelineStage,
) -> None:
    for stage in list(PipelineStage)[
        list(PipelineStage).index(start) : list(PipelineStage).index(stop) + 1
    ]:
        _skip(
            manifest, directory, events, stage, "dry-run: no external call or mutation"
        )
    manifest.status = "dry-run"


def _skip(
    manifest: PipelineManifest,
    directory: Path,
    events: PipelineEventLogger,
    stage: PipelineStage,
    reason: str,
    **outputs: str,
) -> None:
    result = manifest.stages[stage]
    if result.status is StageStatus.PENDING:
        result.outputs = {key: str(value) for key, value in outputs.items()}
        result.inputs["reason"] = reason
        result.transition(StageStatus.SKIPPED)
        write_manifest(directory, manifest)
        events.event(logging.INFO, "stage_skipped", reason, stage=stage.value)


def _set_pipeline_status(manifest: PipelineManifest, stop: PipelineStage) -> None:
    if manifest.status == "dry-run":
        return
    required = list(PipelineStage)[: list(PipelineStage).index(stop) + 1]
    manifest.status = (
        "succeeded"
        if all(
            manifest.stages[item].status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
            for item in required
        )
        and stop is PipelineStage.VALIDATE
        else "stopped"
    )


def _manifest_processed_run(manifest: PipelineManifest, args: argparse.Namespace):
    output = manifest.stages[PipelineStage.TRANSFORM].outputs
    path = output.get("processed_directory")
    return (
        load_processed_run(Path(path)) if path else _processed_run(args.processed_run)
    )


def _raw_path(selector: str) -> Path:
    supplied = Path(selector)
    if supplied.is_absolute() or supplied.parts[:-1]:
        return supplied if supplied.is_absolute() else PROJECT_ROOT / supplied
    return PROJECT_ROOT / "data" / "raw" / "cbs" / settings.cbs_dataset_code / selector


def _processed_run(selector: str):
    from gemeente_data_platform.database_loader import select_processed_run

    return select_processed_run(settings.cbs_dataset_code, selector)


def _migrate_to_head() -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    if _database_revision() != "20260904_03":
        raise PipelineExecutionError("Alembic did not reach revision 20260904_03.")


def _database_revision() -> str | None:
    with create_database_engine().connect() as connection:
        return connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one_or_none()


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()

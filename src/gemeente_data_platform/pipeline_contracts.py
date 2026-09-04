"""Getypeerde, databasevrije contracten voor operationele pipelinefasen."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class PipelineStage(StrEnum):
    EXTRACT = "extract"
    TRANSFORM = "transform"
    MIGRATE = "migrate"
    LOAD = "load"
    VALIDATE = "validate"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    name: PipelineStage
    status: StageStatus = StageStatus.PENDING
    started_at_utc: str | None = None
    ended_at_utc: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)

    def transition(self, target: StageStatus) -> None:
        allowed = {
            StageStatus.PENDING: {StageStatus.RUNNING, StageStatus.SKIPPED},
            StageStatus.RUNNING: {StageStatus.SUCCEEDED, StageStatus.FAILED},
        }
        if target not in allowed.get(self.status, set()):
            raise ValueError(f"Invalid stage transition: {self.status} to {target}.")
        self.status = target
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if target is StageStatus.RUNNING:
            self.started_at_utc = now
        if target in {StageStatus.SUCCEEDED, StageStatus.FAILED}:
            self.ended_at_utc = now

    def prepare_resume(self) -> None:
        if self.status is not StageStatus.FAILED:
            raise ValueError("Only a failed stage can be prepared for resume.")
        self.status = StageStatus.PENDING
        self.error_category = self.error_message = None

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "StageResult":
        """Herstel een stage uit het persistente manifest."""
        return cls(
            name=PipelineStage(str(value["name"])),
            status=StageStatus(str(value.get("status", StageStatus.PENDING))),
            started_at_utc=value.get("started_at_utc")
            if isinstance(value.get("started_at_utc"), str)
            else None,
            ended_at_utc=value.get("ended_at_utc")
            if isinstance(value.get("ended_at_utc"), str)
            else None,
            error_category=value.get("error_category")
            if isinstance(value.get("error_category"), str)
            else None,
            error_message=value.get("error_message")
            if isinstance(value.get("error_message"), str)
            else None,
            inputs=dict(value.get("inputs", {})),
            outputs=dict(value.get("outputs", {})),
        )


@dataclass
class PipelineManifest:
    """Getypeerde, versieerbare staat van een end-to-end pipeline-run."""

    pipeline_run_id: str
    dry_run: bool = False
    schema_version: str = "1.0"
    status: str = "running"
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )
    updated_at_utc: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )
    stages: dict[PipelineStage, StageResult] = field(
        default_factory=lambda: {stage: StageResult(stage) for stage in PipelineStage}
    )
    warnings: list[str] = field(default_factory=list)
    resume_history: list[dict[str, str]] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at_utc = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def as_dict(self) -> dict[str, object]:
        self.touch()
        return {
            "schema_version": self.schema_version,
            "pipeline_run_id": self.pipeline_run_id,
            "status": self.status,
            "dry_run": self.dry_run,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "stages": {
                stage.value: asdict(result) for stage, result in self.stages.items()
            },
            "warnings": self.warnings,
            "resume_history": self.resume_history,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "PipelineManifest":
        stages_value = value.get("stages")
        if not isinstance(value.get("pipeline_run_id"), str) or not isinstance(
            stages_value, dict
        ):
            raise ValueError("Invalid pipeline manifest.")
        stages = {
            stage: StageResult.from_dict(
                dict(stages_value.get(stage.value, {"name": stage.value}))
            )
            for stage in PipelineStage
        }
        return cls(
            pipeline_run_id=value["pipeline_run_id"],
            schema_version=str(value.get("schema_version", "")),
            status=str(value.get("status", "running")),
            dry_run=bool(value.get("dry_run", False)),
            created_at_utc=str(value.get("created_at_utc", "")),
            updated_at_utc=str(value.get("updated_at_utc", "")),
            stages=stages,
            warnings=[
                item for item in value.get("warnings", []) if isinstance(item, str)
            ],
            resume_history=[
                item
                for item in value.get("resume_history", [])
                if isinstance(item, dict)
            ],
        )


def create_run_id(now: datetime | None = None, token: UUID | None = None) -> str:
    """Maak een UTC-gesorteerde, bestandssysteemveilige pipeline-id."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    return f"{current.strftime('%Y%m%dT%H%M%S%fZ')}-{(token or uuid4()).hex[:8]}"

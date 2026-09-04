"""Atomische opslag van pipeline-manifesten en JSONL-logregels."""

from __future__ import annotations

import json
from pathlib import Path

from gemeente_data_platform.pipeline_contracts import PipelineManifest, create_run_id
from gemeente_data_platform.pipeline_security import redact
from gemeente_data_platform.raw_storage import write_json_atomically


def run_directory(root: Path, run_id: str) -> Path:
    """Geef een veilige runmap terug zonder path traversal."""
    if not run_id or Path(run_id).name != run_id or ".." in run_id:
        raise ValueError("Invalid pipeline run-id.")
    return root / run_id


def create_manifest(
    root: Path, run_id: str | None = None, dry_run: bool = False
) -> PipelineManifest:
    """Maak en schrijf een minimaal operationeel manifest atomair."""
    identifier = run_id or create_run_id()
    directory = run_directory(root, identifier)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = PipelineManifest(pipeline_run_id=identifier, dry_run=dry_run)
    write_manifest(directory, manifest)
    return manifest


def write_manifest(directory: Path, manifest: PipelineManifest | dict) -> None:
    """Redigeer en schrijf UTF-8 JSON atomair."""
    value = manifest.as_dict() if isinstance(manifest, PipelineManifest) else manifest
    write_json_atomically(_redact_object(value), directory / "pipeline_manifest.json")


def load_manifest(directory: Path) -> PipelineManifest:
    """Laad een bestaand JSON-object."""
    result = json.loads(
        (directory / "pipeline_manifest.json").read_text(encoding="utf-8")
    )
    if not isinstance(result, dict):
        raise ValueError("Invalid pipeline manifest.")
    return PipelineManifest.from_dict(result)


def log_jsonl(directory: Path, record: dict) -> None:
    """Append één geredigeerde JSONL-record."""
    with (directory / "pipeline.log.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_redact_object(record), ensure_ascii=False) + "\n")


def _redact_object(value):
    if isinstance(value, dict):
        return {key: _redact_object(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    return redact(value) if isinstance(value, str) else value

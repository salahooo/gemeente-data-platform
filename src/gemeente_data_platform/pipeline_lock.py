"""Cross-platform exclusieve schrijflock met filelock."""

from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout


class PipelineLockError(RuntimeError):
    """Een andere schrijvende pipeline bezit de projectlock."""


@contextmanager
def pipeline_lock(path: Path, timeout: float):
    """Verkrijg en geef altijd een OS-ondersteunde projectlock vrij."""
    lock = FileLock(str(path))
    try:
        with lock.acquire(timeout=timeout):
            yield
    except Timeout as exc:
        raise PipelineLockError("Pipeline lock is already held.") from exc

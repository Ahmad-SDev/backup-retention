import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

# Matches the common stamp styles: 2026-11-23_04-00-00, 2026-11-23T04:00:00, 20261123-040000, 20261123
TIMESTAMP_IN_NAME = re.compile(
    r"(?P<year>20\d{2})-?(?P<month>[01]\d)-?(?P<day>[0-3]\d)"
    r"(?:[T_\- ]?(?P<hour>[0-2]\d)[:\-]?(?P<minute>[0-5]\d)(?:[:\-]?(?P<second>[0-5]\d))?)?"
)


@dataclass(frozen=True)
class Backup:
    name: str
    created_at: datetime
    size_bytes: int = 0


class BackupStore(Protocol):
    def list_backups(self) -> list[Backup]: ...

    def delete(self, backup: Backup) -> None: ...


def timestamp_from_name(name: str) -> datetime | None:
    match = TIMESTAMP_IN_NAME.search(name)
    if match is None:
        return None
    parts = {key: int(value) for key, value in match.groupdict().items() if value is not None}
    try:
        return datetime(**parts)
    except ValueError:
        return None


class LocalDirectoryStore:
    """Backups are files (or directories) in one folder. The time comes from the name, else from mtime."""

    def __init__(self, directory: Path, pattern: str = "*") -> None:
        self._directory = directory
        self._pattern = pattern

    def list_backups(self) -> list[Backup]:
        return [self._to_backup(path) for path in sorted(self._directory.glob(self._pattern))]

    def delete(self, backup: Backup) -> None:
        path = self._directory / backup.name
        if path.is_dir():
            raise IsADirectoryError(f"{path} is a directory, refusing to delete it recursively")
        path.unlink()

    @staticmethod
    def _to_backup(path: Path) -> Backup:
        stat = path.stat()
        created_at = timestamp_from_name(path.name) or datetime.fromtimestamp(stat.st_mtime)
        return Backup(name=path.name, created_at=created_at, size_bytes=stat.st_size)

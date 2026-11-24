import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

# Matches the common stamp styles: 2026-11-23_04-00-00, 2026-11-23T04:00:00, 20261123-040000, 20261123,
# and Proxmox vzdump's 2026_11_23-04_00_12
TIMESTAMP_IN_NAME = re.compile(
    r"(?P<year>20\d{2})[-_]?(?P<month>[01]\d)[-_]?(?P<day>[0-3]\d)"
    r"(?:[T_\- ]?(?P<hour>[0-2]\d)[:\-_]?(?P<minute>[0-5]\d)(?:[:\-_]?(?P<second>[0-5]\d))?)?"
)

# Files that belong to a backup rather than being one: vzdump writes NAME.log and NAME.vma.zst.notes
# next to every NAME.vma.zst archive.
SIDECAR_SUFFIXES = (".log", ".notes")


@dataclass(frozen=True)
class Backup:
    name: str
    created_at: datetime
    size_bytes: int = 0
    sidecars: tuple[str, ...] = ()


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
        paths = sorted(self._directory.glob(self._pattern))
        sidecars = _find_sidecars(paths)
        owned = {sidecar.name for group in sidecars.values() for sidecar in group}
        return [self._to_backup(path, sidecars.get(path.name, [])) for path in paths if path.name not in owned]

    def delete(self, backup: Backup) -> None:
        path = self._directory / backup.name
        if path.is_dir():
            raise IsADirectoryError(f"{path} is a directory, refusing to delete it recursively")
        path.unlink()
        for name in backup.sidecars:
            (self._directory / name).unlink(missing_ok=True)

    @staticmethod
    def _to_backup(path: Path, sidecars: list[Path]) -> Backup:
        stat = path.stat()
        created_at = timestamp_from_name(path.name) or datetime.fromtimestamp(stat.st_mtime)
        size = stat.st_size + sum(sidecar.stat().st_size for sidecar in sidecars)
        return Backup(path.name, created_at, size, tuple(sidecar.name for sidecar in sidecars))


def _find_sidecars(paths: list[Path]) -> dict[str, list[Path]]:
    """Maps a backup name to the .log/.notes files written next to it.

    vzdump-qemu-105-2026_11_23-04_00_12.vma.zst owns vzdump-qemu-105-2026_11_23-04_00_12.log
    and vzdump-qemu-105-2026_11_23-04_00_12.vma.zst.notes.
    """
    sidecars_by_stem: dict[str, list[Path]] = {}
    for path in paths:
        if path.is_file() and path.name.endswith(SIDECAR_SUFFIXES):
            sidecars_by_stem.setdefault(path.name.rsplit(".", 1)[0], []).append(path)

    found: dict[str, list[Path]] = {}
    for path in paths:
        if path.name.endswith(SIDECAR_SUFFIXES):
            continue
        group = sidecars_by_stem.get(path.name, []) + sidecars_by_stem.get(path.name.split(".", 1)[0], [])
        if group:
            found[path.name] = group
    return found

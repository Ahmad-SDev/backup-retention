import os
from datetime import datetime

import pytest

from backup_retention.backup import LocalDirectoryStore, timestamp_from_name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("db-2026-11-23_04-00-00.sql.zst", datetime(2026, 11, 23, 4, 0, 0)),
        ("site-2026-11-23T04:30.tar.gz", datetime(2026, 11, 23, 4, 30)),
        ("vzdump-qemu-105-20261123-040012.vma.zst", datetime(2026, 11, 23, 4, 0, 12)),
        ("backup_20261123.tar", datetime(2026, 11, 23)),
    ],
)
def test_reads_common_timestamp_styles(name, expected):
    assert timestamp_from_name(name) == expected


@pytest.mark.parametrize("name", ["latest.tar", "db-2026-13-45.sql"])
def test_returns_none_without_a_valid_timestamp(name):
    assert timestamp_from_name(name) is None


def test_store_falls_back_to_mtime(tmp_path):
    undated = tmp_path / "latest.tar"
    undated.write_bytes(b"x" * 10)
    stamp = datetime(2026, 1, 2, 3, 4, 5).timestamp()
    os.utime(undated, (stamp, stamp))

    (backup,) = LocalDirectoryStore(tmp_path).list_backups()

    assert backup.created_at == datetime(2026, 1, 2, 3, 4, 5)
    assert backup.size_bytes == 10


def test_store_filters_by_pattern_and_deletes(tmp_path):
    (tmp_path / "db-20261122.sql").write_text("old")
    (tmp_path / "db-20261123.sql").write_text("new")
    (tmp_path / "notes.txt").write_text("not a backup")
    store = LocalDirectoryStore(tmp_path, "db-*.sql")

    backups = store.list_backups()
    store.delete(backups[0])

    assert [backup.name for backup in backups] == ["db-20261122.sql", "db-20261123.sql"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["db-20261123.sql", "notes.txt"]


def test_store_refuses_to_delete_directories(tmp_path):
    (tmp_path / "snapshot-20261123").mkdir()
    store = LocalDirectoryStore(tmp_path)

    with pytest.raises(IsADirectoryError):
        store.delete(store.list_backups()[0])


def test_reads_proxmox_vzdump_timestamps():
    name = "vzdump-qemu-105-2026_11_23-04_00_12.vma.zst"
    assert timestamp_from_name(name) == datetime(2026, 11, 23, 4, 0, 12)


def test_vzdump_log_and_notes_travel_with_their_archive(tmp_path):
    for day in ("22", "23"):
        stem = f"vzdump-qemu-105-2026_11_{day}-04_00_12"
        (tmp_path / f"{stem}.vma.zst").write_bytes(b"x" * 100)
        (tmp_path / f"{stem}.log").write_bytes(b"x" * 10)
        (tmp_path / f"{stem}.vma.zst.notes").write_bytes(b"x")
    store = LocalDirectoryStore(tmp_path, "vzdump-qemu-105-*")

    backups = store.list_backups()
    assert [backup.name for backup in backups] == [
        "vzdump-qemu-105-2026_11_22-04_00_12.vma.zst",
        "vzdump-qemu-105-2026_11_23-04_00_12.vma.zst",
    ]
    assert backups[0].size_bytes == 111

    store.delete(backups[0])
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "vzdump-qemu-105-2026_11_23-04_00_12.log",
        "vzdump-qemu-105-2026_11_23-04_00_12.vma.zst",
        "vzdump-qemu-105-2026_11_23-04_00_12.vma.zst.notes",
    ]

from datetime import date, timedelta

from backup_retention.cli import main


def make_nightlies(directory, days):
    for age in range(days):
        (directory / f"db-{(date(2026, 11, 23) - timedelta(days=age)):%Y%m%d}.sql").write_text("dump")


def test_dry_run_deletes_nothing(tmp_path, capsys):
    make_nightlies(tmp_path, 10)

    assert main([str(tmp_path), "--keep-daily", "3"]) == 0

    assert len(list(tmp_path.iterdir())) == 10
    output = capsys.readouterr().out
    assert "3 kept, 7 to delete" in output
    assert "dry run" in output


def test_apply_deletes_the_planned_backups(tmp_path):
    make_nightlies(tmp_path, 10)

    assert main([str(tmp_path), "--keep-daily", "3", "--apply"]) == 0

    assert sorted(path.name for path in tmp_path.iterdir()) == ["db-20261121.sql", "db-20261122.sql", "db-20261123.sql"]


def test_policy_that_keeps_nothing_is_refused(tmp_path, capsys):
    make_nightlies(tmp_path, 3)

    assert main([str(tmp_path), "--apply"]) == 2

    assert len(list(tmp_path.iterdir())) == 3
    assert "keeps nothing" in capsys.readouterr().err

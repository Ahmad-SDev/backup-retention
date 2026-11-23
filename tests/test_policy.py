from datetime import datetime, timedelta

import pytest

from backup_retention.backup import Backup
from backup_retention.policy import RetentionPolicy, plan_retention

NEWEST = datetime(2026, 11, 23, 4, 0)


def nightly_backups(days: int) -> list[Backup]:
    return [
        Backup(name=f"db-{(NEWEST - timedelta(days=age)):%Y-%m-%d}.sql.zst", created_at=NEWEST - timedelta(days=age))
        for age in range(days)
    ]


def kept_names(plan) -> set[str]:
    return {backup.name for backup in plan.keep}


def test_keep_last_keeps_newest_n():
    plan = plan_retention(nightly_backups(10), RetentionPolicy(keep_last=3))

    assert kept_names(plan) == {"db-2026-11-23.sql.zst", "db-2026-11-22.sql.zst", "db-2026-11-21.sql.zst"}
    assert len(plan.delete) == 7


def test_daily_weekly_monthly_over_a_year_of_nightlies():
    plan = plan_retention(nightly_backups(365), RetentionPolicy(daily=7, weekly=4, monthly=6))

    # 2026-11-23 is a Monday, so the 7 dailies already cover ISO weeks 48 and 47.
    # Weekly adds weeks 46 and 45, monthly adds the last day of Oct, Sep, Aug, Jul and Jun.
    assert len(plan.keep) == 7 + 2 + 5
    assert len(plan.keep) + len(plan.delete) == 365


def test_each_period_keeps_its_newest_backup():
    plan = plan_retention(nightly_backups(90), RetentionPolicy(monthly=3))

    assert kept_names(plan) == {"db-2026-11-23.sql.zst", "db-2026-10-31.sql.zst", "db-2026-09-30.sql.zst"}


def test_reasons_explain_why_a_backup_is_kept():
    plan = plan_retention(nightly_backups(1), RetentionPolicy(keep_last=1, daily=1, monthly=1))

    (reasons,) = plan.keep.values()
    assert reasons == ["last", "daily 2026-11-23", "monthly 2026-11"]


def test_several_backups_on_one_day_count_as_one_daily():
    same_day = [Backup(f"b{hour}", NEWEST.replace(hour=hour)) for hour in range(6)]

    plan = plan_retention(same_day, RetentionPolicy(daily=1))

    assert kept_names(plan) == {"b5"}


def test_newest_backup_is_always_kept_by_any_rule():
    for policy in (RetentionPolicy(yearly=1), RetentionPolicy(weekly=1), RetentionPolicy(keep_last=1)):
        assert "db-2026-11-23.sql.zst" in kept_names(plan_retention(nightly_backups(30), policy))


@pytest.mark.parametrize("kwargs", [{}, {"daily": -1}])
def test_unsafe_policies_are_rejected(kwargs):
    with pytest.raises(ValueError):
        RetentionPolicy(**kwargs)

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from .backup import Backup

PeriodKey = Callable[[datetime], str]

PERIODS: dict[str, PeriodKey] = {
    "hourly": lambda moment: moment.strftime("%Y-%m-%d %H:00"),
    "daily": lambda moment: moment.strftime("%Y-%m-%d"),
    "weekly": lambda moment: "{0}-W{1:02d}".format(*moment.isocalendar()),
    "monthly": lambda moment: moment.strftime("%Y-%m"),
    "yearly": lambda moment: moment.strftime("%Y"),
}


@dataclass(frozen=True)
class RetentionPolicy:
    """Same rules as borg/restic prune: for each period keep the newest backup of the last N periods."""

    keep_last: int = 0
    hourly: int = 0
    daily: int = 0
    weekly: int = 0
    monthly: int = 0
    yearly: int = 0

    def __post_init__(self) -> None:
        if any(count < 0 for count in self._counts().values()):
            raise ValueError("retention counts cannot be negative")
        if not any(self._counts().values()):
            raise ValueError("this policy keeps nothing, set at least one keep rule")

    def period_counts(self) -> dict[str, int]:
        return {name: count for name, count in self._counts().items() if name in PERIODS and count > 0}

    def _counts(self) -> dict[str, int]:
        return {
            "last": self.keep_last,
            "hourly": self.hourly,
            "daily": self.daily,
            "weekly": self.weekly,
            "monthly": self.monthly,
            "yearly": self.yearly,
        }


@dataclass
class RetentionPlan:
    keep: dict[Backup, list[str]] = field(default_factory=dict)
    delete: list[Backup] = field(default_factory=list)


def plan_retention(backups: Sequence[Backup], policy: RetentionPolicy) -> RetentionPlan:
    newest_first = sorted(backups, key=lambda backup: backup.created_at, reverse=True)
    plan = RetentionPlan()

    def keep(backup: Backup, reason: str) -> None:
        plan.keep.setdefault(backup, []).append(reason)

    for backup in newest_first[: policy.keep_last]:
        keep(backup, "last")

    for period, count in policy.period_counts().items():
        period_key = PERIODS[period]
        seen_periods: set[str] = set()
        for backup in newest_first:
            key = period_key(backup.created_at)
            if key in seen_periods:
                continue
            seen_periods.add(key)
            keep(backup, f"{period} {key}")
            if len(seen_periods) == count:
                break

    plan.delete = [backup for backup in newest_first if backup not in plan.keep]
    return plan

import argparse
import sys
from pathlib import Path

from .backup import BackupStore, LocalDirectoryStore
from .policy import RetentionPlan, RetentionPolicy, plan_retention


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="backup-prune",
        description="Delete old backups with a grandfather-father-son policy. Shows the plan unless --apply is given.",
    )
    parser.add_argument("directory", type=Path)
    parser.add_argument("--pattern", default="*", help="glob for backup files, e.g. 'db-*.sql.zst' (default: *)")
    for period in ("last", "hourly", "daily", "weekly", "monthly", "yearly"):
        parser.add_argument(f"--keep-{period}", type=int, default=0, metavar="N")
    parser.add_argument("--apply", action="store_true", help="actually delete; without it nothing is removed")
    return parser.parse_args(argv)


def build_policy(args: argparse.Namespace) -> RetentionPolicy:
    return RetentionPolicy(
        keep_last=args.keep_last,
        hourly=args.keep_hourly,
        daily=args.keep_daily,
        weekly=args.keep_weekly,
        monthly=args.keep_monthly,
        yearly=args.keep_yearly,
    )


def print_plan(plan: RetentionPlan) -> None:
    for backup, reasons in sorted(plan.keep.items(), key=lambda item: item[0].created_at, reverse=True):
        print(f"keep    {backup.name}  ({', '.join(reasons)})")
    for backup in plan.delete:
        print(f"delete  {backup.name}")

    freed_mb = sum(backup.size_bytes for backup in plan.delete) / 1_000_000
    print(f"\n{len(plan.keep)} kept, {len(plan.delete)} to delete, {freed_mb:,.1f} MB freed")


def apply_plan(store: BackupStore, plan: RetentionPlan) -> int:
    failures = 0
    for backup in plan.delete:
        try:
            store.delete(backup)
        except OSError as error:
            failures += 1
            print(f"could not delete {backup.name}: {error}", file=sys.stderr)
    return failures


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if not args.directory.is_dir():
        print(f"not a directory: {args.directory}", file=sys.stderr)
        return 2
    try:
        policy = build_policy(args)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    store = LocalDirectoryStore(args.directory, args.pattern)
    backups = store.list_backups()
    if not backups:
        print(f"no backups matching '{args.pattern}' in {args.directory}")
        return 0

    plan = plan_retention(backups, policy)
    print_plan(plan)

    if not args.apply:
        print("dry run, re-run with --apply to delete")
        return 0
    return 1 if apply_plan(store, plan) else 0

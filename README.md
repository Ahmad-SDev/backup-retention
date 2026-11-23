# backup-retention

Prunes a folder of backups with a grandfather-father-son policy: keep the last few, one per day for a week, one per week for a month, one per month for a year, and delete the rest.

The rules work like `borg prune` / `restic forget`, so if you already know those flags this does what you expect. It's meant for the backups those tools don't manage: `mysqldump` files, `vzdump` archives, tarballs of web roots, game server world saves.

- **Dry run by default.** It prints what it would keep and why, and only deletes with `--apply`.
- Refuses a policy that would keep nothing.
- Never deletes directories.
- Reads the time from the file name (`2026-11-23_04-00-00`, `20261123-040012`, `2026-11-23T04:30`...), and falls back to the modification time.

Python 3.11+, standard library only.

## Usage

```bash
pip install git+https://github.com/Ahmad-SDev/backup-retention

backup-prune /var/lib/vz/dump --pattern 'vzdump-qemu-105-*' \
  --keep-daily 3 --keep-weekly 2 --keep-monthly 2
```

```
keep    vzdump-qemu-105-20261123-040012.vma.zst  (daily 2026-11-23, weekly 2026-W48, monthly 2026-11)
keep    vzdump-qemu-105-20261122-040012.vma.zst  (daily 2026-11-22, weekly 2026-W47)
keep    vzdump-qemu-105-20261121-040012.vma.zst  (daily 2026-11-21)
keep    vzdump-qemu-105-20261031-040012.vma.zst  (monthly 2026-10)
delete  vzdump-qemu-105-20261120-040012.vma.zst
...
4 kept, 37 to delete, 0.0 MB freed
dry run, re-run with --apply to delete
```

Typical cron entry after the nightly dump:

```cron
30 4 * * * backup-prune /backups/mysql --pattern 'db-*.sql.zst' --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --apply
```

## As a library

The planning is separate from the storage, so the same policy can drive an S3 bucket or a remote host. Implement `list_backups()` and `delete()` and pass your store's backups to `plan_retention`:

```python
from backup_retention import RetentionPolicy, plan_retention

plan = plan_retention(store.list_backups(), RetentionPolicy(daily=7, weekly=4, monthly=12))
for backup in plan.delete:
    store.delete(backup)
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT

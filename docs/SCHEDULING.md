# Scheduling expiry (no daemon, on purpose)

`amg expire` is an explicit, idempotent command. This project deliberately ships
**no long-lived scheduler process**, for three reasons:

1. A daemon inside the library would need its own failure model (restarts,
   overlapping runs, partial writes) — the file store already has an atomic
   write and an advisory lock, and cron inherits both for free.
2. Expiry is a decision with consequences. Keeping it as a command means it can
   be dry-run, logged, and replayed by hand.
3. An unknown validity window can never be auto-expired. A background process
   invites "just expire everything" defaults; a command does not.

## Safety properties you can rely on

- `amg expire` without `--apply` writes nothing (dry-run is the default).
- `--apply` only touches nodes where the validity window is **known**, the
  `valid_until` has passed, and the node is not already superseded.
- The action is `status: superseded` + `superseded_at` + one `op=expire` change
  record. Nodes are never deleted.
- Running it twice is safe: the second run reports `applied 0`.
- Nodes whose validity time is unknown (everything produced by `amg adopt`) are
  skipped and counted.

## cron

```cron
# every day at 03:17: dry-run first, then apply, append to a log
17 3 * * *  cd /srv/memory && amg expire ./mem > /var/log/amg-expire.log 2>&1 && amg expire ./mem --apply >> /var/log/amg-expire.log 2>&1
```

## systemd timer

```ini
# /etc/systemd/system/amg-expire.service
[Service]
Type=oneshot
WorkingDirectory=/srv/memory
ExecStart=/usr/local/bin/amg expire ./mem --apply
```

```ini
# /etc/systemd/system/amg-expire.timer
[Timer]
OnCalendar=*-*-* 03:17:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Rollback

Expiry does not delete anything, so rollback is a normal write: re-open the node
with `amg status <id> done --note "expiry reversed: <reason>"` (a status change
requires a note by design), and correct the validity window if it was wrong.
The original node and its `op=expire` change record remain in the graph either
way, so the reversal is itself auditable.

## What would have to change to justify a daemon

- Multiple writers per graph, where a cron run could overlap a human write. The
  advisory lock serialises them, but a daemon could batch and back off.
- Graphs large enough that a full load per run is expensive.
- A need for sub-minute expiry precision.

None of these holds at the sizes measured in `docs/BENCHMARKS.md` (10k nodes,
read paths under 100 ms).

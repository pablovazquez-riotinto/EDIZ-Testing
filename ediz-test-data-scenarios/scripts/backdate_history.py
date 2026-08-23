#!/usr/bin/env python3
"""
backdate_history.py
-------------------
Create or rewrite historical commit data backdated to specific dates.

This script supports two primary workflows:

1. **Seed historical data** – Create a sequence of commits whose author/committer
   dates are set to specific past dates, giving the repository a realistic timeline
   for EDIZ snapshot or watermark tests.

2. **Rewrite existing commit timestamps** – Use `git filter-branch` or the safer
   `git-filter-repo` (if installed) to shift all commits in the current branch by
   a given offset, useful when you want to simulate a scenario that starts at an
   exact historical moment.

Usage:
    # Seed 20 commits spread over 2025-11 (one per working day):
    python backdate_history.py seed --start 2025-11-01 --end 2025-11-30 --count 20

    # Seed commits at explicit timestamps from a JSON file:
    python backdate_history.py seed --timestamps-file timestamps.json

    # Shift all commits on the current branch back by 90 days:
    python backdate_history.py shift --days -90

    # Print the resulting commit log without making changes:
    python backdate_history.py seed --start 2025-12-01 --end 2025-12-31 --count 10 --dry-run
"""

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HISTORICAL_MESSAGES = [
    "chore: initial data scaffold",
    "feat: add base activity log schema",
    "feat: add event timestamp fields",
    "docs: add historical data README",
    "chore: add .gitignore for generated files",
    "feat: seed January 2025 activity records",
    "feat: seed February 2025 activity records",
    "fix: correct ISO-8601 format in timestamps",
    "refactor: normalize record IDs",
    "chore: add data validation helpers",
    "feat: add metadata envelope to data files",
    "docs: document data schema v1",
    "test: add schema validation tests",
    "feat: add pagination boundary records",
    "chore: bump schema version to 1.1",
]

ACTORS = ["dev-user-1", "dev-user-2", "dev-user-3"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {value!r}")


def _run(cmd: list[str], env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, capture_output=True, text=True, env=merged_env)
    if check and result.returncode != 0:
        print(f"ERROR running {' '.join(cmd)}\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def _generate_working_day_timestamps(start: datetime, end: datetime, count: int) -> list[datetime]:
    """Return *count* timestamps on working days (Mon–Fri) between *start* and *end*."""
    working_days: list[datetime] = []
    cursor = start.replace(hour=0, minute=0, second=0)
    while cursor <= end:
        if cursor.weekday() < 5:   # 0=Mon … 4=Fri
            working_days.append(cursor)
        cursor += timedelta(days=1)

    if not working_days:
        raise ValueError("No working days in the given range")

    if count > len(working_days):
        print(
            f"WARNING: only {len(working_days)} working days available; "
            f"using {len(working_days)} commits instead of {count}",
            file=sys.stderr,
        )
        count = len(working_days)

    chosen = sorted(random.sample(working_days, count))
    return [
        day + timedelta(hours=random.randint(8, 17), minutes=random.randint(0, 59))
        for day in chosen
    ]


def _write_data_file(repo_path: Path, index: int, timestamp: datetime) -> Path:
    data_dir = repo_path / "data" / "historical"
    data_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "index": index,
        "timestamp": timestamp.isoformat(),
        "type": "historical_seed",
        "actor": random.choice(ACTORS),
        "value": round(random.uniform(0, 500), 2),
    }
    file_path = data_dir / f"record_{index:04d}.json"
    file_path.write_text(json.dumps(record, indent=2))
    return file_path


def create_backdated_commit(
    repo_path: Path,
    timestamp: datetime,
    message: str,
    actor: str,
    index: int,
) -> str:
    """Create a single git commit with the specified backdated timestamp."""
    data_file = _write_data_file(repo_path, index, timestamp)

    _run(["git", "-C", str(repo_path), "add", str(data_file)])

    iso_ts = timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    commit_env = {
        "GIT_AUTHOR_NAME": actor,
        "GIT_AUTHOR_EMAIL": f"{actor}@ediz-test.local",
        "GIT_AUTHOR_DATE": iso_ts,
        "GIT_COMMITTER_NAME": actor,
        "GIT_COMMITTER_EMAIL": f"{actor}@ediz-test.local",
        "GIT_COMMITTER_DATE": iso_ts,
    }
    _run(
        ["git", "-C", str(repo_path), "commit", "-m", message],
        env=commit_env,
    )
    sha = _run(["git", "-C", str(repo_path), "rev-parse", "HEAD"]).stdout.strip()
    return sha


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_seed(args: argparse.Namespace) -> None:
    """Seed historical commits from explicit timestamps or a date range."""
    repo_path = Path(args.repo).resolve()

    # ------------------------------------------------------------------
    # Determine timestamps
    # ------------------------------------------------------------------
    if args.timestamps_file:
        raw = json.loads(Path(args.timestamps_file).read_text())
        if isinstance(raw, list):
            timestamps = [_parse_dt(t) for t in raw]
        else:
            timestamps = [_parse_dt(t) for t in raw.get("timestamps", [])]
    else:
        start = _parse_dt(args.start)
        end   = _parse_dt(args.end)
        timestamps = _generate_working_day_timestamps(start, end, args.count)

    print(f"Seeding {len(timestamps)} historical commits into {repo_path}")

    log_entries: list[dict] = []
    for idx, ts in enumerate(timestamps):
        actor   = random.choice(ACTORS)
        message = HISTORICAL_MESSAGES[idx % len(HISTORICAL_MESSAGES)]

        if args.dry_run:
            print(f"  [{idx+1:3d}] {ts.isoformat()}  {actor}  {message!r}")
            log_entries.append({"index": idx, "timestamp": ts.isoformat(), "actor": actor, "message": message})
            continue

        sha = create_backdated_commit(repo_path, ts, message, actor, idx)
        print(f"  [{idx+1:3d}] {sha[:8]}  {ts.isoformat()}  {message!r}")
        log_entries.append({"sha": sha, "index": idx, "timestamp": ts.isoformat(), "actor": actor, "message": message})

    # Write commit log summary
    log_file = repo_path / "data" / "historical" / "commit_log.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(json.dumps({"commits": log_entries}, indent=2))

    if not args.dry_run:
        _run(["git", "-C", str(repo_path), "add", str(log_file)])
        last_ts = timestamps[-1] if timestamps else datetime.now(tz=timezone.utc)
        iso_ts  = last_ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        commit_env = {
            "GIT_AUTHOR_DATE": iso_ts,
            "GIT_COMMITTER_DATE": iso_ts,
        }
        _run(
            ["git", "-C", str(repo_path), "commit", "-m", "chore: add historical commit log"],
            env=commit_env,
        )
        print(f"\nDone. {len(log_entries)} commits created with backdated timestamps.")
    else:
        print(f"\n[dry-run] Would create {len(log_entries)} backdated commits.")


def cmd_shift(args: argparse.Namespace) -> None:
    """
    Shift all commits on the current branch by *days* days.

    Uses `git filter-branch` (always available). For large repos consider
    installing `git-filter-repo` (pip install git-filter-repo) which is faster.
    """
    repo_path = Path(args.repo).resolve()
    offset = timedelta(days=args.days)
    direction = "forward" if args.days >= 0 else "backward"
    print(f"Shifting all commits {abs(args.days)} days {direction} in {repo_path}")

    if args.dry_run:
        log = _run(["git", "-C", str(repo_path), "log", "--oneline", "-10"])
        print("[dry-run] Current HEAD commits:")
        for line in log.stdout.splitlines():
            print(f"  {line}")
        print(f"\n[dry-run] Would shift by {args.days} days.")
        return

    # Build the env-filter script
    shift_seconds = int(offset.total_seconds())
    env_filter = f"""
import sys, os, datetime

for var in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
    raw = os.environ.get(var, "")
    if not raw:
        continue
    # Handle RFC-2822 and ISO-8601 dates
    try:
        ts = int(raw.split()[0]) if raw.strip()[0].isdigit() else None
        if ts is not None:
            os.environ[var] = str(ts + {shift_seconds}) + " +0000"
            continue
    except Exception:
        pass
    # Fall back: leave unchanged
    pass
"""

    # Write the env-filter to a temp file so it can be executed
    filter_path = repo_path / ".git" / "_ediz_shift_filter.py"
    filter_path.write_text(env_filter)

    try:
        _run([
            "git", "-C", str(repo_path),
            "filter-branch", "--force",
            "--env-filter", f"python3 '{filter_path}'",
            "HEAD",
        ])
        print("Done. Timestamps shifted.")
        print("NOTE: You may need to force-push if this branch has already been pushed.")
    finally:
        filter_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create or backdate git history for EDIZ tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--repo", default=".", help="Path to git repository (default: current dir)")
    sub = p.add_subparsers(dest="command", required=True)

    # ---- seed ----
    seed_p = sub.add_parser("seed", help="Seed historical commits at backdated timestamps")
    seed_p.add_argument("--start", default="2025-11-01", help="Start date (ISO-8601)")
    seed_p.add_argument("--end",   default="2025-11-30", help="End date (ISO-8601)")
    seed_p.add_argument("--count", type=int, default=20, help="Number of commits")
    seed_p.add_argument("--timestamps-file", metavar="FILE", help="JSON file with explicit timestamps")
    seed_p.add_argument("--dry-run", action="store_true")

    # ---- shift ----
    shift_p = sub.add_parser("shift", help="Shift all commits by N days")
    shift_p.add_argument("--days", type=int, required=True, help="Days to shift (negative = back in time)")
    shift_p.add_argument("--dry-run", action="store_true")

    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "seed":
        cmd_seed(args)
    elif args.command == "shift":
        cmd_shift(args)
    else:
        build_parser().print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
generate_commits.py
-------------------
Programmatically generate bulk commits with configurable:
  - Number of commits
  - Time distribution (hourly, daily, weekly patterns)
  - Commit message patterns (for EDIZ filtering tests)
  - Data payloads (to simulate different data volumes)

Usage:
    python generate_commits.py --count 50 --distribution daily --start 2026-01-01 --end 2026-01-31
    python generate_commits.py --count 10 --distribution hourly --start 2026-02-01T08:00:00 --pattern feat
    python generate_commits.py --preset snapshot   # Use predefined snapshot scenario
    python generate_commits.py --preset watermark  # Use predefined watermark scenario
    python generate_commits.py --preset pagination # Use predefined pagination scenario
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

COMMIT_MESSAGE_PATTERNS = {
    "feat":     ["feat: add {noun} support", "feat({scope}): implement {noun}", "feat: {verb} {noun} for testing"],
    "fix":      ["fix: resolve {noun} issue", "fix({scope}): correct {noun} handling", "fix: patch {noun} edge case"],
    "chore":    ["chore: update {noun}", "chore({scope}): bump {noun} version", "chore: cleanup {noun}"],
    "docs":     ["docs: update {noun} docs", "docs({scope}): add {noun} examples", "docs: clarify {noun} usage"],
    "test":     ["test: add {noun} test cases", "test({scope}): cover {noun} scenario", "test: validate {noun} behavior"],
    "refactor": ["refactor: simplify {noun}", "refactor({scope}): extract {noun} helper", "refactor: normalize {noun}"],
}

NOUNS = ["pagination", "cursor", "watermark", "snapshot", "date_slice", "filter", "schema", "fixture", "record", "event"]
VERBS = ["add", "update", "improve", "extend", "validate", "configure", "generate"]
SCOPES = ["pagination", "cursor", "watermark", "snapshot", "date_slice", "filtering", "core", "utils"]
ACTORS = ["dev-user-1", "dev-user-2", "dev-user-3"]

DATA_VOLUME_PRESETS = {
    "tiny":   {"records": 5,   "size_bytes": 512},
    "small":  {"records": 50,  "size_bytes": 5120},
    "medium": {"records": 200, "size_bytes": 20480},
    "large":  {"records": 500, "size_bytes": 51200},
}

SCENARIO_PRESETS = {
    "snapshot": {
        "count": 40,
        "distribution": "daily",
        "start": "2026-01-01T00:00:00",
        "end":   "2026-01-31T23:59:59",
        "patterns": ["feat", "fix", "chore", "docs", "test"],
        "volume": "small",
        "description": "SNAPSHOT: full load from fixed start date",
    },
    "watermark": {
        "count": 30,
        "distribution": "daily",
        "start": "2026-02-01T00:00:00",
        "end":   "2026-02-28T23:59:59",
        "patterns": ["feat", "fix"],
        "volume": "tiny",
        "description": "HIGH_WATERMARK: incremental window ingestion",
    },
    "pagination": {
        "count": 150,
        "distribution": "hourly",
        "start": "2026-01-01T08:00:00",
        "end":   "2026-01-07T18:00:00",
        "patterns": ["feat", "chore"],
        "volume": "medium",
        "description": "PAGINATION: 50 records/page × multiple pages",
    },
    "cursor": {
        "count": 50,
        "distribution": "daily",
        "start": "2026-01-15T00:00:00",
        "end":   "2026-01-21T23:59:59",
        "patterns": ["feat", "fix"],
        "volume": "small",
        "description": "CURSOR: cursor-based continuation",
    },
    "date_slice": {
        "count": 60,
        "distribution": "hourly",
        "start": "2026-02-01T00:00:00",
        "end":   "2026-02-14T23:59:59",
        "patterns": ["feat", "test"],
        "volume": "small",
        "description": "DATE_SLICE: time-based slicing (hourly/daily/weekly)",
    },
}


# ---------------------------------------------------------------------------
# Timestamp generation
# ---------------------------------------------------------------------------

def _parse_dt(value: str) -> datetime:
    """Parse an ISO-8601 string (with or without time component) to UTC datetime."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {value!r}")


def generate_timestamps(count: int, start: datetime, end: datetime, distribution: str) -> list[datetime]:
    """Return *count* timestamps between *start* and *end* according to *distribution*."""
    total_seconds = (end - start).total_seconds()
    if total_seconds <= 0:
        raise ValueError("end must be after start")

    timestamps: list[datetime] = []

    if distribution == "uniform":
        step = total_seconds / count
        for i in range(count):
            timestamps.append(start + timedelta(seconds=step * i + random.uniform(0, step * 0.5)))

    elif distribution == "hourly":
        # Cluster commits around business hours (8 – 18 h), a few per hour
        candidate_hours: list[datetime] = []
        cursor = start
        while cursor <= end:
            if 8 <= cursor.hour < 18:
                candidate_hours.append(cursor)
            cursor += timedelta(hours=1)
        if len(candidate_hours) < count:
            # Fall back to uniform if not enough business hours
            return generate_timestamps(count, start, end, "uniform")
        chosen = sorted(random.sample(candidate_hours, min(count, len(candidate_hours))))
        timestamps = [h + timedelta(minutes=random.randint(0, 59), seconds=random.randint(0, 59)) for h in chosen]

    elif distribution == "daily":
        # One or a handful of commits per day
        candidate_days: list[datetime] = []
        cursor = start.replace(hour=0, minute=0, second=0)
        while cursor <= end:
            candidate_days.append(cursor)
            cursor += timedelta(days=1)
        # Distribute commits across days (some days may have multiple)
        for _ in range(count):
            day = random.choice(candidate_days)
            ts = day + timedelta(
                hours=random.randint(8, 17),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )
            timestamps.append(ts)
        timestamps.sort()

    elif distribution == "weekly":
        # Commits concentrated at the start of each week
        candidate_weeks: list[datetime] = []
        cursor = start
        while cursor <= end:
            candidate_weeks.append(cursor)
            cursor += timedelta(weeks=1)
        for _ in range(count):
            week_start = random.choice(candidate_weeks)
            ts = week_start + timedelta(
                days=random.randint(0, 4),
                hours=random.randint(8, 17),
                minutes=random.randint(0, 59),
            )
            timestamps.append(min(ts, end))
        timestamps.sort()

    else:
        raise ValueError(f"Unknown distribution: {distribution!r}")

    # Ensure all timestamps fall within [start, end]
    return [max(start, min(ts, end)) for ts in timestamps]


# ---------------------------------------------------------------------------
# Commit / payload generation
# ---------------------------------------------------------------------------

def _random_message(patterns: list[str]) -> str:
    prefix = random.choice(patterns)
    templates = COMMIT_MESSAGE_PATTERNS.get(prefix, COMMIT_MESSAGE_PATTERNS["feat"])
    template = random.choice(templates)
    return template.format(
        noun=random.choice(NOUNS),
        verb=random.choice(VERBS),
        scope=random.choice(SCOPES),
    )


def _make_payload(volume: str, index: int, timestamp: datetime) -> dict:
    vol = DATA_VOLUME_PRESETS.get(volume, DATA_VOLUME_PRESETS["small"])
    records = []
    for i in range(min(vol["records"], 5)):   # store a sample in the file, not all records
        records.append({
            "id": f"rec-{index:04d}-{i:03d}",
            "timestamp": (timestamp + timedelta(seconds=i * 10)).isoformat(),
            "value": random.uniform(0, 1000),
            "tag": random.choice(NOUNS),
        })
    return {
        "commit_index": index,
        "timestamp": timestamp.isoformat(),
        "total_records": vol["records"],
        "approximate_bytes": vol["size_bytes"],
        "sample_records": records,
    }


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, capture_output=True, text=True, env=merged_env)
    if check and result.returncode != 0:
        print(f"ERROR running {' '.join(cmd)}\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def create_commit(
    repo_path: Path,
    timestamp: datetime,
    message: str,
    payload: dict,
    actor: str,
    data_dir: str = "data/generated",
) -> str:
    """
    Create a single git commit at the given *timestamp*.

    Returns the commit SHA.
    """
    # Write payload file
    payload_dir = repo_path / data_dir
    payload_dir.mkdir(parents=True, exist_ok=True)
    index = payload["commit_index"]
    payload_file = payload_dir / f"commit_{index:05d}.json"
    payload_file.write_text(json.dumps(payload, indent=2))

    # Stage the file
    _run(["git", "-C", str(repo_path), "add", str(payload_file)])

    # Build the author/committer env with the desired timestamp
    iso_ts = timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    commit_env = {
        "GIT_AUTHOR_NAME": actor,
        "GIT_AUTHOR_EMAIL": f"{actor}@ediz-test.local",
        "GIT_AUTHOR_DATE": iso_ts,
        "GIT_COMMITTER_NAME": actor,
        "GIT_COMMITTER_EMAIL": f"{actor}@ediz-test.local",
        "GIT_COMMITTER_DATE": iso_ts,
    }

    result = _run(
        ["git", "-C", str(repo_path), "commit", "-m", message],
        env=commit_env,
    )

    # Extract SHA from output
    sha_result = _run(["git", "-C", str(repo_path), "rev-parse", "HEAD"])
    return sha_result.stdout.strip()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate bulk git commits for EDIZ test scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--repo", default=".", help="Path to the git repository (default: current dir)")
    p.add_argument("--count", type=int, default=30, help="Number of commits to create")
    p.add_argument(
        "--distribution",
        choices=["uniform", "hourly", "daily", "weekly"],
        default="daily",
        help="How to spread commits over the time window",
    )
    p.add_argument("--start", default="2026-01-01", help="Start datetime (ISO-8601)")
    p.add_argument("--end",   default="2026-01-31", help="End datetime (ISO-8601)")
    p.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        choices=list(COMMIT_MESSAGE_PATTERNS.keys()),
        metavar="PATTERN",
        help="Commit message prefix to include (repeat for multiple). Default: all.",
    )
    p.add_argument(
        "--volume",
        choices=list(DATA_VOLUME_PRESETS.keys()),
        default="small",
        help="Data payload size per commit",
    )
    p.add_argument(
        "--preset",
        choices=list(SCENARIO_PRESETS.keys()),
        help="Use a predefined EDIZ scenario preset (overrides other options)",
    )
    p.add_argument("--data-dir", default="data/generated", help="Subdirectory for payload files")
    p.add_argument("--dry-run", action="store_true", help="Print what would be done without committing")
    return p


def main() -> None:
    args = build_parser().parse_args()

    # ------------------------------------------------------------------
    # Resolve configuration (preset takes precedence)
    # ------------------------------------------------------------------
    if args.preset:
        preset = SCENARIO_PRESETS[args.preset]
        print(f"Using preset: {args.preset!r} — {preset['description']}")
        count        = preset["count"]
        distribution = preset["distribution"]
        start        = _parse_dt(preset["start"])
        end          = _parse_dt(preset["end"])
        patterns     = preset["patterns"]
        volume       = preset["volume"]
    else:
        count        = args.count
        distribution = args.distribution
        start        = _parse_dt(args.start)
        end          = _parse_dt(args.end)
        patterns     = args.patterns or list(COMMIT_MESSAGE_PATTERNS.keys())
        volume       = args.volume

    repo_path = Path(args.repo).resolve()
    data_dir  = args.data_dir

    print(f"Repository : {repo_path}")
    print(f"Commits    : {count}")
    print(f"Window     : {start.isoformat()} → {end.isoformat()}")
    print(f"Distribution: {distribution}")
    print(f"Patterns   : {patterns}")
    print(f"Volume     : {volume}")
    print(f"Data dir   : {data_dir}")
    print()

    if args.dry_run:
        print("[dry-run] No commits will be created.")

    # ------------------------------------------------------------------
    # Generate timestamps
    # ------------------------------------------------------------------
    timestamps = generate_timestamps(count, start, end, distribution)

    # ------------------------------------------------------------------
    # Create commits
    # ------------------------------------------------------------------
    shas: list[str] = []
    for idx, ts in enumerate(timestamps):
        actor   = random.choice(ACTORS)
        message = _random_message(patterns)
        payload = _make_payload(volume, idx, ts)

        if args.dry_run:
            print(f"  [{idx+1:3d}] {ts.isoformat()}  {actor}  {message!r}")
            continue

        sha = create_commit(repo_path, ts, message, payload, actor, data_dir)
        shas.append(sha)
        print(f"  [{idx+1:3d}] {sha[:8]}  {ts.isoformat()}  {message!r}")

    if not args.dry_run:
        print(f"\nDone. Created {len(shas)} commits.")
    else:
        print(f"\n[dry-run] Would create {count} commits.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
pause_resume_activity.py
------------------------
Simulate data gaps by pausing and resuming commit activity.

When testing HIGH_WATERMARK or DATE_SLICE ingestion modes it is important
to have periods in the commit history where *no* data was produced — so the
ingestor has to correctly handle empty windows.

This script provides two operations:

1. **pause**  – Records the "last active commit" SHA and the pause timestamp
   so you know where the gap started.

2. **resume** – Creates a "resume" commit immediately after the gap using
   a timestamp you specify, then optionally generates a burst of commits to
   simulate activity restarting.

Usage:
    # Start a simulated gap at a specific datetime
    python pause_resume_activity.py pause --at 2026-02-10T09:00:00

    # Resume activity (gap from 2026-02-10 to 2026-02-14)
    python pause_resume_activity.py resume \\
        --at 2026-02-14T09:00:00 \\
        --burst 5 \\
        --burst-end 2026-02-14T18:00:00

    # List all recorded pauses/resumes
    python pause_resume_activity.py list

    # Generate an activity timeline showing gaps visually
    python pause_resume_activity.py timeline --start 2026-02-01 --end 2026-02-28
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

GAP_STATE_FILE = "data/gaps/gap_state.json"
ACTORS = ["dev-user-1", "dev-user-2", "dev-user-3"]

RESUME_MESSAGES = [
    "chore: resume activity after maintenance window",
    "feat: restart data generation post-gap",
    "fix: re-enable commit activity",
    "chore: activity resumed — gap simulation complete",
    "feat: restore normal commit cadence",
]

BURST_MESSAGES = [
    "feat: catch-up batch after gap",
    "chore: post-gap data reconciliation",
    "test: validate watermark after gap window",
    "feat: add burst activity record",
    "fix: process backlog from gap period",
]


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


def _load_gap_state(repo_path: Path) -> dict:
    state_file = repo_path / GAP_STATE_FILE
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"pauses": [], "resumes": []}


def _save_gap_state(repo_path: Path, state: dict) -> None:
    state_file = repo_path / GAP_STATE_FILE
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


def _get_head_sha(repo_path: Path) -> str:
    return _run(["git", "-C", str(repo_path), "rev-parse", "HEAD"]).stdout.strip()


def _commit_with_timestamp(
    repo_path: Path,
    timestamp: datetime,
    message: str,
    actor: str,
    file_path: Path,
    file_content: dict,
) -> str:
    """Write a file, stage it, and commit with a specific timestamp."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(file_content, indent=2))

    _run(["git", "-C", str(repo_path), "add", str(file_path)])

    iso_ts = timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    commit_env = {
        "GIT_AUTHOR_NAME": actor,
        "GIT_AUTHOR_EMAIL": f"{actor}@ediz-test.local",
        "GIT_AUTHOR_DATE": iso_ts,
        "GIT_COMMITTER_NAME": actor,
        "GIT_COMMITTER_EMAIL": f"{actor}@ediz-test.local",
        "GIT_COMMITTER_DATE": iso_ts,
    }
    _run(["git", "-C", str(repo_path), "commit", "-m", message], env=commit_env)
    return _get_head_sha(repo_path)


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_pause(args: argparse.Namespace) -> None:
    repo_path = Path(args.repo).resolve()
    pause_at  = _parse_dt(args.at)
    head_sha  = _get_head_sha(repo_path)

    state = _load_gap_state(repo_path)
    pause_entry = {
        "id": f"gap-{len(state['pauses']) + 1:03d}",
        "paused_at": pause_at.isoformat(),
        "last_commit_sha": head_sha,
        "note": args.note or "",
    }
    state["pauses"].append(pause_entry)
    _save_gap_state(repo_path, state)

    if not args.dry_run:
        # Commit the updated gap state file with the pause timestamp
        actor = random.choice(ACTORS)
        _commit_with_timestamp(
            repo_path,
            pause_at,
            f"chore: record activity pause [{pause_entry['id']}]",
            actor,
            repo_path / GAP_STATE_FILE,
            state,
        )
        print(f"Pause recorded: {pause_entry['id']} at {pause_at.isoformat()} (HEAD: {head_sha[:8]})")
    else:
        print(f"[dry-run] Would record pause {pause_entry['id']} at {pause_at.isoformat()}")


def cmd_resume(args: argparse.Namespace) -> None:
    repo_path = Path(args.repo).resolve()
    resume_at = _parse_dt(args.at)

    state = _load_gap_state(repo_path)

    # Find the most recent unmatched pause
    last_pause = None
    pause_ids_with_resume = {r.get("pause_id") for r in state.get("resumes", [])}
    for p in reversed(state.get("pauses", [])):
        if p["id"] not in pause_ids_with_resume:
            last_pause = p
            break

    gap_duration: str | None = None
    if last_pause:
        pause_dt = _parse_dt(last_pause["paused_at"])
        delta = resume_at - pause_dt
        gap_duration = f"{delta.days}d {delta.seconds // 3600}h"

    resume_entry = {
        "id": f"resume-{len(state['resumes']) + 1:03d}",
        "resumed_at": resume_at.isoformat(),
        "pause_id": last_pause["id"] if last_pause else None,
        "gap_duration": gap_duration,
        "note": args.note or "",
    }
    state["resumes"].append(resume_entry)
    _save_gap_state(repo_path, state)

    if args.dry_run:
        print(f"[dry-run] Would record resume {resume_entry['id']} at {resume_at.isoformat()}")
        if gap_duration:
            print(f"[dry-run] Gap duration: {gap_duration}")
        if args.burst:
            print(f"[dry-run] Would create {args.burst} burst commits")
        return

    # Commit the resume marker
    actor = random.choice(ACTORS)
    sha = _commit_with_timestamp(
        repo_path,
        resume_at,
        random.choice(RESUME_MESSAGES),
        actor,
        repo_path / GAP_STATE_FILE,
        state,
    )
    print(f"Resume recorded: {resume_entry['id']} at {resume_at.isoformat()} (SHA: {sha[:8]})")
    if gap_duration:
        print(f"Gap duration: {gap_duration}")

    # Optionally create a burst of commits after resuming
    if args.burst and args.burst > 0:
        burst_end_dt = _parse_dt(args.burst_end) if args.burst_end else resume_at + timedelta(hours=4)
        step = (burst_end_dt - resume_at) / args.burst
        print(f"Creating {args.burst} burst commits ({resume_at.isoformat()} → {burst_end_dt.isoformat()})")
        for i in range(args.burst):
            ts      = resume_at + step * i + timedelta(seconds=random.randint(0, int(step.total_seconds() * 0.5)))
            ts      = min(ts, burst_end_dt)
            actor   = random.choice(ACTORS)
            message = BURST_MESSAGES[i % len(BURST_MESSAGES)]
            burst_file = repo_path / "data" / "gaps" / f"burst_{resume_entry['id']}_{i:03d}.json"
            _commit_with_timestamp(
                repo_path, ts, message, actor, burst_file,
                {"burst_index": i, "timestamp": ts.isoformat(), "resume_id": resume_entry["id"]},
            )
            sha = _get_head_sha(repo_path)
            print(f"  [{i+1:3d}] {sha[:8]}  {ts.isoformat()}  {message!r}")


def cmd_list(args: argparse.Namespace) -> None:
    repo_path = Path(args.repo).resolve()
    state = _load_gap_state(repo_path)

    print("=== Recorded Pauses ===")
    for p in state.get("pauses", []):
        print(f"  {p['id']}: paused at {p['paused_at']}  (last SHA: {p.get('last_commit_sha', 'unknown')[:8]})")

    print("\n=== Recorded Resumes ===")
    for r in state.get("resumes", []):
        print(f"  {r['id']}: resumed at {r['resumed_at']}  gap={r.get('gap_duration', '?')}  pause_id={r.get('pause_id')}")


def cmd_timeline(args: argparse.Namespace) -> None:
    """Print a simple ASCII timeline showing active/gap periods."""
    repo_path = Path(args.repo).resolve()
    state = _load_gap_state(repo_path)
    start = _parse_dt(args.start)
    end   = _parse_dt(args.end)

    days = (end - start).days + 1
    print(f"Activity timeline: {start.date()} → {end.date()}  ({days} days)")
    print("  Legend: █ = active  · = gap")
    print()

    # Build pause/resume intervals
    gaps: list[tuple[datetime, datetime]] = []
    pauses_by_id = {p["id"]: p for p in state.get("pauses", [])}
    for r in state.get("resumes", []):
        if r.get("pause_id") and r["pause_id"] in pauses_by_id:
            p = pauses_by_id[r["pause_id"]]
            gaps.append((_parse_dt(p["paused_at"]), _parse_dt(r["resumed_at"])))

    line = ""
    for d in range(days):
        day_dt = start + timedelta(days=d)
        in_gap = any(gap_start <= day_dt < gap_end for gap_start, gap_end in gaps)
        line += "·" if in_gap else "█"

    # Print in rows of 28 (4 weeks)
    row_size = 28
    for row in range(0, days, row_size):
        label = (start + timedelta(days=row)).strftime("%Y-%m-%d")
        print(f"  {label}  {line[row:row + row_size]}")

    print()
    if gaps:
        print("Gaps:")
        for g_start, g_end in gaps:
            delta = g_end - g_start
            print(f"  {g_start.date()} → {g_end.date()}  ({delta.days} days)")
    else:
        print("No gaps recorded.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Simulate activity gaps for EDIZ gap-tolerance tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--repo", default=".", help="Path to git repository (default: current dir)")
    sub = p.add_subparsers(dest="command", required=True)

    # pause
    pause_p = sub.add_parser("pause", help="Record the start of an activity gap")
    pause_p.add_argument("--at", required=True, help="ISO-8601 datetime when the gap starts")
    pause_p.add_argument("--note", help="Optional description")
    pause_p.add_argument("--dry-run", action="store_true")

    # resume
    resume_p = sub.add_parser("resume", help="Record the end of an activity gap")
    resume_p.add_argument("--at", required=True, help="ISO-8601 datetime when activity resumes")
    resume_p.add_argument("--note", help="Optional description")
    resume_p.add_argument("--burst", type=int, default=0, help="Number of burst commits to create after resuming")
    resume_p.add_argument("--burst-end", help="End datetime for burst commits (default: 4 h after --at)")
    resume_p.add_argument("--dry-run", action="store_true")

    # list
    sub.add_parser("list", help="List all recorded pauses/resumes")

    # timeline
    tl_p = sub.add_parser("timeline", help="Print ASCII activity timeline")
    tl_p.add_argument("--start", default="2026-01-01", help="Start date")
    tl_p.add_argument("--end",   default="2026-02-28", help="End date")

    return p


def main() -> None:
    args = build_parser().parse_args()
    if   args.command == "pause":    cmd_pause(args)
    elif args.command == "resume":   cmd_resume(args)
    elif args.command == "list":     cmd_list(args)
    elif args.command == "timeline": cmd_timeline(args)
    else:
        build_parser().print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

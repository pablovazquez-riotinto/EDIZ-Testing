#!/usr/bin/env python3
"""
reset_repo.py
-------------
Reset the repository to its initial state for clean EDIZ test runs.

Operations:
  - hard    : Reset to a specific commit / tag / initial state (destructive)
  - clean   : Remove generated data files but preserve scripts and docs
  - status  : Show current repository state (commits, branches, gaps)
  - checkpoint : Create a tagged checkpoint for easy rollback

Usage:
    python reset_repo.py status
    python reset_repo.py checkpoint --name pre-test-run-1
    python reset_repo.py clean
    python reset_repo.py hard --to v0.1.0
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"ERROR: {' '.join(cmd)}\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def _repo_path(args: argparse.Namespace) -> Path:
    return Path(args.repo).resolve()


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> None:
    rp = _repo_path(args)

    print("=== Repository Status ===\n")

    # Current branch
    branch = _run(["git", "-C", str(rp), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    print(f"Branch      : {branch}")

    # HEAD commit
    head  = _run(["git", "-C", str(rp), "rev-parse", "HEAD"]).stdout.strip()
    short = head[:8]
    log   = _run(["git", "-C", str(rp), "log", "-1", "--format=%ci %s", "HEAD"]).stdout.strip()
    print(f"HEAD        : {short}  {log}")

    # Commit count
    count = _run(["git", "-C", str(rp), "rev-list", "--count", "HEAD"]).stdout.strip()
    print(f"Total commits: {count}")

    # Tags
    tags = _run(["git", "-C", str(rp), "tag", "-l"]).stdout.strip()
    print(f"Tags        : {tags or '(none)'}")

    # Branches
    print("\nBranches:")
    branches = _run(["git", "-C", str(rp), "branch", "-a"]).stdout.strip()
    for b in branches.splitlines():
        print(f"  {b}")

    # Working tree status
    status = _run(["git", "-C", str(rp), "status", "--short"]).stdout.strip()
    print(f"\nWorking tree: {'clean' if not status else 'DIRTY'}")
    if status:
        for line in status.splitlines():
            print(f"  {line}")

    # Gap state
    gap_file = rp / "data" / "gaps" / "gap_state.json"
    if gap_file.exists():
        state = json.loads(gap_file.read_text())
        pauses  = len(state.get("pauses", []))
        resumes = len(state.get("resumes", []))
        print(f"\nGap state   : {pauses} pause(s), {resumes} resume(s)")
    else:
        print("\nGap state   : no gaps recorded")


def cmd_checkpoint(args: argparse.Namespace) -> None:
    rp   = _repo_path(args)
    name = args.name or datetime.now(tz=timezone.utc).strftime("checkpoint-%Y%m%d-%H%M%S")
    tag  = f"cp/{name}"

    if args.dry_run:
        print(f"[dry-run] Would create tag: {tag}")
        return

    _run(["git", "-C", str(rp), "tag", "-a", tag, "-m", f"Checkpoint: {name}"])
    print(f"Checkpoint created: {tag}")
    head = _run(["git", "-C", str(rp), "rev-parse", "HEAD"]).stdout.strip()
    print(f"HEAD: {head[:8]}")
    print(f"\nTo restore later:\n  python reset_repo.py hard --to {tag}")


def cmd_clean(args: argparse.Namespace) -> None:
    """Remove generated data files while keeping scripts and docs."""
    rp = _repo_path(args)

    patterns = [
        "data/generated/",
        "data/historical/",
        "data/gaps/",
    ]

    print("Cleaning generated data directories:")
    for pattern in patterns:
        target = rp / pattern
        if target.exists():
            if args.dry_run:
                file_count = sum(1 for _ in target.rglob("*") if _.is_file())
                print(f"  [dry-run] Would remove {file_count} files in {pattern}")
            else:
                # Use git rm to keep index clean
                result = _run(
                    ["git", "-C", str(rp), "rm", "-rf", "--ignore-unmatch", pattern],
                    check=False,
                )
                if result.returncode == 0:
                    print(f"  Removed: {pattern}")
                else:
                    print(f"  Nothing to remove in: {pattern}")
        else:
            print(f"  Not found (skip): {pattern}")

    if not args.dry_run:
        # Check if there is anything to commit
        status = _run(["git", "-C", str(rp), "status", "--short"]).stdout.strip()
        if status:
            _run(["git", "-C", str(rp), "commit", "-m", "chore: clean generated data for test reset"])
            print("\nClean commit created.")
        else:
            print("\nNothing to commit — working tree already clean.")


def cmd_hard(args: argparse.Namespace) -> None:
    """Hard-reset the repository to a specific ref (DESTRUCTIVE)."""
    rp  = _repo_path(args)
    ref = args.to

    if args.dry_run:
        # Show what commits would be removed
        log = _run(["git", "-C", str(rp), "log", "--oneline", f"{ref}..HEAD"]).stdout.strip()
        if log:
            print(f"[dry-run] Would remove these commits (HEAD → {ref}):")
            for line in log.splitlines():
                print(f"  {line}")
        else:
            print(f"[dry-run] HEAD is already at or before {ref}")
        return

    # Confirm unless --yes
    if not args.yes:
        answer = input(
            f"WARNING: This will hard-reset to {ref!r} and discard all later commits.\n"
            f"Continue? [y/N] "
        ).strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    _run(["git", "-C", str(rp), "reset", "--hard", ref])
    head = _run(["git", "-C", str(rp), "rev-parse", "HEAD"]).stdout.strip()
    print(f"Hard-reset complete. HEAD is now: {head[:8]}")
    print("NOTE: If you pushed this branch, you will need to force-push.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reset EDIZ test repository state for clean test runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--repo", default=".", help="Path to git repository (default: current dir)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show current repository state")

    cp_p = sub.add_parser("checkpoint", help="Create a tagged checkpoint for easy rollback")
    cp_p.add_argument("--name", help="Checkpoint name (default: timestamp-based)")
    cp_p.add_argument("--dry-run", action="store_true")

    clean_p = sub.add_parser("clean", help="Remove generated data files (keeps scripts and docs)")
    clean_p.add_argument("--dry-run", action="store_true")

    hard_p = sub.add_parser("hard", help="Hard-reset to a ref (DESTRUCTIVE)")
    hard_p.add_argument("--to", required=True, metavar="REF", help="Tag, commit SHA, or branch to reset to")
    hard_p.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    hard_p.add_argument("--dry-run", action="store_true")

    return p


def main() -> None:
    args = build_parser().parse_args()
    if   args.command == "status":     cmd_status(args)
    elif args.command == "checkpoint": cmd_checkpoint(args)
    elif args.command == "clean":      cmd_clean(args)
    elif args.command == "hard":       cmd_hard(args)
    else:
        build_parser().print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

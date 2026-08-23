# EDIZ Test Data Scenarios

**ediz-test-data-scenarios** is a comprehensive test repository for validating
[EDIZ](https://ediz.readthedocs.io) (Extract-Ingest-Data-Zones) API ingestion
pipelines across all supported ingestion modes.

---

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [Quick Start](#quick-start)
3. [Ingestion Mode Scenarios](#ingestion-mode-scenarios)
   - [SNAPSHOT](#snapshot)
   - [HIGH_WATERMARK](#high_watermark)
   - [PAGINATION](#pagination)
   - [CURSOR](#cursor)
   - [DATE_SLICE](#date_slice)
4. [Testing Utilities](#testing-utilities)
   - [generate_commits.py](#generate_commitspy)
   - [backdate_history.py](#backdate_historypy)
   - [pause_resume_activity.py](#pause_resume_activitypy)
   - [reset_repo.py](#reset_repopy)
5. [Commit Log & Timestamps](#commit-log--timestamps)
6. [Branch Structure](#branch-structure)
7. [Resetting for Clean Test Runs](#resetting-for-clean-test-runs)
8. [Expected Behaviour per Mode](#expected-behaviour-per-mode)

---

## Repository Layout

```
ediz-test-data-scenarios/
├── data/
│   ├── activity_logs/          # Monthly activity log JSON files
│   │   ├── activity_log_2026_01.json
│   │   └── activity_log_2026_02.json
│   ├── events/                 # API event records (request/response traces)
│   │   └── api_events_2026_01.json
│   ├── metadata/               # Repository & ingestion state metadata
│   │   └── repo_metadata.json
│   ├── generated/              # Output of generate_commits.py (git-ignored)
│   ├── historical/             # Output of backdate_history.py (git-ignored)
│   └── gaps/                   # Gap state managed by pause_resume_activity.py
│       └── gap_state.json
├── scripts/
│   ├── generate_commits.py     # Bulk commit generator (configurable)
│   ├── backdate_history.py     # Historical seed & timestamp shifting
│   ├── pause_resume_activity.py # Simulate activity gaps
│   └── reset_repo.py           # Clean reset for test runs
├── docs/
│   └── scenarios/              # Detailed per-scenario documentation
└── README.md
```

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/ediz-test-data-scenarios.git
cd ediz-test-data-scenarios

# (Optional) Create a virtual environment for the scripts
python -m venv .venv && source .venv/bin/activate

# No external dependencies required — scripts use stdlib only.

# Verify state
python scripts/reset_repo.py status
```

---

## Ingestion Mode Scenarios

### SNAPSHOT

**What it does:** Performs a full load of all records from a fixed start date,
regardless of any previous ingestion runs.

**Test scenario:**

```
Start date : 2026-01-01T00:00:00Z
Expected   : All 40 commits in the January activity log ingested
Pages      : 40 records ÷ 10 per page = 4 pages fetched
```

**How to set up:**

```bash
# Generate 40 commits spread over January 2026
python scripts/generate_commits.py \
  --preset snapshot \
  --repo .
```

**Expected behaviour:**

- Each run re-fetches everything from `since=2026-01-01T00:00:00Z`.
- The ingestor should handle duplicate detection or upsert logic.
- `data/activity_logs/activity_log_2026_01.json` shows the expected 20 seed records.
- Pages should be exhausted when the API returns `HTTP 204 No Content` or
  an empty `records` array.

---

### HIGH_WATERMARK

**What it does:** Incremental ingestion using an automatically managed `since`
/ `until` window that advances each run.

**Test scenario:**

```
Window size    : 24 hours (configurable)
First window   : since=2026-01-09T09:00:00Z  until=2026-01-10T09:00:00Z
Second window  : since=2026-01-10T09:00:00Z  until=2026-01-11T09:00:00Z
…
Gap window     : since=2026-02-10T09:00:00Z  until=2026-02-14T09:00:00Z → 0 records (gap)
Resume window  : since=2026-02-14T09:00:00Z  until=2026-02-15T09:00:00Z → records present
```

**How to set up:**

```bash
# Generate daily watermark data for February 2026
python scripts/generate_commits.py --preset watermark --repo .

# Simulate a gap (no commits 2026-02-10 to 2026-02-14)
python scripts/pause_resume_activity.py pause  --at 2026-02-10T09:00:00 --repo .
python scripts/pause_resume_activity.py resume --at 2026-02-14T09:00:00 --burst 5 --repo .
```

**Expected behaviour:**

- Watermark advances by window size on each successful run.
- Empty windows (gap period) return `HTTP 204` or empty records — watermark
  still advances.
- After resuming, the ingestor catches up to the current time.
- See `data/metadata/repo_metadata.json → ingestion_state.high_watermark`
  for the expected final watermark value.

---

### PAGINATION

**What it does:** Retrieves large data sets split across multiple pages of
exactly 50 records each.

**Test scenario:**

```
Total records  : 150
Page size      : 50
Expected pages : 3  (pages 1, 2, 3 return 50 records; page 4 returns 204)
Branch         : feature/pagination
```

**How to set up:**

```bash
# Generate 150 commits hourly (creates many records per day)
python scripts/generate_commits.py \
  --count 150 \
  --distribution hourly \
  --start 2026-01-01T08:00:00 \
  --end   2026-01-07T18:00:00 \
  --volume medium \
  --repo .
```

**Expected behaviour:**

- `GET /commits?per_page=50&page=1` → 50 records, `Link: <...>; rel="next"`
- `GET /commits?per_page=50&page=2` → 50 records, `Link: <...>; rel="next"`
- `GET /commits?per_page=50&page=3` → 50 records, `Link: <...>; rel="next"`
- `GET /commits?per_page=50&page=4` → 204 No Content (or empty list) — stop
- See `data/events/api_events_2026_01.json` for recorded pagination traces
  (events ev-0001 through ev-0005).

---

### CURSOR

**What it does:** Uses an opaque cursor token returned by each response to
retrieve the next page, instead of numeric page offsets.

**Test scenario:**

```
Initial request   : GET /commits?per_page=50               → cursor=eyJpZCI6IDEwMH0=
Continuation 1    : GET /commits?cursor=eyJpZCI6IDEwMH0=   → cursor=eyJpZCI6IDE1MH0=
Continuation 2    : GET /commits?cursor=eyJpZCI6IDE1MH0=   → no cursor (last page)
Branch            : feature/cursor
```

**How to set up:**

```bash
python scripts/generate_commits.py --preset cursor --repo .
```

**Expected behaviour:**

- First request has no cursor parameter.
- Each response includes a `next_cursor` field (or `Link: rel="next"` header
  containing the cursor).
- When `next_cursor` is absent or `null`, pagination is complete.
- If ingestion is interrupted mid-cursor, the last cursor can be stored and
  resumed without re-fetching earlier pages.
- See `data/events/api_events_2026_01.json` events ev-0006 through ev-0008.

---

### DATE_SLICE

**What it does:** Divides a time range into fixed-size slices (e.g. 2 hours)
and fetches each slice independently, enabling parallel ingestion and
fine-grained retry.

**Test scenario:**

```
Full range     : 2026-01-15T08:00:00Z → 2026-01-15T14:00:00Z
Slice size     : 2 hours
Slices         : [08:00–10:00], [10:00–12:00], [12:00–14:00]
Slice 1 result : 8 records
Slice 2 result : 5 records
Slice 3 result : 0 records (empty slice → HTTP 204)
Branch         : feature/date-slice
```

**How to set up:**

```bash
python scripts/generate_commits.py --preset date_slice --repo .
```

**Extended scenarios (weekly slices):**

```bash
python scripts/generate_commits.py \
  --count 60 \
  --distribution weekly \
  --start 2026-02-01 \
  --end   2026-02-28 \
  --volume small \
  --repo .
```

**Expected behaviour:**

- Each slice is an independent request with `since` and `until` parameters.
- Empty slices are normal — ingestor should skip and move to the next slice.
- Slices can be processed in parallel if the ingestor supports it.
- See `data/events/api_events_2026_01.json` events ev-0020 through ev-0022.

---

## Testing Utilities

### generate_commits.py

Programmatically create bulk commits with configurable parameters.

```
scripts/generate_commits.py [-h]
  --repo         PATH      Repository path (default: .)
  --count        N         Number of commits (default: 30)
  --distribution {uniform,hourly,daily,weekly}
  --start        ISO-8601  Window start
  --end          ISO-8601  Window end
  --pattern      PATTERN   Commit prefix: feat|fix|chore|docs|test|refactor
  --volume       {tiny,small,medium,large}
  --preset       {snapshot,watermark,pagination,cursor,date_slice}
  --data-dir     PATH      Sub-directory for payload files (default: data/generated)
  --dry-run                Print plan without committing
```

**Presets:**

| Preset       | Commits | Distribution | Window          | Volume |
|--------------|---------|--------------|-----------------|--------|
| `snapshot`   | 40      | daily        | Jan 2026        | small  |
| `watermark`  | 30      | daily        | Feb 2026        | tiny   |
| `pagination` | 150     | hourly       | Jan 1–7 2026    | medium |
| `cursor`     | 50      | daily        | Jan 15–21 2026  | small  |
| `date_slice` | 60      | hourly       | Feb 1–14 2026   | small  |

---

### backdate_history.py

Seed historical commits or shift existing commit timestamps.

```bash
# Seed 20 commits on working days in November 2025
python scripts/backdate_history.py seed \
  --start 2025-11-01 --end 2025-11-30 --count 20 --repo .

# Seed commits from an explicit list of timestamps
python scripts/backdate_history.py seed \
  --timestamps-file /path/to/timestamps.json --repo .

# Shift all commits back 90 days
python scripts/backdate_history.py shift --days -90 --repo .

# Dry-run: preview without committing
python scripts/backdate_history.py seed \
  --start 2025-12-01 --end 2025-12-31 --count 10 --dry-run --repo .
```

The seed command writes a `data/historical/commit_log.json` file listing all
created commits with their exact timestamps — useful for validating SNAPSHOT
ingestion results.

---

### pause_resume_activity.py

Simulate data gaps by pausing and resuming activity.

```bash
# Record a pause at a specific time
python scripts/pause_resume_activity.py pause \
  --at 2026-02-10T09:00:00 --note "Maintenance window" --repo .

# Resume with a burst of 5 commits over 4 hours
python scripts/pause_resume_activity.py resume \
  --at 2026-02-14T09:00:00 --burst 5 --burst-end 2026-02-14T18:00:00 --repo .

# List all recorded pauses/resumes
python scripts/pause_resume_activity.py list --repo .

# Print an ASCII activity timeline
python scripts/pause_resume_activity.py timeline \
  --start 2026-02-01 --end 2026-02-28 --repo .
```

**Example timeline output:**

```
Activity timeline: 2026-02-01 → 2026-02-28  (28 days)
  Legend: █ = active  · = gap

  2026-02-01  █████████·····████████████████
```

---

### reset_repo.py

Reset the repository for clean test runs.

```bash
# Show current state
python scripts/reset_repo.py status

# Create a checkpoint before a test run
python scripts/reset_repo.py checkpoint --name pre-snapshot-test

# Remove generated/historical/gap data only
python scripts/reset_repo.py clean

# Hard reset to a checkpoint or tag (DESTRUCTIVE)
python scripts/reset_repo.py hard --to cp/pre-snapshot-test
```

---

## Commit Log & Timestamps

The `data/activity_logs/` directory contains two months of seed activity records
with exact timestamps. Use these as ground truth when validating ingestor output.

**January 2026 highlights:**

| ID       | Timestamp            | Event               | Branch             |
|----------|----------------------|---------------------|--------------------|
| act-001  | 2026-01-01T08:00:00Z | commit – init       | main               |
| act-005  | 2026-01-05T14:00:00Z | commit – pagination | feature/pagination |
| act-010  | 2026-01-14T10:30:00Z | merge               | main               |
| act-011  | 2026-01-15T09:00:00Z | commit – cursor     | feature/cursor     |
| act-017  | 2026-01-25T16:00:00Z | merge (cursor)      | main               |

**February 2026 highlights:**

| ID       | Timestamp            | Event               | Branch             |
|----------|----------------------|---------------------|--------------------|
| act-025  | 2026-02-07T11:00:00Z | commit – utility    | dev                |
| act-027  | 2026-02-10T16:00:00Z | merge (Feb iter.)   | main               |
| act-033  | 2026-02-20T15:00:00Z | commit – gap sim    | dev                |
| act-036  | 2026-02-23T14:00:00Z | merge (snapshot)    | main               |
| act-038  | 2026-02-25T09:00:00Z | merge (watermark)   | main               |

---

## Branch Structure

| Branch              | Purpose                                     | Status    |
|---------------------|---------------------------------------------|-----------|
| `main`              | Stable release branch                       | Protected |
| `dev`               | Development integration                     | Active    |
| `feature/pagination`| 50 records/page × multiple pages tests      | Merged    |
| `feature/cursor`    | Cursor-based continuation tests             | Merged    |
| `feature/filtering` | Tag-based and field filter tests            | Active    |
| `feature/date-slice`| Hourly/daily/weekly slice tests             | Active    |
| `feature/snapshot`  | Full SNAPSHOT load scenarios                | Merged    |
| `feature/watermark` | HIGH_WATERMARK incremental scenarios        | Merged    |

---

## Resetting for Clean Test Runs

### Option 1 – Clean only generated data

```bash
python scripts/reset_repo.py clean
```

Removes `data/generated/`, `data/historical/`, and `data/gaps/` but leaves
seed data (`activity_logs/`, `events/`, `metadata/`) intact.

### Option 2 – Checkpoint and rollback

```bash
# Before the test run:
python scripts/reset_repo.py checkpoint --name before-my-test

# … run tests …

# To restore:
python scripts/reset_repo.py hard --to cp/before-my-test
```

### Option 3 – Re-seed from scratch

```bash
# Hard reset to the initial commit (v0.1.0 tag):
python scripts/reset_repo.py hard --to v0.1.0 --yes

# Re-generate data for the desired scenario:
python scripts/generate_commits.py --preset snapshot --repo .
```

---

## Expected Behaviour per Mode

| Mode            | Empty window  | Duplicate run | Partial page | Out-of-order |
|-----------------|---------------|---------------|--------------|--------------|
| SNAPSHOT        | Re-fetch all  | Full reload   | No (N/A)     | Sort by time |
| HIGH_WATERMARK  | Advance mark  | Idempotent    | Fetch rest   | Sort by time |
| PAGINATION      | Stop (204)    | Idempotent    | Fetch rest   | Ordered      |
| CURSOR          | Stop (null)   | Resume cursor | Fetch rest   | Ordered      |
| DATE_SLICE      | Skip slice    | Re-run slice  | Fetch rest   | Parallel OK  |

---

## Adding More Data Types

The project structure is designed for easy expansion:

```
data/
  <new_data_type>/        # e.g. pull_requests/, issues/, deployments/
    <new_data_type>_2026_01.json
```

Copy the schema from `data/activity_logs/activity_log_2026_01.json` and
update the `data_type` and `records` fields accordingly.

---

## License

This test repository is provided for testing and evaluation purposes only.
See [LICENSE](LICENSE) for details.

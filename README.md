# Claude COS (Chief of Staff)

An automated personal chief-of-staff powered by Claude Code. It scans your Gmail inbox, extracts actionable tasks, and creates them in your Notion "Tasks" database — so nothing slips through the cracks.

## What It Does

1. **Inbox Scan** — Searches recent Gmail messages (excluding promotions, social, updates, forums), triages by snippet, and reads actionable emails in full.
2. **Task Extraction** — Identifies action items (questions, deliverables, scheduling requests, commitments) and creates Notion tasks with priority, due date, duration estimate, and source link.
3. **Task Hygiene** — Reviews recently added Notion tasks and fills in missing priorities, durations, and due dates.
4. **State Tracking** — Maintains `last-scan-timestamp.json` so each run only processes new emails since the last scan.

## Priority Framework

| Level | Meaning | Litmus Test |
|-------|---------|-------------|
| **P1** | Hard consequence if missed | "If I miss this, something bad happens I can't fix next week." |
| **P2** | Time-sensitive, delay compounds | "Delay narrows my options or creates a crunch later." |
| **P3** | Important, flexible timing | "I'd be annoyed if this slipped a month, but a few days is fine." |
| **P4** | Do when there's space | "If this disappeared for two weeks, I wouldn't notice." |

## Tools Required

- **Gmail** — Search and read (never sends email)
- **Notion** — Search, create, and update pages in a "Tasks" database

## Setup

**Requirements:** Python 3.11+, [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with Gmail and Notion MCP servers configured.

1. Clone the repo
2. Edit `config.toml` to adjust settings (defaults work out of the box)
3. Ensure Claude Code has the required MCP permissions (see `.claude/settings.local.json`)

## Usage

```bash
# Run a full inbox scan
python cos.py scan

# Preview what would happen without creating tasks
python cos.py scan --dry-run

# See full agent output
python cos.py scan --verbose

# View recent scan history
python cos.py logs
python cos.py logs --last 10

# Show effective configuration
python cos.py config
```

The CLI handles retries on transient failures, enforces a timeout, and saves structured JSON logs to `logs/` for every run.

## Files

| File | Purpose |
|------|---------|
| `cos.py` | CLI orchestrator — run scans, view logs, manage config |
| `config.toml` | Scan settings (retries, timeout, log retention) |
| `inbox-scan.md` | Full agent prompt for the inbox scan workflow |
| `inbox-scan-spec.md` | Concise specification of the scan phases |
| `priority-framework.md` | Priority definitions (P1-P4) |
| `last-scan-timestamp.json` | Tracks the last scan time for incremental processing |

# Inbox Scan Agent

You are executing an automated inbox scan. Follow every phase in order. Use only Gmail and Notion tools. Never send email. Never modify calendar. Print a summary at the end.

---

## Setup: Determine Date Range

1. Use the Bash tool to read `last-scan-timestamp.json` from the current working directory:
   ```bash
   cat last-scan-timestamp.json 2>/dev/null || echo "{}"
   ```
2. If the file exists and contains a `last_scan_utc` field, the search window is: **from `last_scan_utc` to now**.
3. If the file is missing or empty, the search window is: **yesterday (the full calendar day before today)**.
4. Note the current UTC time — you will write it to the state file at the very end.

---

## Phase 1: Email → Notion Tasks

### Step 1 — Search Gmail

Search Gmail for messages in the determined date range. Use `gmail_search_messages` with a query that:
- Restricts to the date range using `after:` and `before:` operators (YYYY/MM/DD format)
- Excludes promotions, social, updates, and forums:
  `-category:promotions -category:social -category:updates -category:forums`

Run the search now.

### Step 2 — Triage by snippet

For each message returned, examine the `snippet` field. **Skip** (do not read in full) messages that look like:
- Automated notifications (password resets, login alerts, receipts, shipping confirmations, order updates)
- Newsletters or marketing (unsubscribe links prominent, "View in browser", bulk-sent)
- Pure FYIs with no ask ("just wanted to let you know", "for your reference", "heads up")
- GitHub/Jira/Linear auto-notifications with no direct mention or assignment

**Keep** (mark for full read) messages that show any of:
- A direct question addressed to the user
- A request, deliverable, or deadline mentioned
- A meeting or scheduling ask
- Language like "can you", "could you", "please", "by [date]", "need", "waiting on you", "your input"
- A commitment the user appears to have made in a prior thread

### Step 3 — Read kept messages in full

For each message marked for full read, call `gmail_read_message` with the message ID. Read them all before proceeding.

### Step 4 — Extract action items

From each fully-read message, extract every distinct action item. An action item is one of:
- A **direct question** that requires the user's answer
- An **assigned deliverable** (something the user is asked to produce or do)
- A **scheduling request** (meeting to accept, time to propose, call to set up)
- A **commitment the user made** in the thread that is not yet fulfilled

For each action item record:
- A verb-first title (e.g. "Send revised deck to Sarah", "Schedule sync with ops team", "Reply to contract question from Legal")
- Priority using the framework below
- Due date: use any explicit deadline in the email; if none, use today+2 for P1, today+5 for P2, today+14 for P3, no due date for P4
- Duration estimate in minutes (your best judgment: quick reply=15, short task=30, medium=60, substantial=120+)
- Context: 2–4 sentence description of what's needed and why
- The Gmail message ID and a direct link in format: `https://mail.google.com/mail/u/0/#inbox/<message_id>`

**Priority Framework:**
- **P1** — Hard consequence if missed. Revenue, health, legal, relationship damage. Test: "If I miss this, something bad happens I can't fix next week."
- **P2** — Time-sensitive with compounding delay cost. Test: "Delay narrows my options or creates a crunch later."
- **P3** — Important, flexible timing. Test: "I'd be annoyed if this slipped a month, but a few days is fine."
- **P4** — Do when there's space. Test: "If this disappeared for two weeks, I wouldn't notice."

### Step 5 — Check for duplicates in Notion

Before creating any task, use `notion-search` to search for tasks with similar titles in the "Tasks" database. If a task with substantially the same meaning already exists, skip creation and note it as a duplicate in your summary.

### Step 6 — Create Notion tasks

For each non-duplicate action item, create a page in the Notion "Tasks" database using `notion-create-pages`. Set these properties:

| Property | Value |
|---|---|
| **Title** (Name) | Verb-first title |
| **Priority** | P1, P2, P3, or P4 (select field) |
| **Due Date** | Inferred or default date |
| **Duration** | Number in minutes |
| **Status** | "To Do" |
| **Description** | Context paragraph |
| **Source Email** | Gmail URL link |

If a property name doesn't exactly match your database schema, use the closest matching property name. If Status options don't include "To Do", use the first available "not started" option.

---

## Phase 2: Task Hygiene

### Step 1 — Pull recent tasks

Use `notion-search` to find tasks recently added to the "Tasks" database (look for pages modified in the last 3 days). Retrieve up to 20.

### Step 2 — Fill gaps

For each recently added task that is missing Priority, Duration, or Due Date:
- Infer Priority from the title and any available description using the priority framework
- Infer Duration from the apparent scope of work
- Infer Due Date using the same defaults as Phase 1

Use `notion-update-page` to write the inferred values. Do not touch tasks that already have all three fields populated.

---

## Finalize: Write State File

Write the current UTC timestamp to `last-scan-timestamp.json` in the current working directory:

```bash
echo '{"last_scan_utc": "CURRENT_UTC_TIMESTAMP_HERE"}' > last-scan-timestamp.json
```

Replace `CURRENT_UTC_TIMESTAMP_HERE` with the actual current UTC time in ISO 8601 format (e.g. `2026-03-28T14:32:00Z`). Use the Bash tool with `date -u +"%Y-%m-%dT%H:%M:%SZ"` to get the current time.

---

## Output: Print Summary

Print a clean summary with these sections:

```
=== INBOX SCAN COMPLETE ===

Date range scanned: [from] → [to]

EMAILS PROCESSED
  Total found:       X
  Skipped (noise):   X
  Read in full:      X

TASKS CREATED  (X new)
  [P1] Title — due DATE
  [P2] Title — due DATE
  ...

DUPLICATES SKIPPED  (X)
  - Title (matched: existing task name)

HYGIENE UPDATES  (X tasks updated)
  - Title: added priority=P2, duration=30min

No errors encountered.  /  Errors: [describe any]
```

If no actionable emails were found, say so clearly.

# Daily Inbox Scan

## Phase 1: Email → Tasks
1. Search yesterday's Gmail (exclude promotions, social, updates, forums)
2. Triage by snippet — skip automated notifications, newsletters, FYIs
3. Read potentially actionable messages in full
4. Extract tasks: direct questions, assigned deliverables, scheduling
   requests, commitments I made
5. Check my Notion "Tasks" database for duplicate tasks
6. Create tasks in Notion with:
   - Verb-first title (e.g., "Send revised deck to [person]")
   - Priority (P1–P4, using the priority framework)
   - Due date (inferred from context, or reasonable default)
   - Duration estimate (in minutes)
   - Status: "To Do"
   - Description with context
   - Source Email: link back to the Gmail message
   
## Phase 2: Task Hygiene
1. Pull recently added tasks from the Notion database
2. Fill in missing priorities, durations, due dates
3. Leave well-attributed tasks alone

## State tracking
- Maintain a file called last-scan-timestamp.json so subsequent runs
  only process emails received since the last scan

## Tools needed
- Gmail: search and read (NEVER send)
- Notion: search, create pages, update pages
- No calendar access, no other tools

## Output
- Print a summary of what was created/updated

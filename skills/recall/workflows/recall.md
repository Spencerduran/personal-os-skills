# Recall Workflow

Load context from vault memory - temporal queries use native JSONL files, topic queries use QMD search.

## Step 1: Classify Query

Parse the user's input after `/recall` and classify:

- **Graph** - starts with "graph": "graph last week", "graph yesterday", "graph today"
  -> Go to Step 2C
- **Temporal** - mentions time: "yesterday", "today", "last week", "this week", a date, "what was I doing", "session history"
  -> Go to Step 2A
- **Topic** - mentions a subject: "QMD video", "authentication", "lab content"
  -> Go to Step 2B
- **Both** - temporal + topic: "what did I do with QMD yesterday"
  -> Go to Step 2A first, then scan results for the topic

## Step 2A: Temporal Recall (Vault Markdown Files)

Run the recall-from-vault script from the skill's scripts directory:

```bash
python3 .claude/skills/recall/scripts/recall-from-vault.py list DATE_EXPR --vault $VAULT_DIR
```

Replace `DATE_EXPR` with the parsed date expression. Supported:
- `yesterday`, `today`
- `YYYY-MM-DD`
- `last monday` .. `last sunday`
- `this week`, `last week`
- `N days ago`, `last N days`

Options:
- `--min-msgs N` - filter noise (default: 3)
- `--vault PATH` - path to vault (auto-detected from $VAULT_DIR or CWD)

Present the table to the user. If they pick a session to expand:

```bash
python3 .claude/skills/recall/scripts/recall-from-vault.py expand SESSION_ID --vault $VAULT_DIR
```

This shows the full conversation from the synced Claude-Sessions markdown files. Works on any machine with vault access.

## Step 2B: Topic Recall (QMD BM25 with Query Expansion)

BM25 is keyword-based - it only finds exact word matches. The user's recall of a topic often uses different words than the session itself (e.g. "disk clean up" vs "large files on computer"). Fix: expand the query into 3-4 keyword variants covering synonyms and related phrasings.

**Step 2B.1: Expand query into variants.** Generate 3-4 alternative phrasings that someone might use for the same topic. Think: what other words describe this? Example:
- User says "disk clean up" -> variants: `"disk cleanup free space"`, `"large files storage"`, `"delete cache bloat GB"`, `"free up computer space"`

**Step 2B.2: Run ALL variants across ALL collections in parallel** (fast, ~0.3s each):

```bash
qmd search "VARIANT_1" -c sessions -n 5
qmd search "VARIANT_2" -c sessions -n 5
qmd search "VARIANT_3" -c sessions -n 5
qmd search "VARIANT_1" -c notes -n 5
qmd search "VARIANT_2" -c notes -n 5
qmd search "VARIANT_1" -c daily -n 3
```

Run sessions variants in parallel. Notes/daily can use fewer variants (prioritize sessions for recall).

**Step 2B.3: Deduplicate results** by document path. If same doc appears in multiple searches, keep the highest score. Present top 5 unique results.

## Step 3: Fetch Full Documents (Topic path only)

For the top 3 most relevant results across all collections:

**For session hits** (from `sessions` collection):
- The search result will have a `full_session` wikilink in its frontmatter
- Read that linked Claude-Sessions file directly for full conversation context
- Example: If you find `claude-sessions-qmd/2026-03-01-1352-d3b6ec64.md`, read `Claude-Sessions/2026-03-01-d3b6ec64.md`

**For notes/daily hits**:
- Read the file directly from vault using the path from search results
- Or use `qmd get` if you need excerpts:
  ```bash
  qmd get "qmd://collection/path/to/file.md" -l 50
  ```

The bidirectional wikilinks ensure you can always jump from search-optimized version → full context.

## Step 4: Present Structured Summary

**For temporal queries:** Present the session table and offer to expand any session.

**For topic queries:** Organize results by collection type:

**Sessions**
- What was worked on related to this topic
- Key dates and decisions
- Current status or next steps

**Notes**
- Relevant research findings
- Plans or proposals
- Content drafts

**Daily**
- Recent daily log entries mentioning this topic
- Timestamps and context

Keep this concise - it's context loading, not a full report.

## Step 5: Synthesize "One Thing"

After presenting recall results (temporal, topic, or graph), synthesize the single highest-leverage next action. This replaces generic "what would you like to work on?" with a concrete recommendation.

**How to pick the One Thing:**
1. Look at what has momentum - sessions with recent activity, things mid-flow
2. Look at what's blocked - removing a blocker unlocks downstream work
3. Look at what's closest to done - finishing > starting
4. Weigh urgency signals: deadlines in session titles, "blocked" status, time-sensitive content

**Format:** Bold line at the end of results:

> **One Thing: [specific, concrete action]**

**Good examples:**
- **One Thing: Finish the QMD video outline - sections 3-5 are drafted, just needs the closing CTA**
- **One Thing: Unblock the lab deploy - the DNS config is the only remaining blocker, everything else is ready**
- **One Thing: Record the video intro - the script and thumbnail are done, recording is the bottleneck**

**Bad examples (too generic):**
- "Continue working on the video"
- "Pick up where you left off"
- "Review recent progress"

If the recall results don't have enough signal to pick a clear One Thing (e.g. user just browsed old sessions with no active work), skip it and ask "What would you like to work on from here?" instead.

## Fallback: No Results Found

If no results are found:

```
No results found for "QUERY". Try:
- Different search terms
- Broader keywords / different date range
- --min-msgs 1 to include short sessions
```

## Step 2C: Graph Visualization

Strip "graph" prefix from query to get the date expression. Run:

```bash
python3 .claude/skills/recall/scripts/session-graph.py DATE_EXPR
```

Options:
- `--min-files N` - only show sessions touching N+ files (default: 2, use 5+ for cleaner graphs)
- `--min-msgs N` - filter noise (default: 3)
- `--all-projects` - scan all projects
- `-o PATH` - custom output path (default: /tmp/session-graph.html)
- `--no-open` - don't auto-open browser

Opens interactive HTML in browser. Session nodes colored by day, file nodes colored by folder.
Tell the user the node/edge counts and what to look for (clusters, shared files).

## Notes

- **Temporal queries** go through `recall-from-vault.py` (reads Claude-Sessions markdown, works cross-machine)
- **Graph queries** go through `session-graph.py` (NetworkX + pyvis) - currently JSONL-based, may need local files
- **Topic queries** use BM25 (`qmd search`) NOT hybrid (`qmd query`) - 53x faster
- Run all 3 collection searches in parallel to keep response time fast
- **Bidirectional links**: session search results have `full_session` wikilink to complete conversation
- **Cross-machine compatible**: All recall functions work from synced vault, no local JSONL needed
- If a result is truncated or you need more context, read the full Claude-Sessions file directly

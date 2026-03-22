# Cross-Machine Recall Architecture

## Overview

The recall system has been redesigned to work seamlessly across multiple machines by reading from synced Obsidian vault files instead of machine-local JSONL files.

## Architecture

### Two-Part Search System

**1. claude-sessions-qmd/** - Search-optimized (user messages only)
- Location: `~/vaults/claude_history/Notes/Projects/claude-sessions-qmd/`
- Purpose: Fast BM25 keyword search via QMD
- Content: User messages only (no assistant responses)
- Indexed by: `qmd collection add` → `sessions` collection
- Size: ~1,647 files

**2. Claude-Sessions/** - Full conversations (rich metadata)
- Location: `~/vaults/claude_history/Claude-Sessions/`
- Purpose: Complete session context with metadata
- Content: Full conversations (user + assistant messages)
- Metadata: status, tags, rating, comments, skills used, artifacts
- Size: ~1,824 files

### Bidirectional Wikilinks

Files are cross-linked for seamless navigation:

**claude-sessions-qmd → Claude-Sessions:**
```yaml
---
date: 2026-03-01
session_id: d3b6ec64-...
full_session: "[[Claude-Sessions/2026-03-01-d3b6ec64]]"
---
```

**Claude-Sessions → claude-sessions-qmd:**
```yaml
---
type: claude-session
date: 2026-03-01
session_id: d3b6ec64-...
search_optimized: "[[Notes/Projects/claude-sessions-qmd/2026-03-01-1352-d3b6ec64]]"
---
```

## Recall Workflows

### Temporal Recall ("yesterday", "last week")

**Command:**
```bash
python3 .claude/skills/recall/scripts/recall-from-vault.py list DATE_EXPR --vault $VAULT_DIR
```

**Process:**
1. Scans `Claude-Sessions/` markdown files by date
2. Shows table: time, message count, first message
3. User selects session to expand
4. Reads full conversation from markdown

**Benefits:**
- ✅ Works on any machine with vault access
- ✅ No local JSONL files needed
- ✅ Synced via Obsidian

### Topic Recall ("disk cleanup", "authentication")

**Command:**
```bash
qmd search "QUERY" -c sessions -n 5
```

**Process:**
1. BM25 search on `claude-sessions-qmd` collection (user messages)
2. Results include `full_session` wikilink in frontmatter
3. Read linked `Claude-Sessions/` file for full context
4. Present structured summary with conversation details

**Query Expansion (recommended):**
```bash
# Generate 3-4 keyword variants for better recall
qmd search "disk cleanup free space" -c sessions -n 5
qmd search "large files storage" -c sessions -n 5
qmd search "delete cache bloat GB" -c sessions -n 5
```

### Graph Recall ("graph yesterday")

**Status:** Currently uses JSONL files (machine-local)
**Future:** Could be ported to read from vault markdown

## Setup Instructions

### 1. Convert Historical Sessions

If you have Claude Desktop/Web export:

```bash
python3 skills/sync-claude-sessions/scripts/import-claude-desktop.py \
  ~/Downloads/conversations.json \
  --output ~/vaults/claude_history
```

### 2. Add Bidirectional Links

```bash
python3 skills/recall/scripts/add-bidirectional-links.py \
  --vault ~/vaults/claude_history
```

### 3. Set Up QMD Collections

```bash
cd ~/vaults/claude_history

# Index search-optimized sessions
qmd collection add Notes/Projects/claude-sessions-qmd --name sessions

# Index general notes
qmd collection add Notes --name notes

# Verify
qmd collection list
```

### 4. Test Recall

```bash
# Temporal recall
python3 ~/.claude/skills/recall/scripts/recall-from-vault.py list yesterday --vault ~/vaults/claude_history

# Topic recall
qmd search "your topic here" -c sessions -n 5
```

## Scripts Reference

### New Scripts (Cross-Machine Compatible)

**recall-from-vault.py**
- Temporal queries from vault markdown
- Session expansion from vault markdown
- No JSONL dependency

**import-claude-desktop.py**
- Converts conversations.json → Claude-Sessions/
- Adds search_optimized wikilinks
- One-time migration

**add-bidirectional-links.py**
- Adds full_session links to claude-sessions-qmd files
- Links to corresponding Claude-Sessions files
- One-time setup

### Updated Scripts

**sync-claude-sessions (claude-sessions)**
- Now adds `search_optimized` wikilink to frontmatter
- Automatically finds matching qmd files
- Preserves links across syncs

### Legacy Scripts (JSONL-Based)

**recall-day.py** - Original temporal recall (requires local JSONL)
**session-graph.py** - Graph visualization (requires local JSONL)
**extract-sessions.py** - JSONL → qmd conversion (one-time use)

## Benefits

### ✅ Cross-Machine Compatible
- Works on any machine with vault access
- No need to sync JSONL files between machines
- Obsidian handles file synchronization

### ✅ Bidirectional Navigation
- Search finds user messages → click to full context
- Browsing full sessions → click to search-optimized version
- Obsidian backlinks panel shows connections

### ✅ Portable History
- 1,647 sessions from Sept 2024 - present
- Full conversation context preserved
- Rich metadata (tags, status, ratings, comments)

### ✅ Fast Search
- BM25 keyword search (no embeddings needed)
- Parallel searches across collections
- Query expansion for better recall

## File Naming Conventions

**claude-sessions-qmd:**
```
2026-03-01-1352-d3b6ec64.md
└─┬─┘ └─┬─┘ └───┬───┘
 date  time  session_id (8 chars)
```

**Claude-Sessions:**
```
2026-03-01-d3b6ec64.md
└─┬─┘ └───┬───┘
 date  session_id (8 chars)
```

## QMD Collections

**sessions** → `Notes/Projects/claude-sessions-qmd/`
- User messages only
- Optimized for search
- 1,647 files indexed

**notes** → `Notes/`
- General vault notes
- Research, plans, drafts
- Indexed for topic search

**daily** (optional) → Daily notes folder
- Daily logs
- Time-coded entries

## Maintenance

### Sync New Claude Code Sessions

```bash
# From any project directory
cd ~/vaults/claude_history
python3 ~/.claude/skills/sync-claude-sessions/scripts/claude-sessions sync
```

### Update QMD Index

```bash
cd ~/vaults/claude_history
qmd update
```

### Regenerate Wikilinks (if needed)

```bash
python3 ~/.claude/skills/recall/scripts/add-bidirectional-links.py \
  --vault ~/vaults/claude_history
```

## Troubleshooting

**"No sessions found" in temporal recall:**
- Check vault path is correct
- Verify Claude-Sessions/ directory exists
- Check date range (use `--min-msgs 1` to see all)

**"No results found" in topic recall:**
- Run `qmd collection list` to verify indexing
- Try broader keywords or query expansion
- Check collection paths are correct

**Wikilinks not working:**
- Run add-bidirectional-links.py again
- Check file naming matches (8-char session IDs)
- Verify both directories exist

## Migration Checklist

- [ ] Export Claude Desktop/Web data (conversations.json)
- [ ] Run import-claude-desktop.py
- [ ] Run add-bidirectional-links.py
- [ ] Set up QMD collections (sessions, notes, daily)
- [ ] Test temporal recall
- [ ] Test topic recall
- [ ] Verify wikilinks work in Obsidian
- [ ] Set up sync on other machines
- [ ] Test recall from second machine

## Future Enhancements

- [ ] Port session-graph.py to read from vault markdown
- [ ] Add semantic search option (requires embeddings)
- [ ] Auto-sync hooks for new sessions
- [ ] Cross-vault search (multiple projects)
- [ ] Session tagging automation
- [ ] Status workflow automation

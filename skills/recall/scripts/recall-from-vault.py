#!/usr/bin/env python3
"""Recall sessions by date from Claude-Sessions markdown files (cross-machine compatible).

Usage:
    recall-from-vault.py list DATE_EXPR [--vault PATH] [--min-msgs N]
    recall-from-vault.py expand SESSION_ID [--vault PATH] [--max-msgs N]

DATE_EXPR examples: yesterday, today, 2026-02-25, "last tuesday", "this week",
                    "last week", "3 days ago", "last 3 days"

Reads from synced Claude-Sessions/ markdown files instead of local JSONL files.
Works on any machine with access to the vault.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DAY_NAMES = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}


def detect_vault_dir():
    """Auto-detect Obsidian vault from VAULT_DIR env var or by walking up from CWD."""
    if os.environ.get("VAULT_DIR"):
        return Path(os.environ["VAULT_DIR"])
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".obsidian").is_dir():
            return parent
    return None


def parse_frontmatter(content: str) -> dict:
    """Extract frontmatter from markdown."""
    if not content.startswith('---'):
        return {}

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}

    fm_block = parts[1].strip()
    fm_dict = {}

    for line in fm_block.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"')
            fm_dict[key] = value

    return fm_dict


def parse_date_expr(expr: str) -> tuple[datetime, datetime]:
    """Parse a date expression into (start, end) date range (UTC, day boundaries)."""
    expr = expr.strip().lower()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if expr == 'today':
        return today_start, today_start + timedelta(days=1)

    if expr == 'yesterday':
        start = today_start - timedelta(days=1)
        return start, today_start

    # YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', expr)
    if m:
        d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        return d, d + timedelta(days=1)

    # "N days ago"
    m = re.match(r'^(\d+)\s+days?\s+ago$', expr)
    if m:
        n = int(m.group(1))
        start = today_start - timedelta(days=n)
        return start, start + timedelta(days=1)

    # "last N days"
    m = re.match(r'^last\s+(\d+)\s+days?$', expr)
    if m:
        n = int(m.group(1))
        start = today_start - timedelta(days=n)
        return start, today_start + timedelta(days=1)

    # "this week" (Monday-based)
    if expr == 'this week':
        monday = today_start - timedelta(days=today_start.weekday())
        return monday, today_start + timedelta(days=1)

    # "last week"
    if expr == 'last week':
        this_monday = today_start - timedelta(days=today_start.weekday())
        last_monday = this_monday - timedelta(days=7)
        return last_monday, this_monday

    # "last monday" .. "last sunday"
    m = re.match(r'^last\s+(\w+)$', expr)
    if m and m.group(1) in DAY_NAMES:
        target_dow = DAY_NAMES[m.group(1)]
        current_dow = today_start.weekday()
        days_back = (current_dow - target_dow) % 7
        if days_back == 0:
            days_back = 7
        start = today_start - timedelta(days=days_back)
        return start, start + timedelta(days=1)

    print(f"Error: Can't parse date expression: '{expr}'", file=sys.stderr)
    print("Supported: today, yesterday, YYYY-MM-DD, 'N days ago', 'last N days',", file=sys.stderr)
    print("           'this week', 'last week', 'last monday'...'last sunday'", file=sys.stderr)
    sys.exit(1)


def scan_session_file(filepath: Path) -> dict | None:
    """Extract metadata from Claude-Sessions markdown file."""
    try:
        content = filepath.read_text()
        fm = parse_frontmatter(content)

        if not fm:
            return None

        # Parse date
        date_str = fm.get('date', '')
        if not date_str:
            return None

        try:
            start_time = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

        session_id = fm.get('session_id', filepath.stem)
        title = fm.get('title', 'Untitled')
        messages = int(fm.get('messages', 0))
        file_size = filepath.stat().st_size

        return {
            'session_id': session_id,
            'start_time': start_time,
            'user_msg_count': messages,  # Approximate - full count includes assistant
            'file_size': file_size,
            'title': title,
            'filepath': str(filepath),
        }
    except Exception:
        return None


def format_size(size_bytes: int) -> str:
    """Format file size human-readable."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def cmd_list(args):
    """List sessions for a date range from Claude-Sessions markdown files."""
    vault_dir = args.vault if args.vault else detect_vault_dir()
    if not vault_dir or not Path(vault_dir).exists():
        print("Error: Could not find vault directory. Use --vault PATH", file=sys.stderr)
        sys.exit(1)

    sessions_dir = Path(vault_dir) / "Claude-Sessions"
    if not sessions_dir.exists():
        print(f"Error: {sessions_dir} not found", file=sys.stderr)
        sys.exit(1)

    date_start, date_end = parse_date_expr(args.date_expr)

    sessions = []
    noise_count = 0

    for filepath in sessions_dir.glob("*.md"):
        meta = scan_session_file(filepath)
        if meta is None:
            continue

        # Filter by date range
        if meta['start_time'] < date_start or meta['start_time'] >= date_end:
            continue

        # Filter by message count (approximate)
        if meta['user_msg_count'] < args.min_msgs:
            noise_count += 1
            continue

        sessions.append(meta)

    sessions.sort(key=lambda s: s['start_time'])

    # Format date range for header
    if date_end - date_start <= timedelta(days=1):
        header_date = date_start.strftime('%Y-%m-%d (%A)')
    else:
        header_date = f"{date_start.strftime('%Y-%m-%d')} to {(date_end - timedelta(days=1)).strftime('%Y-%m-%d')}"

    print(f"\nSessions for {header_date}\n")

    if not sessions:
        print("No sessions found.")
        if noise_count:
            print(f"({noise_count} filtered as noise, try --min-msgs 1)")
        return

    # Print table
    print(f" {'#':>2}  {'Time':5}  {'Msgs':>4}  {'Size':>6}  First Message")
    print(f" {'--':>2}  {'-----':5}  {'----':>4}  {'------':>6}  -------------")

    for i, s in enumerate(sessions, 1):
        time_str = s['start_time'].strftime('%H:%M')
        size_str = format_size(s['file_size'])
        title = s['title'][:60]
        sid_short = s['session_id'][:8]

        print(f" {i:2d}  {time_str}  {s['user_msg_count']:4d}  {size_str:>6}  {title}")
        print(f"     Session ID: {sid_short}")


def cmd_expand(args):
    """Show full conversation for a session ID."""
    vault_dir = args.vault if args.vault else detect_vault_dir()
    if not vault_dir or not Path(vault_dir).exists():
        print("Error: Could not find vault directory. Use --vault PATH", file=sys.stderr)
        sys.exit(1)

    sessions_dir = Path(vault_dir) / "Claude-Sessions"
    if not sessions_dir.exists():
        print(f"Error: {sessions_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Find matching file by session ID
    target_id = args.session_id.lower()
    session_file = None

    for filepath in sessions_dir.glob(f"*-{target_id[:8]}*.md"):
        session_file = filepath
        break

    if not session_file:
        # Try full UUID match in frontmatter
        for filepath in sessions_dir.glob("*.md"):
            content = filepath.read_text()
            if target_id in content.lower():
                session_file = filepath
                break

    if not session_file:
        print(f"Error: Session {target_id} not found in {sessions_dir}", file=sys.stderr)
        sys.exit(1)

    # Read and display
    content = session_file.read_text()
    fm = parse_frontmatter(content)

    print(f"\nSession: {fm.get('title', 'Untitled')}")
    print(f"Date: {fm.get('date', 'unknown')}")
    print(f"ID: {fm.get('session_id', 'unknown')[:16]}...")
    print(f"Messages: {fm.get('messages', 'unknown')}")
    print("=" * 80)
    print()

    # Extract conversation section
    parts = content.split('## Conversation', 1)
    if len(parts) > 1:
        conversation = parts[1].strip()

        # Limit messages if requested
        if args.max_msgs:
            lines = conversation.split('\n')
            msg_count = 0
            output_lines = []
            for line in lines:
                if line.startswith('### User') or line.startswith('### Assistant'):
                    msg_count += 1
                    if msg_count > args.max_msgs:
                        output_lines.append(f"\n... (truncated, {args.max_msgs} messages shown) ...")
                        break
                output_lines.append(line)
            print('\n'.join(output_lines))
        else:
            print(conversation)
    else:
        print("(No conversation section found)")


def main():
    parser = argparse.ArgumentParser(description='Recall sessions from vault markdown files')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # List command
    list_parser = subparsers.add_parser('list', help='List sessions for a date range')
    list_parser.add_argument('date_expr', help='Date expression (e.g., yesterday, today, last week)')
    list_parser.add_argument('--vault', help='Path to vault directory')
    list_parser.add_argument('--min-msgs', type=int, default=3, help='Minimum messages to show (default: 3)')

    # Expand command
    expand_parser = subparsers.add_parser('expand', help='Expand a session to show full conversation')
    expand_parser.add_argument('session_id', help='Session ID (short or full UUID)')
    expand_parser.add_argument('--vault', help='Path to vault directory')
    expand_parser.add_argument('--max-msgs', type=int, help='Maximum messages to show')

    args = parser.parse_args()

    if args.command == 'list':
        cmd_list(args)
    elif args.command == 'expand':
        cmd_expand(args)


if __name__ == '__main__':
    main()

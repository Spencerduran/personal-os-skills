#!/usr/bin/env python3
"""Convert Claude Desktop/Web conversations.json to Claude-Sessions markdown format.

Usage:
    python3 import-claude-desktop.py <conversations.json> --output <vault-path>

Creates rich session markdown files with full conversations and bidirectional wikilinks
to claude-sessions-qmd files.
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path


def clean_title(title: str) -> str:
    """Clean title for use in frontmatter."""
    if not title or not title.strip():
        return ""
    # Remove quotes and escape special chars
    title = title.strip().replace('"', '\\"')
    # Truncate if too long
    if len(title) > 200:
        title = title[:197] + "..."
    return title


def derive_title_from_messages(messages: list) -> str:
    """Derive a title from the first user message if name is empty."""
    for msg in messages:
        if msg.get('sender') == 'human':
            text = msg.get('text', '').strip()
            if not text and msg.get('content'):
                # Try to get text from content array
                for content in msg['content']:
                    if content.get('type') == 'text':
                        text = content.get('text', '').strip()
                        if text:
                            break
            if text and len(text) > 10:
                # Take first line
                first_line = text.split('\n')[0].strip()
                if len(first_line) > 100:
                    first_line = first_line[:97] + "..."
                return first_line
    return "Untitled conversation"


def find_matching_qmd_file(session_id: str, qmd_dir: Path) -> str | None:
    """Find matching claude-sessions-qmd file by session ID."""
    if not qmd_dir.exists():
        return None

    # Look for files with this session ID (last 8 chars)
    short_id = session_id[:8]
    for file in qmd_dir.glob(f"*-{short_id}.md"):
        return file.stem  # Return filename without .md
    return None


def format_timestamp(ts_str: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return ts_str


def convert_conversation(conv: dict, qmd_dir: Path) -> dict:
    """Convert a conversation to Claude-Sessions markdown format."""
    session_id = conv['uuid']
    short_id = session_id[:8]

    # Get timestamps
    created_at = conv['created_at']
    updated_at = conv.get('updated_at', created_at)

    try:
        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H%M')
    except:
        date_str = 'unknown'
        time_str = '0000'

    # Get title
    title = conv.get('name', '').strip()
    if not title:
        title = derive_title_from_messages(conv.get('chat_messages', []))
    title = clean_title(title)

    # Get summary
    summary = conv.get('summary', '').strip()

    # Count messages
    messages = conv.get('chat_messages', [])
    message_count = len(messages)

    # Find matching QMD file
    qmd_file = find_matching_qmd_file(session_id, qmd_dir)

    # Build frontmatter
    frontmatter = [
        '---',
        'type: claude-session',
        f'date: {date_str}',
        f'session_id: {session_id}',
        f'title: "{title}"',
    ]

    if summary:
        frontmatter.append(f'summary: "{clean_title(summary)}"')

    frontmatter.extend([
        f'messages: {message_count}',
        f'last_activity: {updated_at}',
        'status: active',
        'tags: []',
        'rating: null',
        'comments: ""',
        'projects: []',
        'source: claude-desktop',
    ])

    if qmd_file:
        frontmatter.append(f'search_optimized: "[[Notes/Projects/claude-sessions-qmd/{qmd_file}]]"')

    frontmatter.append('---')

    # Build content
    content = [
        '',
        f'# {title}',
        '',
    ]

    # Add link to search-optimized version if exists
    if qmd_file:
        content.extend([
            '**Quick Links:**',
            f'- Search-optimized version: [[Notes/Projects/claude-sessions-qmd/{qmd_file}]]',
            '',
        ])

    content.extend([
        '## My Notes',
        '',
        '<!-- Add your notes here. This section is preserved across syncs. -->',
        '',
        '## Conversation',
        '',
    ])

    # Add conversation
    for msg in messages:
        sender = msg.get('sender', 'unknown')
        sender_label = 'User' if sender == 'human' else 'Assistant'

        # Get message text
        text = msg.get('text', '').strip()
        if not text and msg.get('content'):
            # Try to extract from content array
            texts = []
            for content_block in msg['content']:
                if content_block.get('type') == 'text':
                    block_text = content_block.get('text', '').strip()
                    if block_text:
                        texts.append(block_text)
            text = '\n\n'.join(texts)

        if not text:
            text = '(empty message)'

        # Get timestamp
        msg_time = msg.get('created_at', '')
        time_label = format_timestamp(msg_time) if msg_time else ''

        content.append(f'### {sender_label}')
        if time_label:
            content.append(f'*{time_label}*')
        content.append('')
        content.append(text)
        content.append('')

    # Create filename
    filename = f"{date_str}-{short_id}.md"

    return {
        'filename': filename,
        'content': '\n'.join(frontmatter + content),
        'session_id': session_id,
        'date': date_str,
    }


def main():
    parser = argparse.ArgumentParser(description='Import Claude Desktop conversations to Claude-Sessions')
    parser.add_argument('input', help='Path to conversations.json file')
    parser.add_argument('--output', required=True, help='Path to vault directory')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be created without writing files')
    args = parser.parse_args()

    input_path = Path(args.input)
    vault_path = Path(args.output)
    output_dir = vault_path / 'Claude-Sessions'
    qmd_dir = vault_path / 'Notes' / 'Projects' / 'claude-sessions-qmd'

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        return 1

    if not vault_path.exists():
        print(f"Error: Vault directory {vault_path} not found")
        return 1

    # Load conversations
    print(f"Loading conversations from {input_path}...")
    with open(input_path) as f:
        conversations = json.load(f)

    print(f"Found {len(conversations)} conversations")

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Convert each conversation
    created = 0
    skipped = 0

    for conv in conversations:
        result = convert_conversation(conv, qmd_dir)
        output_path = output_dir / result['filename']

        if output_path.exists():
            skipped += 1
            continue

        if args.dry_run:
            print(f"Would create: {result['filename']}")
            created += 1
        else:
            with open(output_path, 'w') as f:
                f.write(result['content'])
            created += 1
            if created % 100 == 0:
                print(f"Created {created} files...")

    print(f"\nComplete!")
    print(f"Created: {created} files")
    print(f"Skipped: {skipped} files (already exist)")
    if not args.dry_run:
        print(f"Output: {output_dir}")

    return 0


if __name__ == '__main__':
    exit(main())

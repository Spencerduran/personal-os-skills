#!/usr/bin/env python3
"""Add bidirectional wikilinks between claude-sessions-qmd and Claude-Sessions files.

Updates claude-sessions-qmd files to include a link to the full conversation in Claude-Sessions.
"""

import os
import re
from pathlib import Path


def extract_frontmatter(content: str) -> tuple[dict, str, str]:
    """Extract frontmatter, content, and raw frontmatter block from markdown."""
    if not content.startswith('---'):
        return {}, content, ''

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content, ''

    fm_block = parts[1].strip()
    fm_dict = {}

    for line in fm_block.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            fm_dict[key.strip()] = value.strip()

    return fm_dict, parts[2], fm_block


def find_full_session_file(session_id: str, sessions_dir: Path) -> str | None:
    """Find the Claude-Sessions file matching this session ID."""
    short_id = session_id[:8]

    # Look for files with this session ID
    for file in sessions_dir.glob(f"*-{short_id}.md"):
        return file.stem  # Return filename without .md

    return None


def add_link_to_qmd_file(file_path: Path, sessions_dir: Path) -> bool:
    """Add full_session wikilink to a claude-sessions-qmd file."""
    content = file_path.read_text()

    fm_dict, body, fm_block = extract_frontmatter(content)

    # Check if link already exists
    if 'full_session' in fm_dict:
        return False

    # Get session ID
    session_id = fm_dict.get('session_id', '')
    if not session_id:
        return False

    # Find matching full session file
    full_file = find_full_session_file(session_id, sessions_dir)
    if not full_file:
        return False

    # Add link to frontmatter
    new_fm = fm_block + f'\nfull_session: "[[Claude-Sessions/{full_file}]]"'

    # Rebuild file
    new_content = f"---\n{new_fm}\n---{body}"

    file_path.write_text(new_content)
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Add bidirectional links between session formats')
    parser.add_argument('--vault', required=True, help='Path to vault directory')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated')
    args = parser.parse_args()

    vault_path = Path(args.vault)
    qmd_dir = vault_path / 'Notes' / 'Projects' / 'claude-sessions-qmd'
    sessions_dir = vault_path / 'Claude-Sessions'

    if not qmd_dir.exists():
        print(f"Error: {qmd_dir} not found")
        return 1

    if not sessions_dir.exists():
        print(f"Error: {sessions_dir} not found")
        return 1

    print(f"Processing {qmd_dir}...")

    updated = 0
    skipped = 0
    no_match = 0

    for file_path in qmd_dir.glob('*.md'):
        if args.dry_run:
            # Check if it would update
            content = file_path.read_text()
            fm_dict, _, _ = extract_frontmatter(content)

            if 'full_session' in fm_dict:
                skipped += 1
                continue

            session_id = fm_dict.get('session_id', '')
            if session_id:
                full_file = find_full_session_file(session_id, sessions_dir)
                if full_file:
                    print(f"Would update: {file_path.name}")
                    updated += 1
                else:
                    no_match += 1
            else:
                skipped += 1
        else:
            result = add_link_to_qmd_file(file_path, sessions_dir)
            if result:
                updated += 1
                if updated % 100 == 0:
                    print(f"Updated {updated} files...")
            else:
                content = file_path.read_text()
                fm_dict, _, _ = extract_frontmatter(content)
                if 'full_session' in fm_dict:
                    skipped += 1
                else:
                    no_match += 1

    print(f"\nComplete!")
    print(f"Updated: {updated} files")
    print(f"Skipped: {skipped} files (already have links)")
    print(f"No match: {no_match} files (no corresponding full session)")

    return 0


if __name__ == '__main__':
    exit(main())

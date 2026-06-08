#!/usr/bin/env python3
"""
apply_patch.py — Read-only CLI for the update-patch framework.

This tool inspects the patches in `backend/patches/`. It NEVER:
  - touches `dashboard.db`
  - mutates source files
  - runs git commands
  - touches `docs/data/*` or pipeline output

Apply a patch by hand:
  1) Merge the patch branch on git.
  2) Run each migration SQL against `dashboard.db` manually.
  3) Update the patch's `manifest.json` (`applied_at`, `rollback_commit`).

Subcommands:
  list                  — list every patch folder + its declared version
  status                — show last applied patch + pending patches
  show <version>        — print manifest + rollback hint for one patch
  verify <version>      — sanity-check the patch folder (files_modified exist)

Exit code is 0 on success, 1 on any sanity-check failure.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PATCHES_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PATCHES_DIR.parent
REPO_ROOT = BACKEND_DIR.parent  # ../ (assumes patches live under backend/)


# ─────────────────────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────────────────────

def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert '1.2' → (1, 2) for sorting. Non-numeric pieces sort last."""
    out = []
    for part in v.split('.'):
        try:
            out.append(int(part))
        except ValueError:
            out.append(9999)
    return tuple(out)


def _is_patch_dir(p: Path) -> bool:
    """A directory is a patch folder if it contains a manifest.json."""
    return p.is_dir() and (p / 'manifest.json').exists()


def find_patches() -> list[Path]:
    """Return all patch folders sorted by version ascending."""
    if not PATCHES_DIR.exists():
        return []
    patches = [p for p in PATCHES_DIR.iterdir() if _is_patch_dir(p)]
    patches.sort(key=lambda p: _version_tuple(p.name))
    return patches


def load_manifest(patch_dir: Path) -> dict:
    """Load the manifest.json for a patch folder. Returns {} on failure."""
    mf = patch_dir / 'manifest.json'
    if not mf.exists():
        return {}
    try:
        with mf.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] Could not parse {mf}: {e}", file=sys.stderr)
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Subcommands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_list(_args: list[str]) -> int:
    """list — show every patch folder + declared version + applied status."""
    patches = find_patches()
    if not patches:
        print("(no patches found in backend/patches/)")
        return 0

    print(f"{'Version':<10} {'Status':<14} {'Name':<48} Audit refs")
    print("-" * 100)
    for p in patches:
        mf = load_manifest(p)
        version = mf.get('patch_version', p.name)
        applied_at = mf.get('applied_at', '').strip()
        status = 'applied' if applied_at else 'pending'
        name = (mf.get('name') or '')[:47]
        audit_refs = ','.join(mf.get('audit_refs', []) or [])
        print(f"{version:<10} {status:<14} {name:<48} {audit_refs}")
    return 0


def cmd_status(_args: list[str]) -> int:
    """status — last applied patch + currently pending patches."""
    patches = find_patches()
    if not patches:
        print("No patches available.")
        return 0

    applied = []
    pending = []
    for p in patches:
        mf = load_manifest(p)
        if mf.get('applied_at', '').strip():
            applied.append((mf.get('patch_version', p.name),
                            mf.get('applied_at'),
                            mf.get('name', '')))
        else:
            pending.append((mf.get('patch_version', p.name),
                            mf.get('name', '')))

    print("=== Applied ===")
    if applied:
        for v, ts, name in applied:
            print(f"  {v:<8} {ts:<22}  {name}")
        last = applied[-1]
        print(f"\nLast applied: {last[0]}  ({last[1]})")
    else:
        print("  (none)")

    print("\n=== Pending ===")
    if pending:
        for v, name in pending:
            print(f"  {v:<8}  {name}")
    else:
        print("  (none)")
    return 0


def cmd_show(args: list[str]) -> int:
    """show <version> — print manifest + rollback git command hint."""
    if not args:
        print("Usage: apply_patch.py show <version>", file=sys.stderr)
        return 1
    version = args[0]
    target = PATCHES_DIR / version
    if not _is_patch_dir(target):
        print(f"Patch {version!r} not found at {target}", file=sys.stderr)
        return 1

    mf = load_manifest(target)
    print(f"Patch {mf.get('patch_version', version)} — {mf.get('name', '')}")
    print(f"  depends_on:      {mf.get('depends_on', [])}")
    print(f"  applied_at:      {mf.get('applied_at', '') or '(not applied)'}")
    print(f"  rollback_commit: {mf.get('rollback_commit', '') or '(unset)'}")
    print(f"  audit_refs:      {', '.join(mf.get('audit_refs', []) or [])}")

    print("\n  Files modified:")
    for path in mf.get('files_modified', []) or []:
        print(f"    {path}")
    print("  Files added:")
    for path in mf.get('files_added', []) or []:
        print(f"    {path}")

    migrations = mf.get('migrations', []) or []
    if migrations:
        print("\n  Migrations (apply in order, MANUALLY):")
        for m in migrations:
            print(f"    sqlite3 backend/dashboard.db < backend/patches/{version}/migrations/{m}")

    print("\n  Rollback hint:")
    rb = mf.get('rollback_commit', '').strip()
    if rb:
        print(f"    git revert -m 1 <merge-sha-of-patch-{version}>")
        print(f"    # rollback_commit (pre-patch HEAD): {rb}")
    else:
        print(f"    # rollback_commit not set — see {version}/rollback.md")

    notes = target / 'PATCH_NOTES.md'
    if notes.exists():
        print(f"\n  Full notes: {notes}")
    rb_doc = target / 'rollback.md'
    if rb_doc.exists():
        print(f"  Rollback doc: {rb_doc}")
    return 0


def cmd_verify(args: list[str]) -> int:
    """verify <version> — sanity-check files_modified exist; never edits anything."""
    if not args:
        print("Usage: apply_patch.py verify <version>", file=sys.stderr)
        return 1
    version = args[0]
    target = PATCHES_DIR / version
    if not _is_patch_dir(target):
        print(f"Patch {version!r} not found at {target}", file=sys.stderr)
        return 1

    mf = load_manifest(target)
    problems: list[str] = []

    declared_version = mf.get('patch_version', '').strip()
    if declared_version != target.name:
        problems.append(
            f"manifest patch_version {declared_version!r} != folder name {target.name!r}"
        )

    # files_modified must exist
    for rel in mf.get('files_modified', []) or []:
        abs_path = REPO_ROOT / rel
        if not abs_path.exists():
            problems.append(f"files_modified missing on disk: {rel}")

    # files_added must exist
    for rel in mf.get('files_added', []) or []:
        abs_path = REPO_ROOT / rel
        if not abs_path.exists():
            problems.append(f"files_added missing on disk: {rel}")

    # migrations listed must exist
    for m in mf.get('migrations', []) or []:
        mp = target / 'migrations' / m
        if not mp.exists():
            problems.append(f"migration missing: migrations/{m}")

    # depends_on patches must also exist as folders
    for dep in mf.get('depends_on', []) or []:
        dep_dir = PATCHES_DIR / dep
        if not _is_patch_dir(dep_dir):
            problems.append(f"declared dep {dep!r} not found at {dep_dir}")

    if problems:
        print(f"[VERIFY] Patch {version}: {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"[VERIFY] Patch {version}: OK")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

USAGE = """\
Usage: apply_patch.py <command> [args]

Commands:
  list                  list every patch folder + declared version
  status                show last applied patch + pending patches
  show <version>        print manifest + rollback hint
  verify <version>      sanity-check the patch folder

This tool is READ-ONLY. It does not run SQL, modify source files, or
touch the database.
"""


COMMANDS = {
    'list': cmd_list,
    'status': cmd_status,
    'show': cmd_show,
    'verify': cmd_verify,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ('-h', '--help'):
        print(USAGE)
        return 0
    cmd = argv[0]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd!r}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 1
    return COMMANDS[cmd](argv[1:])


if __name__ == '__main__':
    sys.exit(main())

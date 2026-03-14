"""
deploy_to_github.py — Sync static frontend assets from public/ into docs/

GitHub Pages serves files from the docs/ directory on the main branch.
This script is idempotent: safe to run repeatedly.

What it copies:
  Everything in public/ -> docs/  (excluding hidden files and node_modules)

What it does NOT touch:
  docs/data/         — managed by export_dashboard.py (preserved during sync)
"""

import shutil
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directories and patterns to exclude from the copy
_IGNORE = shutil.ignore_patterns(
    ".*",           # hidden files/dirs
    "node_modules", # npm artifacts
)


def main():
    public_dir = os.path.join(PROJECT_ROOT, "public")
    docs_dir = os.path.join(PROJECT_ROOT, "docs")

    if not os.path.isdir(public_dir):
        print("ERROR: public/ directory not found")
        return

    # Preserve docs/data/ (managed by export_dashboard.py)
    data_dir = os.path.join(docs_dir, "data")
    data_backup = None
    if os.path.isdir(data_dir):
        data_backup = data_dir + "_backup"
        if os.path.exists(data_backup):
            shutil.rmtree(data_backup)
        os.rename(data_dir, data_backup)

    # Sync public/ -> docs/ (full copytree with ignore patterns)
    shutil.copytree(public_dir, docs_dir, ignore=_IGNORE, dirs_exist_ok=True)

    # Restore docs/data/
    if data_backup and os.path.isdir(data_backup):
        if os.path.isdir(data_dir):
            shutil.rmtree(data_dir)
        os.rename(data_backup, data_dir)

    # Print what was copied
    copied = []
    for root, dirs, files in os.walk(public_dir):
        # Skip ignored dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for f in files:
            if not f.startswith("."):
                rel = os.path.relpath(os.path.join(root, f), public_dir)
                copied.append(rel)

    for rel in sorted(copied):
        print(f"Copied public/{rel} -> docs/{rel}")

    print(f"deploy_to_github.py: synced {len(copied)} files from public/ to docs/")


if __name__ == "__main__":
    main()

"""
deploy_to_github.py -- Sync static frontend assets from public/ into docs/

GitHub Pages serves files from the docs/ directory on the main branch.
This script is idempotent: safe to run repeatedly.

What it copies:
  public/index.html  -> docs/index.html
  public/404.html    -> docs/404.html
  public/js/*        -> docs/js/*

What it does NOT touch:
  docs/data/         -- managed by export_dashboard.py
"""

import shutil
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    public_dir = os.path.join(PROJECT_ROOT, "public")
    docs_dir = os.path.join(PROJECT_ROOT, "docs")

    if not os.path.isdir(public_dir):
        print("ERROR: public/ directory not found")
        sys.exit(1)

    os.makedirs(docs_dir, exist_ok=True)
    copied = []

    # Copy top-level files (html)
    for fname in os.listdir(public_dir):
        src = os.path.join(public_dir, fname)
        if os.path.isfile(src) and not fname.startswith("."):
            dst = os.path.join(docs_dir, fname)
            shutil.copy2(src, dst)
            copied.append(fname)

    # Copy js/ directory
    js_src = os.path.join(public_dir, "js")
    js_dst = os.path.join(docs_dir, "js")
    if os.path.isdir(js_src):
        os.makedirs(js_dst, exist_ok=True)
        for fname in os.listdir(js_src):
            src = os.path.join(js_src, fname)
            if os.path.isfile(src) and not fname.startswith("."):
                shutil.copy2(src, os.path.join(js_dst, fname))
                copied.append(os.path.join("js", fname))

    for rel in sorted(copied):
        print(f"  {rel}")

    print(f"deploy_to_github.py: synced {len(copied)} files from public/ to docs/")

    # Validate docs/index.html exists
    index_path = os.path.join(docs_dir, "index.html")
    if not os.path.isfile(index_path):
        print("ERROR: docs/index.html not found after deploy")
        sys.exit(1)

    # Validate docs/data/ has content
    data_dir = os.path.join(docs_dir, "data")
    if not os.path.isdir(data_dir):
        print("WARNING: docs/data/ missing -- run export_dashboard.py")
    else:
        json_count = len([f for f in os.listdir(data_dir) if f.endswith(".json")])
        if json_count < 5:
            print(f"WARNING: docs/data/ has only {json_count} JSON files -- expected 20+")
        else:
            print(f"  docs/data/: {json_count} JSON files OK")


if __name__ == "__main__":
    main()

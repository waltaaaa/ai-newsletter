"""
deploy_to_github.py — Copy static frontend assets from public/ into docs/

GitHub Pages serves files from the docs/ directory on the main branch.
This script is idempotent: safe to run repeatedly.

What it copies:
  public/index.html  -> docs/index.html
  public/404.html    -> docs/404.html
  public/js/         -> docs/js/   (shutil.copytree with dirs_exist_ok=True)

What it does NOT touch:
  docs/data/         — managed by export_dashboard.py
"""

import shutil
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    public_dir = os.path.join(PROJECT_ROOT, "public")
    docs_dir = os.path.join(PROJECT_ROOT, "docs")

    # Ensure docs/ exists (docs/data/ may already be there from export_dashboard.py)
    os.makedirs(docs_dir, exist_ok=True)

    # Copy individual HTML files
    for filename in ("index.html", "404.html"):
        src = os.path.join(public_dir, filename)
        dst = os.path.join(docs_dir, filename)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"Copied public/{filename} -> docs/{filename}")
        else:
            print(f"WARNING: public/{filename} not found, skipping")

    # Copy js/ directory (dirs_exist_ok keeps existing files in place)
    src_js = os.path.join(public_dir, "js")
    dst_js = os.path.join(docs_dir, "js")
    if os.path.isdir(src_js):
        shutil.copytree(src_js, dst_js, dirs_exist_ok=True)
        js_files = os.listdir(src_js)
        for f in js_files:
            print(f"Copied public/js/{f} -> docs/js/{f}")
    else:
        print("WARNING: public/js/ not found, skipping")

    print("deploy_to_github.py: done")


if __name__ == "__main__":
    main()

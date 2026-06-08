# Update-Patch Framework

This directory holds the **update-patch framework** for The Lagging Indicator
backend. A patch is a self-contained, dated, semver-numbered bundle of code
changes, schema migrations, and operator notes that ships together as one
logical fix-set.

The framework is intentionally lightweight: every patch lives in its own
folder, every patch carries its own manifest + rollback instructions, and the
companion CLI (`apply_patch.py`) is **informational only** — it never mutates
the database or the working tree. Patches are applied via plain git commits
on a dedicated branch; the manifest exists so future operators can answer
"what changed in 1.4? when? how do I roll it back?" without spelunking the
git log.

---

## Directory layout

```
backend/patches/
├── README.md                  # this file
├── apply_patch.py             # CLI — list / status / rollback hints
├── PATCH_TEMPLATE/            # skeleton to copy when starting a new patch
│   ├── PATCH_NOTES.md.tmpl
│   ├── manifest.json.tmpl
│   └── rollback.md.tmpl
├── 1.2/                       # first formal patch
│   ├── PATCH_NOTES.md
│   ├── manifest.json
│   ├── rollback.md
│   └── migrations/
│       ├── 001_*.sql
│       └── 002_*.sql
├── 1.3/                       # next patch — created from PATCH_TEMPLATE
└── ...
```

Code changes themselves live in `backend/` next to the rest of the source.
The patch folder is the **dossier** — what was changed, why, how to verify,
how to roll back.

---

## Semver convention

Patches use `MAJOR.MINOR` (no PATCH-level micro releases — the unit of work
is the patch itself).

| Bump      | When                                                                                                  |
|-----------|-------------------------------------------------------------------------------------------------------|
| **MINOR** | Non-breaking fixes, monitoring additions, new optional tables, refactors that preserve external API.  |
| **MAJOR** | Breaking changes to the schema (column drop / rename), pipeline contract changes (phase ordering, JSON output shape), or any change that requires coordinated frontend/backend deploy. |

The current MAJOR is `1`. Patches in this series: `1.0` (implicit baseline),
`1.1`, `1.2`, `1.3`, … When the next breaking change arrives, bump to `2.0`.

---

## Creating patch X.Y

```bash
cd /c/AI_newsletter/backend
cp -r patches/PATCH_TEMPLATE patches/X.Y
cd patches/X.Y
mv PATCH_NOTES.md.tmpl PATCH_NOTES.md
mv manifest.json.tmpl  manifest.json
mv rollback.md.tmpl    rollback.md
mkdir -p migrations
```

Then:

1. Create branch `patch-X.Y` from current `main` HEAD.
2. Implement each fix as one commit on that branch.
3. Fill in `manifest.json`:
   - `patch_version`: `"X.Y"`
   - `name`: short human label
   - `depends_on`: `["X.(Y-1)"]` (the prior patch — establishes ordering)
   - `files_modified` / `files_added`: list of touched paths
   - `migrations`: ordered list of `.sql` filenames in `migrations/`
   - `audit_refs`: which `PIPELINE_AUDIT.md` finding IDs each fix addresses
4. Fill in `PATCH_NOTES.md` per the template sections.
5. Fill in `rollback.md` with the specific revert procedure.
6. Final commit: `docs(patch-X.Y): finalize patch notes + manifest + migrations`.
7. After merge, fill `applied_at` (ISO8601) and `rollback_commit` (the
   pre-patch SHA on `main`) in `manifest.json`.

---

## Manifest schema

```json
{
  "patch_version": "1.2",
  "name": "audit fixes — discovery, monitoring, decay, alerts",
  "applied_at": "2026-06-08T17:23:14Z",
  "depends_on": ["1.1"],
  "files_modified": [
    "backend/project_sync.py",
    "backend/phases/finalize.py"
  ],
  "files_added": [
    "backend/rss_feed_health.py"
  ],
  "migrations": [
    "001_backfill_status_enum.sql",
    "002_weekly_briefings_schema.sql"
  ],
  "rollback_commit": "72beb2b7930a7cdd75810b05cf70fc1dd5d49375",
  "audit_refs": ["D-2", "D-4", "M-2", "M-3", "M-4", "M-5", "M-7", "M-8", "M-9"],
  "tests": []
}
```

Field-by-field:

- `patch_version` — semver, must match the directory name.
- `name` — operator-readable label.
- `applied_at` — ISO8601 UTC timestamp; left blank until the patch is merged.
- `depends_on` — list of prior patch versions this patch assumes are applied.
  Establishes a deterministic apply order. First patch in a series has `[]`.
- `files_modified` / `files_added` — every source file touched. Used by
  `apply_patch.py` to verify the working tree matches the manifest.
- `migrations` — ordered list of `.sql` filenames in this patch's
  `migrations/` folder. Filenames sort lexicographically (`001_*`, `002_*`)
  to keep apply order deterministic. **Patches do not run SQL
  automatically** — the operator applies migrations manually after reviewing
  the patch.
- `rollback_commit` — the git SHA of `main` immediately before the patch
  was merged. Used by `apply_patch.py rollback`.
- `audit_refs` — back-references into `PIPELINE_AUDIT.md` (or successor
  audit docs). Lets future readers trace each fix to its motivating finding.
- `tests` — paths to test files added with this patch. Empty if no tests
  shipped.

---

## Apply procedure

The framework does **not** auto-apply patches. Applying a patch is a
manual git operation:

```bash
# 1. Pull the patch branch
git fetch
git checkout patch-X.Y
git rebase main           # resolve conflicts if any
git checkout main
git merge --no-ff patch-X.Y

# 2. Apply migrations in order (one at a time, review between each)
sqlite3 backend/dashboard.db < backend/patches/X.Y/migrations/001_*.sql
sqlite3 backend/dashboard.db < backend/patches/X.Y/migrations/002_*.sql
# ... etc

# 3. Verify (see PATCH_NOTES.md § Verification)

# 4. Record the apply
# Edit backend/patches/X.Y/manifest.json:
#   set "applied_at" to the current ISO8601 UTC time
#   set "rollback_commit" to `git rev-parse main~1` (pre-merge SHA)
git add backend/patches/X.Y/manifest.json
git commit -m "chore(patch-X.Y): record apply timestamp + rollback SHA"
```

The patch is now live.

---

## Rollback procedure

Code rollback is a single git revert; data rollback (the migration changes)
must be reasoned about per patch — see each patch's `rollback.md`.

```bash
# 1. Find the patch's merge commit
git log --merges --oneline | grep "patch-X.Y"
# → 5a8b9f1 Merge branch 'patch-X.Y'

# 2. Revert it
git revert -m 1 5a8b9f1

# 3. Read backend/patches/X.Y/rollback.md for any data-side undo SQL
# (usually "do nothing — migrations were additive" but check)
```

The dependency chain (`depends_on`) makes apply order deterministic. Rollback
is the inverse: you cannot roll back patch X.Y while X.Y+1 (which depends on
it) is still applied — first roll back the newer patch, then the older one.

---

## `apply_patch.py` — what it does and doesn't do

This CLI is **strictly read-only**.

```bash
python backend/patches/apply_patch.py list           # available patches
python backend/patches/apply_patch.py status         # last applied; pending
python backend/patches/apply_patch.py show X.Y       # manifest + rollback hint
python backend/patches/apply_patch.py verify X.Y     # check files_modified exist
```

It will **never**:

- Run SQL against `dashboard.db`
- Modify source files
- Run `git` commands
- Touch `docs/data/*` or any pipeline output

If you want destructive behaviour, do it by hand with explicit commands. The
patches framework treats the operator as the final apply gate.

---

## File-touching policy

Patches edit source files in `backend/` directly — they are not text-patch
files (no `.diff`/`.patch` payloads). The folder is a **record** of the
change, not the change itself. Git is the source of truth for the actual
code delta.

Exception: if a patch needs to ship a one-off operator script (e.g. a
backfill, a sanity-check), it lives under `patches/X.Y/scripts/` and is
**never** invoked by the running pipeline.

---

## Concurrent-work safety

When a patch is being authored while the weekly pipeline is in flight:

- Do not touch `dashboard.db`, `dashboard.db-wal`, `dashboard.db-shm`.
- Do not touch `backend/docs/data/*`.
- Do not touch `backend/.claude/skills/*` (the conductor reads these).
- Do not run the pipeline scripts (`update_dashboard.py`, validator, exporter).
- Source files in `backend/` that the pipeline has already imported are safe
  to edit — Python caches modules at import time.

This concurrent-work rule is enforced by convention, not by the framework.

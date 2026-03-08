# CONVENTIONS.md — Code Style & Patterns

## Language Style

### Python
- **Version:** 3.12+ (modern union types `str | None`, type hints throughout)
- **Indentation:** 4 spaces
- **Line length:** No strict limit, practical ~120 chars
- **Quotes:** Single quotes for strings, triple-quoted docstrings
- **Encoding:** `sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)` at module top

### Naming
- **Functions:** `snake_case` — `fetch_primary_indicators()`, `run_google_news_search()`
- **Constants:** `UPPER_CASE` — `SONNET_MODEL`, `ELIGIBLE_STATUSES`, `NAICS_MAP`
- **Private helpers:** `_underscore_prefix` — `_fmt_period()`, `_statcan_wds()`
- **Classes:** `PascalCase` — `_GdeltDocPatched`, `TavilyClient`
- **Files:** `snake_case.py` — descriptive, matches primary function
- **Config keys:** `snake_case` in JSON, `UPPER_CASE` in Python

### Imports
Standard organization (not enforced by linter):
```python
import sys                    # stdlib
import firebase_admin         # third-party
from project_sync import ...  # local modules
```

Optional imports with feature flags:
```python
try:
    from tavily import TavilyClient as _TavilyClient
    _HAS_TAVILY = True
except ImportError:
    _HAS_TAVILY = False
    print("[WARN] tavily-python not installed — Tavily Extract will be skipped")
```

## Function Patterns

### Standard function shape
```python
def fetch_something(param: str, limit: int = 100) -> list[dict]:
    """One-line docstring describing what it does."""
    # Implementation
    return results
```

- Type hints on parameters and return values
- Default arguments for optional params
- Single-line docstrings (triple-quoted)
- Functions typically 50-200 lines
- Comments only where logic isn't self-evident

### Factory pattern
`pipeline_config.py` → `make_project()` — builds standardized project dicts matching Firestore schema. All projects go through this factory.

### Normalization pattern
`norm_status()`, `norm_key()`, `normalize_project_type()` — convert raw strings to canonical forms using keyword matching.

### Inference pattern
`infer_naics()` — heuristic keyword matching to classify projects by NAICS code from name/sector text.

## Error Handling

### Try/except with logging
```python
try:
    result = await fetch_something()
except Exception as e:
    print(f"[WARN] fetch_something failed: {e}")
    result = []  # graceful degradation
```

- Specific exception types where possible
- `[WARN]` / `[ERROR]` / `[INFO]` prefix tags in print statements
- Graceful degradation (return empty list/dict, continue pipeline)
- Pipeline never crashes — partial results are acceptable

### Bail-out pattern
GDELT: after 3 consecutive failures, skips remaining searches rather than retrying.

### Optional dependency pattern
Tavily, Perplexity wrapped in try/except import with `_HAS_*` flags.

## Data Patterns

### Project schema enforcement
Every project requires: name, province, NAICS code, status, source_url, discovery_source. URL hard gate — no URL = no Firestore write.

### Evidence merge (never lose data)
During dedup, evidence arrays combine (append), never overwrite. Status never regresses — merge advances to highest status.

### Additive-only adaptive learning
System can add queries, keywords, feeds. NEVER removes existing ones.

### Confidence scoring
Calculated from evidence count, government source presence, verified value. Decays after 30 days without re-discovery.

## Configuration Patterns

### Environment variables via dotenv
```python
from dotenv import load_dotenv
load_dotenv()
MODEL = os.environ.get('MODEL_NAME', 'default-value')
```

### Feature flags
`*_ENABLED` pattern: `GEMINI_SEARCH_ENABLED`, `PERPLEXITY_ENABLED`, `WAYBACK_ENABLED` — all read from `.env` with string-to-bool conversion.

### Central config module
`pipeline_config.py` is the single source of truth for: model routing, NAICS map, province thresholds, status normalization, dedup logic, project schema.

## Logging
- `print()` with prefix tags: `[INFO]`, `[WARN]`, `[ERROR]`, `[SKIP]`
- Python `logging` module used in some newer modules
- Line buffering enabled for real-time monitoring
- Audit logs written to dated text files: `citation_audit_2026-03-04.txt`, `seed_audit_2026-03-04.txt`

## Editorial Rules (enforced in AI prompts)
- **REPORTING ONLY** — no editorializing, no opinions, no recommendations
- No "should," "must," "hopefully," "unfortunately," "worrying," "promising"
- Every claim must cite a source or reference specific database data
- Conditional language for projections: "If rates hold, 23 projects would see..."

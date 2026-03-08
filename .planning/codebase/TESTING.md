# TESTING.md — Test Structure & Practices

## Framework
**Pure Python** — no pytest, no unittest framework. Manual test runners with `assert` statements and `if __name__ == "__main__":` execution.

## Test Files

### `test_dedup.py`
- Tests deduplication logic from `project_dedup.py` and `pipeline_config.py`
- Validates `norm_key()`, `fuzzy_match()`, evidence merge behavior
- Uses hardcoded fixture dicts simulating Firestore project documents

### `test_rss_filter.py`
- Tests the 6-layer RSS article filter
- Validates government bypass, dollar-value bypass, keyword matching, negative keywords
- Tests against sample article dicts

### `test_compound_queries.py`
- Validates 759 compound queries in `compound_queries_final.json`
- Checks query format, RSS URL generation, dedup across queries
- Schema compliance checks

### `test_brownfield_discovery.py`
- Tests brownfield project detection from `project_schema.py`
- Validates `is_brownfield()` and `normalize_project_type()` functions
- Tests against project type taxonomy (11 types)

## Testing Patterns

### Test function naming
```python
def test_norm_key_basic():
    assert norm_key("My Project", "Ontario") == "myproject__ontario"

def test_fuzzy_match_high_similarity():
    result = fuzzy_match("Trans Mountain", ["Trans Mountain Expansion"])
    assert result is not None
```

### Fixtures
Hardcoded dicts and constants — no fixture framework:
```python
SAMPLE_PROJECT = {
    "name": "Test Project",
    "province": "Ontario",
    "status": "Proposed",
    ...
}
```

### Live API tests
Some test files check for environment variables before calling live APIs:
```python
if not os.environ.get("TAVILY_API_KEY"):
    print("[SKIP] No API key — skipping live Tavily test")
    return
```

### Execution
```bash
python test_dedup.py
python test_rss_filter.py
python test_compound_queries.py
python test_brownfield_discovery.py
```

## Mocking
Not detected in existing tests. Tests use:
- Real data fixtures (hardcoded dicts)
- Live API calls with env var guards
- No mocking libraries imported

## Coverage

### What's tested
- Deduplication logic (norm_key, fuzzy_match, merge)
- RSS filter layers (bypass, keywords, negatives)
- Compound query format and schema
- Project type taxonomy and brownfield detection

### What's NOT tested
- Full pipeline end-to-end
- Claude/Gemini API integration
- Firestore read/write operations
- RSS feed fetching and parsing
- Government registry scrapers
- Market data collection
- Briefing generation
- PDF/DOCX export
- Frontend functionality
- Error handling / recovery paths
- Confidence scoring and decay

## CI/CD
No automated test pipeline. Tests are run manually. No coverage enforcement or thresholds.

## Quality Audits (separate from tests)
- `citation_audit.py` — Verifies source URLs, detects link rot, checks Wayback archives
- `coverage_audit.py` — Measures discovery coverage across tiers
- `quality_report.py` — Pipeline quality metrics
- `dedup_audit.py` — Verifies dedup accuracy
- Audit logs written to dated `.txt` files in project root

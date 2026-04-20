# Self-Check Template — producer skills

Every producing tldr-* skill (researchers, analysts, writers, charts, visualizer, assembler, data-refresh, data-gap) MUST run this self-check block on its output BEFORE saving. It is a superset of `tools/validate_briefing_schema.py` — catching issues at the skill level is cheaper than letting them reach the deploy gate.

## Self-check checklist

1. **JSON validity** — `json.dumps(payload, ensure_ascii=False)` does not raise.
2. **Required fields** — every field in this skill's "Output contract" section is present and non-empty (per `references/output_contracts.md`).
3. **Banned words** — no word from `references/editorial_rules.md` banned list appears in prose (case-insensitive, word-boundary).
4. **Citation integrity** — every `<sup>N</sup>` has a matching `sources[i].id`.
5. **Encoding sanity** — no `U+FFFD` (REPLACEMENT CHARACTER) anywhere in the serialized output. All reads + writes use `encoding='utf-8'`, writes use `ensure_ascii=False`.
6. **JSON I/O discipline** — follow `references/json_io_pattern.md` for every read and write.

## Canonical Python block (copy into Step N "Validate" for every producer)

```python
import json, re, sys

# ── Inputs ──
# payload   : the dict you are about to write
# path      : where you are about to write it
# required  : list of top-level keys this skill owns (e.g. ['headline', 'analysis', 'sources'])
# prose_fields : list of HTML/prose fields to scan for banned words
# sources_field : name of the sources array (usually 'sources' or 'industrySources')

# ── 1. JSON validity ──
try:
    serialized = json.dumps(payload, ensure_ascii=False)
except Exception as e:
    sys.exit(f"FAIL — JSON SERIALIZATION: {e}")

# ── 2. Required fields ──
missing = [k for k in required if k not in payload or payload[k] in (None, "", [], {})]
if missing:
    sys.exit(f"FAIL — MISSING REQUIRED FIELDS: {missing}")

# ── 3. Banned-word scan ──
BANNED = [
    "should", "must", "hopefully", "unfortunately", "worrying", "promising",
    "encouraging", "welcome", "bullish", "bearish", "concerning", "headwind",
    "tailwind", "thrilled", "feared", "hoped",
    # extended editorial list
    "good news", "bad news", "optimistic", "pessimistic", "troubling", "reassuring",
]
prose_blob = " ".join(str(payload.get(f, "")) for f in prose_fields)
hits = [w for w in BANNED if re.search(r"\b" + re.escape(w) + r"\b", prose_blob, re.IGNORECASE)]
if hits:
    sys.exit(f"FAIL — BANNED WORDS FOUND: {hits}")

# ── 4. Citation integrity ──
sup_refs = set(int(x) for x in re.findall(r"<sup>(\d+)</sup>", prose_blob))
source_ids = set(s.get("id") for s in payload.get(sources_field, []) if isinstance(s, dict))
orphaned = sup_refs - source_ids
if orphaned:
    sys.exit(f"FAIL — ORPHANED CITATIONS: {orphaned}")

# ── 5. Encoding sanity ──
if "\ufffd" in serialized:
    sys.exit("FAIL — U+FFFD REPLACEMENT CHARACTER found in payload. "
             "Root cause: non-UTF-8 input file (CP1252 smart quotes or em-dashes) "
             "read without encoding='utf-8', or concatenated byte slices. "
             "See references/json_io_pattern.md.")

# ── 6. Persist (UTF-8, ensure_ascii=False) ──
with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)

# ── 7. Verify on-disk bytes ──
with open(path, "r", encoding="utf-8") as f:
    disk = f.read()
if "\ufffd" in disk:
    sys.exit(f"FAIL — U+FFFD in file after write: {path}")

print(f"OK — self-check passed: {path}")
```

## Why each step exists

- **Step 1** — catches circular refs, non-serializable types (datetime, set), malformed nesting before deploy.
- **Step 2** — producer-gap detection. Validator's 0 FAIL is only meaningful if every producer contracts its own output.
- **Step 3** — editorial-policy drift. Banned words are the first tell that wire-service tone slipped.
- **Step 4** — broken `<sup>N</sup>` refs render as literal superscript garbage on the frontend.
- **Step 5** — the mojibake class. 83 `U+FFFD` reached `briefing_latest.json` because a producer concatenated CP1252 bytes into a UTF-8 string; the validator now tolerates but the frontend shows replacement diamonds. Reject at write time.
- **Step 7** — bytes on disk are what deploys. Tripwire for encoding drift introduced by the fs layer, file copy, or git line-ending conversion.

## Skill-specific extensions

Every skill's SKILL.md "Self-check" section points here AND lists its own required fields, prose fields, and sources array name. Do not reimplement this block inline — reference it.

## Relationship to the deploy gate

`tools/validate_briefing_schema.py` runs at GATE 3.5, GATE 4, GATE PRE-DEPLOY, and in `update_dashboard.py` post-export. Any FAIL blocks the weekly/daily ship. This self-check should be a **superset** of what the validator inspects — if your skill emits output that passes self-check but fails the validator, either:

1. The validator caught a schema gap your self-check missed (extend this block), or
2. Your output contract in SKILL.md is stale — re-read `references/output_contracts.md` and align.

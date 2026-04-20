# JSON I/O Pattern — mojibake-proof reads and writes

Canonical pattern every tldr-* producer MUST follow for JSON I/O. This reference exists because em-dash corruption reached `briefing_latest.json` with 83 `U+FFFD` replacement characters in production — root cause was a producer reading a CP1252-bytes file without explicit `encoding='utf-8'`, then serializing the mojibake-bearing string into the briefing.

## Canonical read

```python
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
```

## Canonical write

```python
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

## Encoding sanity audit (run after every read, before every write)

```python
def assert_utf8_clean(blob, label=""):
    """Abort if U+FFFD (REPLACEMENT CHARACTER) is present. U+FFFD means
    bytes were decoded with errors='replace' somewhere upstream. Root
    cause is almost always a missing encoding='utf-8' on open() or a
    byte-level concat of mismatched codepages."""
    if isinstance(blob, (dict, list)):
        blob = json.dumps(blob, ensure_ascii=False)
    if "\ufffd" in blob:
        raise RuntimeError(
            f"U+FFFD REPLACEMENT CHARACTER in {label!r} — "
            "root cause: non-UTF-8 read or CP1252 bytes concatenated "
            "into a UTF-8 string. Fix the upstream read site, do not "
            "post-process the output."
        )
```

Usage:

```python
# after read
with open(path, "r", encoding="utf-8") as f:
    dossier = json.load(f)
assert_utf8_clean(dossier, label=path)

# before write
assert_utf8_clean(payload, label=path)
with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)

# after write (defense in depth)
with open(path, "r", encoding="utf-8") as f:
    assert_utf8_clean(f.read(), label=path)
```

## What NOT to do

```python
# NEVER — platform-dependent default encoding (Windows = cp1252)
with open(path) as f: data = json.load(f)

# NEVER — double-encodes non-ASCII, breaks <strong>— (em-dash) display
json.dump(data, f, indent=2)            # missing ensure_ascii=False
json.dump(data, f, indent=2, ensure_ascii=True)

# NEVER — concatenating bytes of unknown encoding
raw1 = open(a, "rb").read()
raw2 = open(b, "rb").read()
combined = (raw1 + raw2).decode("utf-8", errors="replace")  # breeds U+FFFD
```

## Why `ensure_ascii=False` matters

`ensure_ascii=True` (the default) escapes every non-ASCII codepoint as `\uXXXX`. The briefing pipeline relies on native UTF-8 for em-dashes (`—`), non-breaking spaces, smart quotes, province names (Québec, Yukon), and `<sup>N</sup>` citation markup. Escaping those:

- Bloats file size (each char becomes 6 bytes)
- Breaks the frontend's `<sup>` and `<strong>` parsing when it round-trips through legacy converters
- Introduces double-escape bugs when downstream producers re-serialize

## Why explicit `encoding='utf-8'` matters

On Windows (user's dev environment), `open()` without `encoding=` defaults to `cp1252`. CP1252 maps em-dash (`—`, U+2014) to byte `0x97`, smart-quote-right (`"`) to byte `0x94`, etc. When that byte is later decoded as UTF-8, the codec sees an invalid continuation byte and either raises `UnicodeDecodeError` or — with `errors='replace'` — emits `U+FFFD`.

Every read site must force UTF-8. Every write site must force UTF-8. No exceptions.

## One-line copy-paste checklist

- [ ] Every `open(path, "r"...)` has `encoding="utf-8"`.
- [ ] Every `open(path, "w"...)` has `encoding="utf-8"`.
- [ ] Every `json.dump(...)` has `ensure_ascii=False`.
- [ ] Every producer runs `assert_utf8_clean(...)` after read and before write.
- [ ] Verify on-disk bytes: after write, reopen with `encoding="utf-8"` and re-check for `U+FFFD`.
